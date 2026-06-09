"""Generation worker — Task 10 Day08, nhận chunks đã merge từ supervisor."""

from __future__ import annotations

from Lab_Assignment.day08_bridge import ensure_day08_available

ensure_day08_available()

from tasks.task10_generation import (  # noqa: E402
    SYSTEM_PROMPT,
    TOP_K,
    TOP_P,
    TEMPERATURE,
    _call_openai,
    _extractive_answer,
    _has_sufficient_evidence,
    _source_label,
    format_context,
    reorder_for_llm,
)


def generate_from_chunks(query: str, chunks: list[dict]) -> dict:
    """Sinh câu trả lời có citation từ chunks (không retrieve lại)."""
    ordered = reorder_for_llm(chunks[:TOP_K])
    context = format_context(ordered)

    if not _has_sufficient_evidence(query, ordered):
        answer = "Tôi không thể xác minh thông tin này từ nguồn hiện có."
        return {
            "answer": answer,
            "sources": ordered,
            "retrieval_source": ordered[0].get("source", "none") if ordered else "none",
            "generation_mode": "none",
        }

    answer = _call_openai(query, context)
    generation_mode = "openai" if answer else "extractive"
    if not answer or "[" not in (answer or ""):
        answer = _extractive_answer(query, ordered)
        generation_mode = "extractive"

    if "[" not in answer and ordered:
        answer = f"{answer}\n\n" + " ".join(f"[{_source_label(c)}]" for c in ordered[:2])

    return {
        "answer": answer.strip(),
        "sources": ordered,
        "retrieval_source": ordered[0].get("source", "hybrid") if ordered else "none",
        "generation_mode": generation_mode,
        "top_p": TOP_P,
        "temperature": TEMPERATURE,
        "system_prompt": SYSTEM_PROMPT[:80] + "...",
    }
