# Lab Assignment — Supervisor–Workers

Cải tiến **Day08 RAG Agent** (`Day08_2A202600713/personal_project/2A202600713_DangMinhHai`) bằng pattern **Supervisor–Workers** với **3 workers**.

## Day08 gốc (monolithic)

```
Câu hỏi → Task 9 retrieve() → Task 10 generate_with_citation() → Trả lời
```

Một pipeline xử lý mọi loại câu hỏi (luật + tin tức), không tách chuyên môn retrieval.

## Lab_Assignment (Supervisor–Workers)

```
                    ┌─────────────────┐
                    │ supervisor_plan │  ← phân loại: legal / news / hybrid
                    └────────┬────────┘
                             │ Send (parallel)
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
    │legal_worker │  │ news_worker │  │hybrid_worker │
    │ (luật)      │  │ (báo chí)   │  │ (Task 9 full)│
    └──────┬──────┘  └──────┬──────┘  └──────┬───────┘
           └─────────────────┼─────────────────┘
                             ▼
                  ┌──────────────────────┐
                  │ supervisor_merge     │  ← RRF + rerank (Task 7)
                  └──────────┬───────────┘
                             ▼
                  ┌──────────────────────┐
                  │ generation_worker    │  ← Task 10 citation
                  └──────────────────────┘
```

## 3 Workers

| Worker | Vai trò | Day08 module |
|--------|---------|--------------|
| `legal_worker` | Retrieval văn bản pháp luật (`type=legal`) | Task 5 + 6 + 7 |
| `news_worker` | Retrieval tin tức nghệ sĩ (`type=news`) | Task 5 + 6 + 7 |
| `hybrid_worker` | Full hybrid + PageIndex fallback | Task 9 |
| `generation_worker` | Sinh câu trả lời có citation | Task 10 |

## Yêu cầu môi trường

1. **Day08 repo** phải nằm cạnh Day09:
   ```
   Assignment/
   ├── Day08_2A202600713/
   │   └── personal_project/2A202600713_DangMinhHai/
   └── Day09-2A202600713/
       └── Lab_Assignment/
   ```

2. **Index Day08** đã build (`data/.cache/task4_index.json`)

3. **API key** trong `.env` (Day09 hoặc Day08):
   - `OPENAI_API_KEY` — embedding + generation (Task 4, 10)
   - Hoặc OpenRouter qua Day09 `common/llm.py` cho supervisor routing

## Chạy

```bash
cd Day09-2A202600713

# Câu hỏi mặc định (luật)
uv run python Lab_Assignment/main.py

# Câu hỏi tùy chỉnh
uv run python Lab_Assignment/main.py "Nghệ sĩ nào bị bắt vì ma tuý?"
```

## So sánh cải tiến

| | Day08 Task 10 | Lab_Assignment |
|---|---------------|----------------|
| Kiến trúc | Monolithic | Supervisor + 3 workers |
| Retrieval | Một pipeline cho all | Tách legal / news / hybrid |
| Parallel | Không | Workers chạy song song (Send) |
| Routing | Không | Supervisor plan theo loại câu hỏi |
| Generation | Gộp trong 1 hàm | Worker riêng sau merge |

## Files

| File | Mô tả |
|------|--------|
| `day08_bridge.py` | Import path tới Day08 personal project |
| `retrieval_helpers.py` | Retrieval theo doc type + merge |
| `generation.py` | Task 10 từ chunks đã merge |
| `workers.py` | 3 retrieval workers + generation |
| `graph.py` | LangGraph Supervisor–Workers |
| `main.py` | CLI demo |
