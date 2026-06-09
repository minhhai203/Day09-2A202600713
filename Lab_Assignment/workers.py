"""Specialist worker nodes for the Supervisor–Workers graph."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from common.llm import get_llm


async def law_worker(state: dict) -> dict:
    """Worker 1 — contract, tort, general business law."""
    llm = get_llm()
    messages = [
        SystemMessage(
            content=(
                "Bạn là luật sư doanh nghiệp. Phân tích khía cạnh pháp lý (hợp đồng, trách nhiệm). "
                "Trả lời bằng tiếng Việt, tối đa 150 từ."
            )
        ),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    return {"law_result": result.content}


async def tax_worker(state: dict) -> dict:
    """Worker 2 — tax law, IRS, penalties."""
    llm = get_llm()
    context = state.get("law_result", "")
    messages = [
        SystemMessage(
            content=(
                "Bạn là luật sư thuế. Phân tích khía cạnh thuế (IRS, trốn thuế, phạt). "
                "Trả lời bằng tiếng Việt, tối đa 150 từ."
            )
        ),
        HumanMessage(
            content=f"Câu hỏi: {state['question']}\n\nPhân tích pháp lý (tham khảo):\n{context or 'N/A'}"
        ),
    ]
    result = await llm.ainvoke(messages)
    return {"tax_result": result.content}


async def compliance_worker(state: dict) -> dict:
    """Worker 3 — SEC, SOX, GDPR, regulatory compliance."""
    llm = get_llm()
    context = state.get("law_result", "")
    messages = [
        SystemMessage(
            content=(
                "Bạn là chuyên viên tuân thủ (SEC, SOX, GDPR, AML). "
                "Trả lời bằng tiếng Việt, tối đa 150 từ."
            )
        ),
        HumanMessage(
            content=f"Câu hỏi: {state['question']}\n\nPhân tích pháp lý (tham khảo):\n{context or 'N/A'}"
        ),
    ]
    result = await llm.ainvoke(messages)
    return {"compliance_result": result.content}


WORKER_NODES = {
    "law": law_worker,
    "tax": tax_worker,
    "compliance": compliance_worker,
}
