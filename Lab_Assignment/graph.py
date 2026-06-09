"""Supervisor–Workers LangGraph for legal advisory.

Pattern:
    supervisor_plan → dispatch workers (Send, parallel) → supervisor_synthesize → END

Improvement over Day08 / Stage 3:
- Stage 3: một ReAct agent xử lý mọi domain
- Lab_Assignment: Supervisor phân công 3 workers chuyên môn (law, tax, compliance)
"""

from __future__ import annotations

import json
import re
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send
from langgraph.graph import END, StateGraph

from common.llm import get_llm
from Lab_Assignment.workers import WORKER_NODES, compliance_worker, law_worker, tax_worker


def _last_wins(left: str | None, right: str | None) -> str:
    return right if right is not None else (left or "")


class SupervisorState(TypedDict):
    question: str
    workers_plan: list[str]
    law_result: Annotated[str, _last_wins]
    tax_result: Annotated[str, _last_wins]
    compliance_result: Annotated[str, _last_wins]
    final_answer: str


def _keyword_plan(question: str) -> list[str]:
    """Fallback routing when LLM JSON parse fails."""
    q = question.lower()
    plan: list[str] = ["law"]
    if any(kw in q for kw in ["tax", "irs", "thuế", "trốn", "tránh"]):
        plan.append("tax")
    if any(kw in q for kw in ["compliance", "sec", "sox", "gdpr", "tuân thủ", "quy định", "dữ liệu", "privacy"]):
        plan.append("compliance")
    return plan


async def supervisor_plan(state: SupervisorState) -> dict:
    """Supervisor: decide which workers to invoke."""
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "Bạn là supervisor điều phối workers pháp lý. "
                "Chọn workers cần thiết từ: law, tax, compliance.\n"
                "Trả lời CHỈ bằng JSON array, ví dụ: [\"law\", \"tax\"]\n"
                "law = luôn cần cho câu hỏi pháp lý chung\n"
                "tax = thuế, IRS, trốn thuế\n"
                "compliance = SEC, SOX, GDPR, tuân thủ quy định"
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    raw = result.content.strip()

    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

    plan: list[str] = []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            plan = [str(w).lower() for w in parsed if str(w).lower() in WORKER_NODES]
    except json.JSONDecodeError:
        plan = _keyword_plan(state["question"])

    if not plan:
        plan = _keyword_plan(state["question"])
    if "law" not in plan:
        plan.insert(0, "law")

    return {"workers_plan": plan}


def dispatch_workers(state: SupervisorState) -> list[Send]:
    """Supervisor dispatches parallel Send to selected workers."""
    sends: list[Send] = []
    for worker in state.get("workers_plan", []):
        if worker == "law":
            sends.append(Send("law_worker", state))
        elif worker == "tax":
            sends.append(Send("tax_worker", state))
        elif worker == "compliance":
            sends.append(Send("compliance_worker", state))

    if not sends:
        sends.append(Send("supervisor_synthesize", state))
    return sends


async def supervisor_synthesize(state: SupervisorState) -> dict:
    """Supervisor aggregates worker outputs into final report."""
    llm = get_llm()
    sections: list[str] = []
    if state.get("law_result"):
        sections.append(f"## Phân tích pháp lý\n{state['law_result']}")
    if state.get("tax_result"):
        sections.append(f"## Phân tích thuế\n{state['tax_result']}")
    if state.get("compliance_result"):
        sections.append(f"## Phân tích tuân thủ\n{state['compliance_result']}")

    combined = "\n\n".join(sections) if sections else state["question"]
    messages = [
        SystemMessage(
            content=(
                "Bạn là supervisor tổng hợp báo cáo pháp lý từ các workers. "
                "Trả lời mạch lạc, có tiêu đề, tối đa 400 từ, tiếng Việt. "
                "Kết bằng disclaimer ngắn."
            )
        ),
        HumanMessage(content=f"Câu hỏi gốc: {state['question']}\n\n{combined}"),
    ]
    result = await llm.ainvoke(messages)
    return {"final_answer": result.content}


def build_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor_plan", supervisor_plan)
    graph.add_node("law_worker", law_worker)
    graph.add_node("tax_worker", tax_worker)
    graph.add_node("compliance_worker", compliance_worker)
    graph.add_node("supervisor_synthesize", supervisor_synthesize)

    graph.set_entry_point("supervisor_plan")
    graph.add_conditional_edges(
        "supervisor_plan",
        dispatch_workers,
        ["law_worker", "tax_worker", "compliance_worker", "supervisor_synthesize"],
    )
    graph.add_edge("law_worker", "supervisor_synthesize")
    graph.add_edge("tax_worker", "supervisor_synthesize")
    graph.add_edge("compliance_worker", "supervisor_synthesize")
    graph.add_edge("supervisor_synthesize", END)

    return graph.compile()


def describe_topology() -> str:
    return (
        "supervisor_plan → [law_worker ∥ tax_worker ∥ compliance_worker] "
        "→ supervisor_synthesize → END"
    )
