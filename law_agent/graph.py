"""Law Agent LangGraph StateGraph definition.

Graph topology:
    analyze_law → check_routing → (parallel) call_tax + call_compliance → aggregate → END

The parallel branches (call_tax / call_compliance) are dispatched via LangGraph's
Send API so that both sub-agent calls happen concurrently.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send
from langgraph.graph import END, StateGraph

from common.llm import get_llm
from common.trace_log import trace_event

logger = logging.getLogger(__name__)

MAX_DELEGATION_DEPTH = 3


# ---------------------------------------------------------------------------
# State definition
# ---------------------------------------------------------------------------

def _last_wins(a: str, b: str) -> str:
    """Reducer: keep the most recently written value."""
    return b if b else a


class LawState(TypedDict):
    question: str
    context_id: str
    trace_id: str
    delegation_depth: int
    law_analysis: str
    needs_tax: bool
    needs_compliance: bool
    # Annotated so parallel branches can both write without conflict
    tax_result: Annotated[str, _last_wins]
    compliance_result: Annotated[str, _last_wins]
    final_answer: str


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def _latency_optimized() -> bool:
    return os.getenv("LATENCY_OPTIMIZED", "").lower() in ("1", "true", "yes")


async def analyze_law(state: LawState) -> dict:
    """LLM analysis from a contract / general law perspective."""
    trace_event(
        "graph_node",
        trace_id=state["trace_id"],
        service="law",
        node="analyze_law",
        depth=state.get("delegation_depth", 0),
    )
    llm = get_llm()
    if _latency_optimized():
        system = (
            "Luật sư doanh nghiệp. Phân tích ngắn gọn câu hỏi pháp lý. "
            "Tối đa 120 từ, dạng gạch đầu dòng. Trả lời bằng tiếng Việt."
        )
    else:
        system = (
            "Bạn là luật sư tranh tụng doanh nghiệp, chuyên hợp đồng, trách nhiệm dân sự "
            "và luật kinh doanh. Phân tích khía cạnh pháp lý, điều luật và trách nhiệm. "
            "Trả lời bằng tiếng Việt."
        )
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    return {"law_analysis": result.content}


async def check_routing(state: LawState) -> dict:
    """Determine whether tax and/or compliance sub-agents are needed.

    Returns updated state flags so the routing function can read them.
    If delegation depth is already at the max, skip further delegation.
    """
    depth = state.get("delegation_depth", 0)
    if depth >= MAX_DELEGATION_DEPTH:
        logger.info("Max delegation depth reached (%d); skipping sub-agents", depth)
        return {"needs_tax": False, "needs_compliance": False}

    if _latency_optimized():
        question_lower = state["question"].lower()
        needs_tax = any(
            kw in question_lower
            for kw in ["tax", "irs", "thuế", "avoid", "trốn", "tránh"]
        )
        needs_compliance = any(
            kw in question_lower
            for kw in [
                "compliance", "sec", "regulation", "regulatory", "sox", "aml",
                "tuân thủ", "quy định",
            ]
        )
        logger.info("Fast keyword routing: needs_tax=%s needs_compliance=%s", needs_tax, needs_compliance)
    else:
        llm = get_llm()
        messages = [
            SystemMessage(
                content=(
                    'You are a legal routing expert. Based on the question, decide whether '
                    'specialist sub-agents are needed.\n'
                    'Reply with ONLY valid JSON — no markdown, no extra text:\n'
                    '{"needs_tax": <true|false>, "needs_compliance": <true|false>}\n\n'
                    'needs_tax = true  → question involves tax law, IRS, tax evasion, penalties\n'
                    'needs_compliance = true → question involves regulatory compliance, SEC, SOX, AML, FCPA'
                )
            ),
            HumanMessage(content=state["question"]),
        ]
        result = await llm.ainvoke(messages)
        raw = result.content.strip()

        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Routing LLM returned non-JSON: %r — defaulting to both=True", raw)
            parsed = {"needs_tax": True, "needs_compliance": True}

        needs_tax = bool(parsed.get("needs_tax", True))
        needs_compliance = bool(parsed.get("needs_compliance", True))
    logger.info("Routing decision: needs_tax=%s needs_compliance=%s", needs_tax, needs_compliance)
    trace_event(
        "routing",
        trace_id=state["trace_id"],
        service="law",
        needs_tax=needs_tax,
        needs_compliance=needs_compliance,
        depth=state.get("delegation_depth", 0),
    )
    return {"needs_tax": needs_tax, "needs_compliance": needs_compliance}


def route_to_subagents(state: LawState) -> list[Send]:
    """Routing function: dispatch parallel Send objects based on routing flags.

    This function is used with add_conditional_edges; it returns a list of
    Send objects which LangGraph executes as parallel branches.
    """
    sends: list[Send] = []
    if state.get("needs_tax"):
        sends.append(Send("call_tax", state))
    if state.get("needs_compliance"):
        sends.append(Send("call_compliance", state))
    if not sends:
        # No sub-agents needed — go straight to aggregation
        sends.append(Send("aggregate", state))
    else:
        targets = []
        if state.get("needs_tax"):
            targets.append("tax")
        if state.get("needs_compliance"):
            targets.append("compliance")
        trace_event(
            "parallel_dispatch",
            trace_id=state["trace_id"],
            service="law",
            targets=targets,
            depth=state.get("delegation_depth", 0),
        )
    return sends


async def call_tax(state: LawState) -> dict:
    """Delegate to the Tax Agent via A2A."""
    from common.a2a_client import delegate
    from common.registry_client import discover

    try:
        endpoint = await discover("tax_question")
        result = await delegate(
            endpoint=endpoint,
            question=state["question"],
            context_id=state["context_id"],
            trace_id=state["trace_id"],
            depth=state.get("delegation_depth", 0) + 1,
            from_service="law",
        )
        logger.info("Tax Agent returned %d chars", len(result))
        return {"tax_result": result}
    except Exception as exc:
        logger.exception("call_tax failed: %s", exc)
        return {"tax_result": f"[Không có phân tích thuế: {exc}]"}


async def call_compliance(state: LawState) -> dict:
    """Delegate to the Compliance Agent via A2A."""
    from common.a2a_client import delegate
    from common.registry_client import discover

    try:
        endpoint = await discover("compliance_question")
        result = await delegate(
            endpoint=endpoint,
            question=state["question"],
            context_id=state["context_id"],
            trace_id=state["trace_id"],
            depth=state.get("delegation_depth", 0) + 1,
            from_service="law",
        )
        logger.info("Compliance Agent returned %d chars", len(result))
        return {"compliance_result": result}
    except Exception as exc:
        logger.exception("call_compliance failed: %s", exc)
        return {"compliance_result": f"[Không có phân tích tuân thủ: {exc}]"}


async def aggregate(state: LawState) -> dict:
    """Combine law_analysis, tax_result, and compliance_result into a final answer."""
    trace_event(
        "graph_node",
        trace_id=state["trace_id"],
        service="law",
        node="aggregate",
        depth=state.get("delegation_depth", 0),
    )
    llm = get_llm()

    sections: list[str] = []
    if state.get("law_analysis"):
        sections.append(f"## Phân tích pháp lý\n{state['law_analysis']}")
    if state.get("tax_result"):
        sections.append(f"## Phân tích thuế\n{state['tax_result']}")
    if state.get("compliance_result"):
        sections.append(f"## Phân tích tuân thủ quy định\n{state['compliance_result']}")

    combined = "\n\n---\n\n".join(sections)

    if _latency_optimized():
        system = (
            "Tổng hợp các phân tích thành câu trả lời ngắn gọn. Tối đa 200 từ, "
            "có tiêu đề rõ, không lặp. Kết bằng một dòng disclaimer. Trả lời bằng tiếng Việt."
        )
    else:
        system = (
            "Bạn là cố vấn pháp lý cấp cao, tổng hợp phân tích chuyên môn thành câu trả lời "
            "mạch lạc cho khách hàng. Tránh lặp. Kết thúc bằng disclaimer ngắn: chỉ mang tính "
            "giáo dục, nên hỏi luật sư có chứng chỉ. Trả lời bằng tiếng Việt."
        )
    messages = [
        SystemMessage(content=system),
        HumanMessage(content=combined),
    ]
    result = await llm.ainvoke(messages)
    return {"final_answer": result.content}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def create_graph():
    """Build and compile the Law Agent StateGraph."""
    graph = StateGraph(LawState)

    graph.add_node("analyze_law", analyze_law)
    graph.add_node("check_routing", check_routing)
    graph.add_node("call_tax", call_tax)
    graph.add_node("call_compliance", call_compliance)
    graph.add_node("aggregate", aggregate)

    graph.set_entry_point("analyze_law")
    graph.add_edge("analyze_law", "check_routing")

    # Conditional parallel dispatch: after check_routing, route_to_subagents
    # returns a list of Send objects (to call_tax, call_compliance, or aggregate)
    graph.add_conditional_edges(
        "check_routing",
        route_to_subagents,
        ["call_tax", "call_compliance", "aggregate"],
    )

    graph.add_edge("call_tax", "aggregate")
    graph.add_edge("call_compliance", "aggregate")
    graph.add_edge("aggregate", END)

    return graph.compile()