"""Retrieval helpers — tách theo worker, dùng lại Task 5–9 Day08."""

from __future__ import annotations

from Lab_Assignment.day08_bridge import ensure_day08_available

ensure_day08_available()

from tasks.task5_semantic_search import semantic_search  # noqa: E402
from tasks.task6_lexical_search import lexical_search  # noqa: E402
from tasks.task7_reranking import rerank, rerank_rrf  # noqa: E402
from tasks.task8_pageindex_vectorless import pageindex_search  # noqa: E402
from tasks.task9_retrieval_pipeline import retrieve as day08_retrieve  # noqa: E402


def _filter_by_type(chunks: list[dict], doc_type: str) -> list[dict]:
    filtered = []
    for item in chunks:
        meta = item.get("metadata") or {}
        if meta.get("type") == doc_type:
            filtered.append(item)
    return filtered


def retrieve_for_type(query: str, doc_type: str, top_k: int = 5) -> list[dict]:
    """Hybrid retrieval (semantic + lexical + RRF + rerank) trên subset legal/news."""
    dense = _filter_by_type(semantic_search(query, top_k=top_k * 4), doc_type)
    sparse = _filter_by_type(lexical_search(query, top_k=top_k * 4), doc_type)

    if not dense and not sparse:
        return []

    merged = rerank_rrf([dense, sparse], top_k=top_k * 2)
    for item in merged:
        item["source"] = f"{doc_type}-hybrid"
        item["worker"] = f"{doc_type}_worker"

    if not merged:
        return []

    ranked = rerank(query, merged, top_k=top_k, method="cross_encoder")
    return ranked[:top_k]


def retrieve_hybrid_full(query: str, top_k: int = 5) -> list[dict]:
    """Full Day08 Task 9 pipeline (fallback / câu hỏi tổng hợp)."""
    chunks = day08_retrieve(query, top_k=top_k)
    for item in chunks:
        item["worker"] = "hybrid_worker"
    return chunks


def merge_worker_chunks(query: str, chunk_lists: list[list[dict]], top_k: int = 5) -> list[dict]:
    """Supervisor merge: dedupe + RRF + rerank across workers."""
    seen: set[str] = set()
    pool: list[dict] = []
    for chunks in chunk_lists:
        for item in chunks:
            key = (item.get("content") or "")[:200]
            if key in seen:
                continue
            seen.add(key)
            pool.append(item)

    if not pool:
        fallback = pageindex_search(query, top_k=top_k)
        for item in fallback:
            item["worker"] = "pageindex_fallback"
        return fallback

    if len(pool) <= top_k:
        return pool

    merged = rerank_rrf([pool], top_k=min(len(pool), top_k * 2))
    return rerank(query, merged, top_k=top_k, method="cross_encoder")
