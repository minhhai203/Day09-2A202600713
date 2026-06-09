"""CLI demo — Supervisor–Workers legal advisory system."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

from Lab_Assignment.graph import build_graph, describe_topology

DEFAULT_QUESTION = (
    "Nếu một công ty vi phạm hợp đồng và trốn thuế, "
    "hậu quả pháp lý và tuân thủ quy định là gì?"
)


async def main() -> None:
    load_dotenv()
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    print("=" * 70)
    print("Lab Assignment — Supervisor–Workers Pattern")
    print("=" * 70)
    print(f"\nTopology: {describe_topology()}")
    print(f"\nWorkers: law_worker, tax_worker, compliance_worker (3 specialists)")
    print(f"\nCâu hỏi: {question}\n")
    print("Đang xử lý...\n")

    graph = build_graph()
    result = await graph.ainvoke({
        "question": question,
        "workers_plan": [],
        "law_result": "",
        "tax_result": "",
        "compliance_result": "",
        "final_answer": "",
    })

    print(f"Supervisor chọn workers: {result.get('workers_plan', [])}\n")
    print("=" * 70)
    print("KẾT QUẢ")
    print("=" * 70)
    print(result["final_answer"])
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
