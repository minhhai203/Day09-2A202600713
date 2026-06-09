# Lab Assignment — Supervisor–Workers

Cải tiến agent **Day08 / Stage 3** (một ReAct agent xử lý mọi domain) bằng pattern **Supervisor–Workers** với **3 workers** chuyên môn.

## Kiến trúc

```
                    ┌─────────────────┐
                    │ supervisor_plan │  ← quyết định workers nào cần gọi
                    └────────┬────────┘
                             │ Send (parallel)
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐
    │ law_worker  │  │ tax_worker  │  │ compliance_worker│
    └──────┬──────┘  └──────┬──────┘  └────────┬─────────┘
           └─────────────────┼─────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ supervisor_synthesize│  ← tổng hợp báo cáo
                  └──────────────────────┘
```

## So sánh Day08 (Stage 3) vs Lab_Assignment

| | Stage 3 (Day08) | Lab_Assignment |
|---|-----------------|----------------|
| Pattern | Single ReAct agent | Supervisor + 3 Workers |
| Chuyên môn | 1 prompt cho mọi domain | Mỗi worker 1 domain |
| Orchestration | Agent tự chọn tool | Supervisor plan + dispatch |
| Parallel | Không | Workers chạy song song (Send API) |

## Files

| File | Mô tả |
|------|--------|
| `graph.py` | StateGraph: supervisor_plan → workers → supervisor_synthesize |
| `workers.py` | 3 worker nodes: law, tax, compliance |
| `main.py` | CLI demo |

## Chạy

```bash
# Từ project root
uv run python Lab_Assignment/main.py

# Câu hỏi tùy chỉnh
uv run python Lab_Assignment/main.py "Công ty rò rỉ dữ liệu GDPR có bị phạt không?"
```

Yêu cầu: `.env` có `OPENROUTER_API_KEY` (dùng chung `common/llm.py`).
