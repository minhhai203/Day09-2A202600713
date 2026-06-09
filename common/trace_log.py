"""Structured trace events for distributed A2A observability.

Events are written as JSONL to `.trace_events.jsonl` and echoed as
`[TRACE] {...}` on stdout so lab UI and terminals can correlate hops.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
TRACE_FILE = Path(os.getenv("TRACE_LOG_FILE", str(ROOT / ".trace_events.jsonl")))

SERVICE_PORTS: dict[str, int] = {
    "registry": 10000,
    "customer": 10100,
    "law": 10101,
    "tax": 10102,
    "compliance": 10103,
    "test_client": 0,
}

SERVICE_LABELS: dict[str, str] = {
    "test_client": "Test Client",
    "customer": "Customer Agent",
    "law": "Law Agent",
    "tax": "Tax Agent",
    "compliance": "Compliance Agent",
    "registry": "Registry",
}


def clear_trace_log() -> None:
    """Reset trace file before a new E2E run."""
    TRACE_FILE.write_text("", encoding="utf-8")


def preview_text(text: str, max_len: int = 160) -> str:
    """Single-line preview for UI and terminal summaries."""
    one_line = " ".join(str(text).split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 1].rstrip() + "…"


def trace_event(
    event: str,
    *,
    trace_id: str,
    service: str,
    **fields: Any,
) -> None:
    """Append one trace event and print a parseable line for streaming UIs."""
    payload: dict[str, Any] = {
        "ts": time.time(),
        "event": event,
        "trace_id": trace_id,
        "service": service,
    }
    port = SERVICE_PORTS.get(service)
    if port is not None:
        payload["port"] = port
    payload.update(fields)

    line = json.dumps(payload, ensure_ascii=False)
    print(f"[TRACE] {line}", flush=True)

    try:
        TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TRACE_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def read_trace_events(trace_id: str | None = None) -> list[dict[str, Any]]:
    """Load trace events from JSONL, optionally filtered by trace_id."""
    if not TRACE_FILE.exists():
        return []

    events: list[dict[str, Any]] = []
    for line in TRACE_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        if trace_id and evt.get("trace_id") != trace_id:
            continue
        events.append(evt)
    return events


def build_trace_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build call graph + per-agent result summary from raw events."""
    if not events:
        return {
            "trace_id": None,
            "call_chain": [],
            "agent_results": [],
            "graph_nodes": [],
            "routing": None,
            "latency_s": None,
            "hop_count": 0,
            "incomplete": True,
            "warning": "Không có trace events. Chạy Test Client sau khi services đã khởi động.",
        }

    trace_id = events[-1].get("trace_id")
    call_chain: list[dict[str, Any]] = []
    agent_results: dict[str, dict[str, Any]] = {}
    graph_nodes: list[str] = []
    routing: dict[str, Any] | None = None
    latency_s: float | None = None

    for evt in events:
        event_type = evt.get("event")
        if event_type == "request_start":
            call_chain.append(
                {
                    "from": evt.get("service", "test_client"),
                    "to": evt.get("to", "customer"),
                    "depth": evt.get("depth", 0),
                    "protocol": "A2A",
                }
            )
        elif event_type == "a2a_send":
            call_chain.append(
                {
                    "from": evt.get("service"),
                    "to": evt.get("to"),
                    "endpoint": evt.get("endpoint"),
                    "depth": evt.get("depth"),
                    "protocol": "A2A",
                }
            )
        elif event_type == "a2a_recv":
            from_agent = evt.get("from_agent")
            if from_agent:
                agent_results.setdefault(from_agent, {})
                agent_results[from_agent].update(
                    {
                        "service": from_agent,
                        "chars": evt.get("chars", 0),
                        "preview": evt.get("preview", ""),
                        "responded_to": evt.get("service"),
                    }
                )
        elif event_type == "agent_complete":
            svc = evt.get("service")
            if svc:
                agent_results.setdefault(svc, {})
                agent_results[svc].update(
                    {
                        "service": svc,
                        "chars": evt.get("chars", 0),
                        "preview": evt.get("preview", agent_results.get(svc, {}).get("preview", "")),
                        "depth": evt.get("depth"),
                    }
                )
        elif event_type == "graph_node":
            node = evt.get("node")
            if node and node not in graph_nodes:
                graph_nodes.append(node)
        elif event_type == "routing":
            routing = {
                "needs_tax": evt.get("needs_tax"),
                "needs_compliance": evt.get("needs_compliance"),
            }
        elif event_type == "request_complete":
            latency_s = evt.get("latency_s")

    # Deduplicate consecutive identical hops
    deduped_chain: list[dict[str, Any]] = []
    for hop in call_chain:
        if deduped_chain and deduped_chain[-1] == hop:
            continue
        deduped_chain.append(hop)

    incomplete = len(deduped_chain) <= 1
    warning = None
    if incomplete:
        warning = (
            "Chỉ thấy hop từ Test Client. Restart services (Dừng → Khởi động) "
            "để agents load code trace mới, rồi chạy lại Test Client."
        )

    return {
        "trace_id": trace_id,
        "call_chain": deduped_chain,
        "agent_results": list(agent_results.values()),
        "graph_nodes": graph_nodes,
        "routing": routing,
        "latency_s": latency_s,
        "hop_count": len(deduped_chain),
        "event_count": len(events),
        "incomplete": incomplete,
        "warning": warning,
    }


def print_trace_summary(trace_id: str) -> None:
    """Print human-readable call graph and agent previews to stdout."""
    events = read_trace_events(trace_id)
    summary = build_trace_summary(events)

    print("\n" + "=" * 60)
    print("TRACE SUMMARY — Luồng gọi giữa các Agent")
    print("=" * 60)
    print(f"Trace ID: {trace_id}")
    print(f"Events: {summary['event_count']} · Hops: {summary['hop_count']}", end="")
    if summary.get("latency_s") is not None:
        print(f" · Latency: {summary['latency_s']}s")
    else:
        print()

    if summary.get("warning"):
        print(f"\n⚠️  {summary['warning']}\n")

    print("\n[Call chain]")
    if not summary["call_chain"]:
        print("  (trống)")
    for i, hop in enumerate(summary["call_chain"], 1):
        src = SERVICE_LABELS.get(hop["from"], hop["from"])
        dst = SERVICE_LABELS.get(hop["to"], hop["to"])
        port = SERVICE_PORTS.get(hop["to"])
        port_str = f" :{port}" if port else ""
        print(f"  {i}. {src} ──A2A──▶ {dst}{port_str}  (depth={hop.get('depth', '?')})")

    if summary.get("routing"):
        r = summary["routing"]
        print(
            f"\n[Law Agent routing] needs_tax={r.get('needs_tax')} · "
            f"needs_compliance={r.get('needs_compliance')}"
        )

    if summary.get("graph_nodes"):
        print(f"\n[Law Agent graph] {' → '.join(summary['graph_nodes'])}")

    print("\n[Kết quả từng agent]")
    if not summary["agent_results"]:
        print("  (chưa có — agents chưa ghi trace hoặc chưa restart services)")
    else:
        for item in summary["agent_results"]:
            label = SERVICE_LABELS.get(item["service"], item["service"])
            chars = item.get("chars", 0)
            prev = item.get("preview") or "(không có preview)"
            print(f"  • {label} ({chars} chars)")
            print(f"    {prev}")

    print("=" * 60)


def endpoint_to_service(endpoint: str) -> str:
    """Map agent base URL to a short service name."""
    for name, port in SERVICE_PORTS.items():
        if f":{port}" in endpoint:
            return name
    return endpoint.rstrip("/").rsplit("/", 1)[-1]
