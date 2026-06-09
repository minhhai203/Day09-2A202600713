"""End-to-end test client for the Legal Multi-Agent System.

Sends a legal question to the Customer Agent and prints the response.
"""

import asyncio
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

CUSTOMER_AGENT_URL = os.getenv("CUSTOMER_AGENT_URL", "http://localhost:10100")

QUESTION = (
    "Nếu một công ty vi phạm hợp đồng và trốn thuế, "
    "hậu quả pháp lý và tuân thủ quy định là gì?"
)


async def main() -> None:
    from uuid import uuid4

    from common.trace_log import clear_trace_log, print_trace_summary, trace_event

    trace_id = str(uuid4())
    context_id = str(uuid4())
    clear_trace_log()

    print(f"Connecting to Customer Agent at {CUSTOMER_AGENT_URL}")
    print(f"Câu hỏi: {QUESTION}")
    print(f"Trace ID: {trace_id}")
    print("-" * 60)

    trace_event(
        "request_start",
        trace_id=trace_id,
        service="test_client",
        to="customer",
        context_id=context_id,
        depth=0,
    )

    async with httpx.AsyncClient(timeout=300.0) as http_client:
        # Resolve agent card
        card_url = f"{CUSTOMER_AGENT_URL}/.well-known/agent.json"
        try:
            card_resp = await http_client.get(card_url)
            card_resp.raise_for_status()
        except Exception as e:
            print(f"ERROR: Could not reach Customer Agent at {card_url}")
            print(f"  {e}")
            print("Make sure all services are running (./start_all.sh)")
            sys.exit(1)

        from a2a.types import AgentCard, Message, Part, Role, TextPart, MessageSendParams
        from a2a.client import A2AClient

        agent_card = AgentCard.model_validate(card_resp.json())
        print(f"Connected to agent: {agent_card.name} v{agent_card.version}")
        print("-" * 60)

        # Build the legacy A2AClient
        client = A2AClient(httpx_client=http_client, agent_card=agent_card)

        # Construct the message
        from a2a.types import SendMessageRequest, MessageSendParams as MSP
        message = Message(
            role=Role.user,
            parts=[Part(root=TextPart(text=QUESTION))],
            message_id=str(uuid4()),
            context_id=context_id,
            metadata={
                "trace_id": trace_id,
                "context_id": context_id,
                "delegation_depth": 0,
            },
        )
        request = SendMessageRequest(
            id=str(uuid4()),
            params=MSP(message=message),
        )

        print("Sending request (this may take 30-60s while agents chain)...\n")
        print("[Request flow — watch trace panel or grep [TRACE] in service logs]")
        print(f"  test_client → customer (:10100) → law (:10101) → [tax ∥ compliance]")
        print("-" * 60)

        start = time.perf_counter()
        response = await client.send_message(request)
        elapsed = time.perf_counter() - start
        print(f"\n⏱️  Latency: {elapsed:.2f}s ({elapsed:.1f} giây)\n")

        trace_event(
            "request_complete",
            trace_id=trace_id,
            service="test_client",
            latency_s=round(elapsed, 2),
        )

        # Parse response
        result_text = ""
        if hasattr(response, "root"):
            root = response.root
            if hasattr(root, "result"):
                result = root.result
                # Task with artifacts
                if hasattr(result, "artifacts") and result.artifacts:
                    for artifact in result.artifacts:
                        for part in artifact.parts:
                            p = part.root if hasattr(part, "root") else part
                            if hasattr(p, "text"):
                                result_text += p.text
                # Message with parts
                elif hasattr(result, "parts") and result.parts:
                    for part in result.parts:
                        p = part.root if hasattr(part, "root") else part
                        if hasattr(p, "text"):
                            result_text += p.text

        if result_text:
            print("KẾT QUẢ:")
            print("=" * 60)
            print(result_text)
            print("=" * 60)
            print(f"\nTrace ID (correlate logs): {trace_id}")
            print(f"Trace file: .trace_events.jsonl")
            print_trace_summary(trace_id)
        else:
            print("Không nhận được câu trả lời. Raw response:")
            print(response)


if __name__ == "__main__":
    asyncio.run(main())
