"""Customer Agent LangGraph definition.

Uses create_react_agent with a `delegate_to_legal_agent` tool that:
1. Discovers the Law Agent via the registry
2. Sends the question to it via A2A
3. Returns the comprehensive legal response to the user

The tool accepts context propagation data (trace_id, context_id, depth)
via a closure — these are bound per-request in agent_executor.py.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from common.llm import get_llm

logger = logging.getLogger(__name__)

CUSTOMER_SYSTEM_PROMPT = """Bạn là trợ lý pháp lý tại quầy lễ tân của hệ thống multi-agent.

Nhiệm vụ:
1. Hiểu câu hỏi pháp lý của người dùng
2. Với câu hỏi cần phân tích chuyên sâu (hợp đồng, thuế, tuân thủ, trách nhiệm doanh nghiệp…),
   dùng tool `delegate_to_legal_agent` gửi sang Law Agent
3. Trình bày câu trả lời tổng hợp rõ ràng cho người dùng

Luôn dùng `delegate_to_legal_agent` với câu hỏi pháp lý phức tạp.
Không tự trả lời từ kiến thức nội bộ khi cần chuyên gia.
Trả lời bằng tiếng Việt, chuyên nghiệp và dễ hiểu.
"""


def build_graph(trace_id: str, context_id: str, depth: int) -> Any:
    """Build a create_react_agent graph with trace context bound into the tool closure.

    Args:
        trace_id: UUID generated at this request's entry point.
        context_id: A2A context_id for this conversation.
        depth: Delegation depth (0 at customer agent).

    Returns:
        A compiled LangGraph agent.
    """

    @tool
    async def delegate_to_legal_agent(question: str) -> str:
        """Send a legal question to the Law Agent for comprehensive analysis.

        The Law Agent will coordinate Tax and Compliance sub-agents in parallel
        and return a synthesised response covering all relevant legal dimensions.

        Args:
            question: The legal question to analyse.

        Returns:
            A comprehensive legal analysis from the multi-agent system.
        """
        from common.a2a_client import delegate
        from common.registry_client import discover

        logger.info(
            "Customer delegate_to_legal_agent | trace=%s context=%s depth=%d",
            trace_id, context_id, depth,
        )

        try:
            endpoint = await discover("legal_question")
            result = await delegate(
                endpoint=endpoint,
                question=question,
                context_id=context_id,
                trace_id=trace_id,
                depth=depth + 1,
                from_service="customer",
            )
            if not result:
                return "Law Agent trả về rỗng. Vui lòng thử lại."
            return result
        except Exception as exc:
            logger.exception("delegate_to_legal_agent failed: %s", exc)
            return f"Không thể kết nối Law Agent: {exc}"

    llm = get_llm()
    graph = create_react_agent(
        model=llm,
        tools=[delegate_to_legal_agent],
        prompt=CUSTOMER_SYSTEM_PROMPT,
    )
    return graph