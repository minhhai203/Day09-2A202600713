"""Supervisor–Workers LangGraph — cải tiến Day08 RAG Chatbot.

Day08 (monolithic):
    generate_with_citation() → retrieve() → reorder → LLM

Lab_Assignment (Supervisor–Workers):
    supervisor_plan → [legal_worker ∥ news_worker ∥ hybrid_worker]
                   → supervisor_merge → generation_worker → END
"""

from __future__ import annotations

import json
import operator
import re
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send
from langgraph.graph import END, StateGraph

from common.llm import get_llm
from Lab_Assignment.workers import (
    WORKER_NODE_NAMES,
    generation_worker,
    hybrid_worker,
    legal_worker,
    news_worker,
    supervisor_merge,
)


def _merge_logs(left: list[str] | None, right: list[str] | None) -> list[str]:
    return (left or []) + (right or [])


class SupervisorState(TypedDict):
    question: str
    workers_plan: list[str]
    legal_chunks: list[dict]
    news_chunks: list[dict]
    hybrid_chunks: list[dict]
    merged_chunks: list[dict]
    worker_logs: Annotated[list[str], _merge_logs]
    final_answer: str
    sources: list[dict]
    metadata: dict


LEGAL_KEYWORDS = (
    "luật", "điều", "nghị định", "hình phạt", "phạm tội", "tàng trữ",
    "cai nghiện", "ma tuý", "chất ma tuý", "hình sự", "quy định", "pháp luật",
)
NEWS_KEYWORDS = (
    "nghệ sĩ", "ca sĩ", "diễn viên", "bắt", "khởi tố", "tin tức", "báo",
    "scandal", "vụ án", "showbiz", "rapper", "singer",
)


def keyword_plan(question: str) -> list[str]:
    q = question.lower()
    plan: list[str] = []
    if any(kw in q for kw in LEGAL_KEYWORDS):
        plan.append("legal")
    if any(kw in q for kw in NEWS_KEYWORDS):
        plan.append("news")
    if not plan:
        plan.append("hybrid")
    elif len(plan) == 2:
        plan.append("hybrid")  # câu hỏi mixed → thêm full pipeline
    return plan


async def supervisor_plan(state: SupervisorState) -> dict:
    """Supervisor: phân loại câu hỏi → chọn workers (legal / news / hybrid)."""
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "Bạn là supervisor RAG về pháp luật ma tuý Việt Nam. "
                "Chọn workers cần gọi từ: legal, news, hybrid.\n"
                "legal = văn bản luật, điều khoản, hình phạt\n"
                "news = tin tức nghệ sĩ, vụ án báo chí\n"
                "hybrid = câu hỏi phức tạp hoặc cần full retrieval pipeline\n"
                "Trả lời CHỈ JSON array, ví dụ: [\"legal\", \"news\"]"
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
            plan = [str(w).lower() for w in parsed if str(w).lower() in WORKER_NODE_NAMES]
    except json.JSONDecodeError:
        plan = keyword_plan(state["question"])

    if not plan:
        plan = keyword_plan(state["question"])

    return {
        "workers_plan": plan,
        "worker_logs": [f"supervisor_plan: workers={plan}"],
    }


def dispatch_workers(state: SupervisorState) -> list[Send]:
    sends: list[Send] = []
    for worker in state.get("workers_plan", []):
        if worker == "legal":
            sends.append(Send("legal_worker", state))
        elif worker == "news":
            sends.append(Send("news_worker", state))
        elif worker == "hybrid":
            sends.append(Send("hybrid_worker", state))
    if not sends:
        sends.append(Send("hybrid_worker", state))
    return sends


def build_graph():
    graph = StateGraph(SupervisorState)

    graph.add_node("supervisor_plan", supervisor_plan)
    graph.add_node("legal_worker", legal_worker)
    graph.add_node("news_worker", news_worker)
    graph.add_node("hybrid_worker", hybrid_worker)
    graph.add_node("supervisor_merge", supervisor_merge)
    graph.add_node("generation_worker", generation_worker)

    graph.set_entry_point("supervisor_plan")
    graph.add_conditional_edges(
        "supervisor_plan",
        dispatch_workers,
        list(WORKER_NODE_NAMES),
    )
    graph.add_edge("legal_worker", "supervisor_merge")
    graph.add_edge("news_worker", "supervisor_merge")
    graph.add_edge("hybrid_worker", "supervisor_merge")
    graph.add_edge("supervisor_merge", "generation_worker")
    graph.add_edge("generation_worker", END)

    return graph.compile()


def describe_topology() -> str:
    return (
        "supervisor_plan → [legal_worker ∥ news_worker ∥ hybrid_worker] "
        "→ supervisor_merge → generation_worker → END"
    )
