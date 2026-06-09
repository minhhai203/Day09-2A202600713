"""3 Workers — cải tiến Day08 monolithic RAG (Task 9 + 10)."""

from __future__ import annotations

from Lab_Assignment.generation import generate_from_chunks
from Lab_Assignment.retrieval_helpers import (
    merge_worker_chunks,
    retrieve_for_type,
    retrieve_hybrid_full,
)


def _chunk_key(item: dict) -> str:
    return (item.get("content") or "")[:120]


def legal_worker(state: dict) -> dict:
    """Worker 1 — retrieval chuyên văn bản pháp luật (legal/)."""
    chunks = retrieve_for_type(state["question"], "legal", top_k=5)
    return {
        "legal_chunks": chunks,
        "worker_logs": [f"legal_worker: {len(chunks)} chunks"],
    }


def news_worker(state: dict) -> dict:
    """Worker 2 — retrieval chuyên tin tức / nghệ sĩ (news/)."""
    chunks = retrieve_for_type(state["question"], "news", top_k=5)
    return {
        "news_chunks": chunks,
        "worker_logs": [f"news_worker: {len(chunks)} chunks"],
    }


def hybrid_worker(state: dict) -> dict:
    """Worker 3 — full hybrid pipeline Task 9 (fallback / câu hỏi phức tạp)."""
    chunks = retrieve_hybrid_full(state["question"], top_k=5)
    return {
        "hybrid_chunks": chunks,
        "worker_logs": [f"hybrid_worker: {len(chunks)} chunks"],
    }


def supervisor_merge(state: dict) -> dict:
    """Supervisor merge chunks từ các workers + rerank."""
    lists = [
        state.get("legal_chunks") or [],
        state.get("news_chunks") or [],
        state.get("hybrid_chunks") or [],
    ]
    merged = merge_worker_chunks(state["question"], lists, top_k=5)
    logs = list(state.get("worker_logs") or [])
    logs.append(f"supervisor_merge: {len(merged)} chunks sau rerank")
    return {"merged_chunks": merged, "worker_logs": logs}


def generation_worker(state: dict) -> dict:
    """Worker generation — Task 10, dùng chunks đã merge."""
    result = generate_from_chunks(state["question"], state.get("merged_chunks") or [])
    logs = list(state.get("worker_logs") or [])
    logs.append(f"generation_worker: mode={result.get('generation_mode')}")
    return {
        "final_answer": result["answer"],
        "sources": result["sources"],
        "metadata": {
            "workers_plan": state.get("workers_plan", []),
            "retrieval_source": result.get("retrieval_source"),
            "generation_mode": result.get("generation_mode"),
            "source_count": len(result.get("sources") or []),
            "worker_logs": logs,
        },
    }


WORKER_NODE_NAMES = ("legal_worker", "news_worker", "hybrid_worker")
