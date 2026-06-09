"""CLI demo — Supervisor–Workers cải tiến Day08 RAG (2A202600713)."""

from __future__ import annotations

import asyncio
import sys

from Lab_Assignment.day08_bridge import load_env, ensure_day08_available
from Lab_Assignment.graph import build_graph, describe_topology

DEFAULT_QUESTION = (
    "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?"
)

DAY08_DEMO_QUESTIONS = [
    "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
    "Những nghệ sĩ nào đã bị bắt vì liên quan tới ma tuý?",
    "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
]


async def main() -> None:
    load_env()
    ensure_day08_available()

    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    print("=" * 70)
    print("Lab Assignment — Supervisor–Workers (Day08 RAG Improvement)")
    print("=" * 70)
    print(f"\nDay08 base: personal_project/2A202600713_DangMinhHai (Task 5–10)")
    print(f"Topology: {describe_topology()}")
    print("\nWorkers (3):")
    print("  • legal_worker   — retrieval văn bản pháp luật")
    print("  • news_worker    — retrieval tin tức / nghệ sĩ")
    print("  • hybrid_worker  — full Task 9 pipeline")
    print("  • generation_worker — Task 10 citation (sau merge)")
    print(f"\nCâu hỏi: {question}\n")
    print("Đang xử lý...\n")

    graph = build_graph()
    result = await graph.ainvoke({
        "question": question,
        "workers_plan": [],
        "legal_chunks": [],
        "news_chunks": [],
        "hybrid_chunks": [],
        "merged_chunks": [],
        "worker_logs": [],
        "final_answer": "",
        "sources": [],
        "metadata": {},
    })

    logs = result.get("worker_logs") or []
    unique_logs = list(dict.fromkeys(logs))
    print(f"Supervisor chọn: {result.get('workers_plan', [])}")
    print("Logs:", " → ".join(unique_logs))
    print(f"Merged chunks: {len(result.get('merged_chunks') or [])}")
    print(f"Generation: {result.get('metadata', {}).get('generation_mode', '?')}")
    print("\n" + "=" * 70)
    print("KẾT QUẢ")
    print("=" * 70)
    print(result["final_answer"])
    print("\n" + "-" * 70)
    print("Nguồn đã dùng:")
    for i, src in enumerate(result.get("sources") or [], 1):
        meta = src.get("metadata") or {}
        title = meta.get("title") or meta.get("citation_label") or meta.get("source") or "?"
        print(f"  {i}. [{src.get('score', 0):.3f}] {title} (worker={src.get('worker', '?')})")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
