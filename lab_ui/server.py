"""Lab Dashboard — FastAPI server chạy stages và stream log qua SSE."""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
ROOT = Path(__file__).resolve().parent.parent
LAB_PROGRESS = ROOT / "LAB_PROGRESS.md"
CODELAB = ROOT / "CODELAB.md"

from common.trace_log import TRACE_FILE, clear_trace_log, read_trace_events, build_trace_summary

app = FastAPI(title="Legal Multi-Agent Lab Dashboard")

# Track background service PIDs (Stage 5)
_service_proc: subprocess.Popen | None = None


class StartServicesRequest(BaseModel):
    latency_optimized: bool = False

STAGE_COMMANDS: dict[str, dict] = {
    "1": {
        "label": "Stage 1 — Direct LLM",
        "cmd": ["uv", "run", "python", "stages/stage_1_direct_llm/main.py"],
        "timeout": 120,
    },
    "2": {
        "label": "Stage 2 — RAG + Tools",
        "cmd": ["uv", "run", "python", "stages/stage_2_rag_tools/main.py"],
        "timeout": 180,
    },
    "3": {
        "label": "Stage 3 — ReAct Agent",
        "cmd": ["uv", "run", "python", "stages/stage_3_single_agent/main.py"],
        "timeout": 180,
    },
    "4": {
        "label": "Stage 4 — Multi-Agent",
        "cmd": ["uv", "run", "python", "stages/stage_4_milti_agent/main.py"],
        "timeout": 300,
    },
    "5-test": {
        "label": "Test Client (E2E)",
        "cmd": ["uv", "run", "python", "test_client.py"],
        "timeout": 600,
    },
    "ex2": {
        "label": "Exercise 2 — Tools",
        "cmd": ["uv", "run", "python", "exercises/exercise_2_tools.py"],
        "timeout": 180,
    },
    "ex4": {
        "label": "Exercise 4 — Multi-Agent",
        "cmd": ["uv", "run", "python", "exercises/exercise_4_multiagent.py"],
        "timeout": 300,
    },
}


def _parse_lab_sections() -> dict[str, str]:
    """Trích nội dung từng phần trong LAB_PROGRESS.md."""
    if not LAB_PROGRESS.exists():
        return {}

    text = LAB_PROGRESS.read_text(encoding="utf-8")
    pattern = re.compile(r"^## (Phần \d+:[^\n]+)", re.MULTILINE)
    matches = list(pattern.finditer(text))
    sections: dict[str, str] = {}

    for i, match in enumerate(matches):
        part_num = re.search(r"Phần (\d+)", match.group(1))
        if not part_num:
            continue
        key = part_num.group(1)
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[key] = text[start:end].strip()

    # Phần tổng quan + lệnh chạy nhanh
    overview_end = matches[0].start() if matches else len(text)
    sections["overview"] = text[:overview_end].strip()
    return sections


def _env_with_path() -> dict[str, str]:
    env = os.environ.copy()
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    uv_bin = Path.home() / ".local" / "bin"
    if uv_bin.exists():
        env["PATH"] = f"{uv_bin}:{env.get('PATH', '')}"
    return env


async def _stream_process(cmd: list[str], timeout: int) -> AsyncIterator[str]:
    """Chạy subprocess và yield từng dòng log dạng SSE."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=_env_with_path(),
    )

    assert proc.stdout is not None
    try:
        async with asyncio.timeout(timeout):
            while True:
                line = await proc.stdout.readline()
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip("\n\r")
                yield f"data: {json.dumps({'type': 'log', 'line': decoded}, ensure_ascii=False)}\n\n"

        await proc.wait()
        status = "success" if proc.returncode == 0 else "error"
        yield (
            f"data: {json.dumps({'type': 'done', 'code': proc.returncode, 'status': status}, ensure_ascii=False)}\n\n"
        )
    except TimeoutError:
        proc.kill()
        yield f"data: {json.dumps({'type': 'error', 'line': f'⏱️ Timeout sau {timeout}s — đã dừng process.'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'code': -1, 'status': 'error'}, ensure_ascii=False)}\n\n"


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/sections")
async def get_sections() -> dict:
    sections = _parse_lab_sections()
    return {
        "sections": sections,
        "commands": {k: {"label": v["label"], "timeout": v["timeout"]} for k, v in STAGE_COMMANDS.items()},
        "root": str(ROOT),
    }


@app.get("/api/run/{stage_id}")
async def run_stage(stage_id: str) -> StreamingResponse:
    if stage_id not in STAGE_COMMANDS:
        return StreamingResponse(
            iter([f"data: {json.dumps({'type': 'error', 'line': f'Unknown stage: {stage_id}'})}\n\n"]),
            media_type="text/event-stream",
        )

    cfg = STAGE_COMMANDS[stage_id]
    cmd = cfg["cmd"]
    timeout = cfg["timeout"]

    async def event_stream() -> AsyncIterator[str]:
        if stage_id == "5-test":
            clear_trace_log()
        yield f"data: {json.dumps({'type': 'start', 'label': cfg['label'], 'cmd': ' '.join(cmd)}, ensure_ascii=False)}\n\n"
        async for chunk in _stream_process(cmd, timeout):
            yield chunk

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/services/start")
async def start_services(body: StartServicesRequest | None = None) -> dict:
    global _service_proc
    if _service_proc and _service_proc.poll() is None:
        return {"status": "already_running", "pid": _service_proc.pid}

    script = ROOT / "start_all.sh"
    if not script.exists():
        return {"status": "error", "message": "start_all.sh not found"}

    req = body or StartServicesRequest()
    env = _env_with_path()
    if req.latency_optimized:
        env["LATENCY_OPTIMIZED"] = "1"
        env["LLM_MAX_TOKENS"] = "350"
        mode_msg = "Tối ưu latency (~45s) — LATENCY_OPTIMIZED=1, LLM_MAX_TOKENS=350"
    else:
        env.pop("LATENCY_OPTIMIZED", None)
        env.pop("LLM_MAX_TOKENS", None)
        mode_msg = "Baseline (~150s) — không bật tối ưu latency"

    _service_proc = subprocess.Popen(
        ["bash", str(script)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        preexec_fn=os.setsid if sys.platform != "win32" else None,
    )
    return {
        "status": "started",
        "pid": _service_proc.pid,
        "message": f"Đang khởi động 5 services… (~10s). {mode_msg}",
        "latency_optimized": req.latency_optimized,
        "env": {
            "LATENCY_OPTIMIZED": env.get("LATENCY_OPTIMIZED"),
            "LLM_MAX_TOKENS": env.get("LLM_MAX_TOKENS"),
        },
    }


@app.post("/api/services/stop")
async def stop_services() -> dict:
    global _service_proc
    killed: list[str] = []

    if _service_proc and _service_proc.poll() is None:
        try:
            os.killpg(os.getpgid(_service_proc.pid), signal.SIGTERM)
            killed.append(f"start_all.sh (pid {_service_proc.pid})")
        except ProcessLookupError:
            pass
        _service_proc = None

    for port in (10000, 10100, 10101, 10102, 10103):
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            for pid in result.stdout.strip().split():
                if pid:
                    os.kill(int(pid), signal.SIGTERM)
                    killed.append(f"port {port} (pid {pid})")
        except (subprocess.TimeoutExpired, ProcessLookupError, ValueError):
            pass

    return {"status": "stopped", "killed": killed or ["Không có process nào đang chạy"]}


@app.get("/api/services/status")
async def services_status() -> dict:
    ports = {"registry": 10000, "customer": 10100, "law": 10101, "tax": 10102, "compliance": 10103}
    status: dict[str, bool] = {}
    for name, port in ports.items():
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            status[name] = bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            status[name] = False

    running = _service_proc is not None and _service_proc.poll() is None
    return {"start_all_running": running, "ports": status, "all_up": all(status.values())}


@app.post("/api/trace/clear")
async def clear_trace() -> dict:
    clear_trace_log()
    return {"status": "cleared", "file": str(TRACE_FILE)}


@app.get("/api/trace/events")
async def get_trace_events(trace_id: str | None = None) -> dict:
    events = read_trace_events(trace_id)
    summary = build_trace_summary(events)
    return {"events": events, "summary": summary, "file": str(TRACE_FILE)}


@app.get("/api/trace/stream")
async def trace_stream() -> StreamingResponse:
    """SSE stream of JSONL trace events (shared across all agent processes)."""

    async def event_stream() -> AsyncIterator[str]:
        pos = 0
        if TRACE_FILE.exists():
            text = TRACE_FILE.read_text(encoding="utf-8")
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    yield f"data: {json.dumps({'type': 'trace', 'event': evt}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    pass
            pos = TRACE_FILE.stat().st_size

        while True:
            await asyncio.sleep(0.25)
            if not TRACE_FILE.exists():
                continue
            with TRACE_FILE.open("r", encoding="utf-8") as fh:
                fh.seek(pos)
                chunk = fh.read()
                pos = fh.tell()
            for line in chunk.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    evt = json.loads(line)
                    yield f"data: {json.dumps({'type': 'trace', 'event': evt}, ensure_ascii=False)}\n\n"
                except json.JSONDecodeError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    print(f"🚀 Lab Dashboard: http://localhost:8765")
    print(f"   Project root: {ROOT}")
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="warning")
