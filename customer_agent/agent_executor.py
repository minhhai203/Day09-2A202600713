"""Customer Agent — AgentExecutor bridge between A2A SDK and LangGraph."""

from __future__ import annotations

import logging
import os
from uuid import uuid4

from langchain_core.messages import HumanMessage

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TextPart

from customer_agent.graph import build_graph
from common.trace_log import trace_event, preview_text

logger = logging.getLogger(__name__)


class CustomerAgentExecutor(AgentExecutor):
    """Bridges A2A RequestContext to the Customer LangGraph agent."""

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = self._extract_question(context)
        context_id = context.context_id or str(uuid4())
        task_id = context.task_id or str(uuid4())

        # Propagate or generate trace metadata
        metadata = context.message.metadata or {} if context.message else {}
        trace_id = metadata.get("trace_id", str(uuid4()))
        depth = int(metadata.get("delegation_depth", 0))

        logger.info(
            "CustomerAgent executing | task=%s context=%s trace=%s depth=%d",
            task_id, context_id, trace_id, depth,
        )
        trace_event(
            "agent_receive",
            trace_id=trace_id,
            service="customer",
            depth=depth,
            task_id=task_id,
            context_id=context_id,
        )

        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.submit()
        await updater.start_work()

        try:
            if os.getenv("LATENCY_OPTIMIZED", "").lower() in ("1", "true", "yes"):
                # Skip ReAct loop — delegate directly to Law Agent (saves 1–2 LLM calls)
                from common.a2a_client import delegate
                from common.registry_client import discover

                endpoint = await discover("legal_question")
                answer = await delegate(
                    endpoint=endpoint,
                    question=question,
                    context_id=context_id,
                    trace_id=trace_id,
                    depth=depth + 1,
                    from_service="customer",
                )
            else:
                graph = build_graph(
                    trace_id=trace_id,
                    context_id=context_id,
                    depth=depth,
                )

                result = await graph.ainvoke(
                    {"messages": [HumanMessage(content=question)]},
                    config={"configurable": {"thread_id": context_id}},
                )

                answer = ""
                for msg in reversed(result.get("messages", [])):
                    if hasattr(msg, "content") and msg.content:
                        if not isinstance(msg, HumanMessage):
                            from langchain_core.messages import AIMessage
                            if isinstance(msg, AIMessage):
                                answer = msg.content
                                break

                if not answer:
                    for msg in reversed(result.get("messages", [])):
                        content = getattr(msg, "content", "")
                        if content and not isinstance(msg, HumanMessage):
                            answer = content
                            break

                if not answer:
                    answer = "Không thể xử lý câu hỏi pháp lý lúc này. Vui lòng thử lại."

            await updater.add_artifact(
                parts=[Part(root=TextPart(text=answer))],
                name="legal_response",
            )
            await updater.complete()
            trace_event(
                "agent_complete",
                trace_id=trace_id,
                service="customer",
                depth=depth,
                chars=len(answer),
                preview=preview_text(answer),
            )

        except Exception as exc:
            logger.exception("CustomerAgent execution error: %s", exc)
            await updater.failed(
                updater.new_agent_message(
                    parts=[Part(root=TextPart(text=f"Yêu cầu thất bại: {exc}"))]
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id or str(uuid4())
        context_id = context.context_id or str(uuid4())
        updater = TaskUpdater(event_queue, task_id, context_id)
        await updater.cancel()

    @staticmethod
    def _extract_question(context: RequestContext) -> str:
        if context.message and context.message.parts:
            parts = []
            for part in context.message.parts:
                inner = getattr(part, "root", part)
                text = getattr(inner, "text", None)
                if text:
                    parts.append(text)
            return "\n".join(parts)
        return ""