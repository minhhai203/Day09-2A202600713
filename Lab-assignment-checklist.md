# Checklist Assignment Files Day09

## 1. File Lab-Solution.md
Giải quyết các bài Lab trên lớp.

**✅ Hoàn thành:** [Lab-Solution.md](Lab-Solution.md)

## 2. Assignment File: Improve Agent Day08 sử dụng pattern Supervisor - Workers (ít nhất 2-3 workers)
Tạo folder mới tên là `Lab_Assignment` và đặt toàn bộ code dưới folder này.

**✅ Hoàn thành:** [Lab_Assignment/](Lab_Assignment/) — cải tiến Day08 RAG (`2A202600713_DangMinhHai`) với 3 workers: legal, news, hybrid + generation.

```bash
uv run python Lab_Assignment/main.py
```

## 3. Bài cộng điểm — Vite demo Stage 4/5

**✅ Hoàn thành:** [lab_ui/vite-demo/](lab_ui/vite-demo/)

```bash
uv run python lab_ui/server.py          # :8765
cd lab_ui/vite-demo && npm install && npm run dev   # :5173
```

## 4. Thời điểm nộp bài: Trước 24h00 ngày hôm nay.

**Bổ sung:** [SUBMISSION_REPORT.md](SUBMISSION_REPORT.md) — trace flow, fault tolerance, latency benchmark.
