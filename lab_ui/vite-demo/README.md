# Vite Demo — Lab Dashboard (giống bản HTML gốc)

Port **toàn bộ** `lab_ui/index.html` sang Vite: cùng sidebar, buttons, terminal log, trace A2A, theme toggle.

## Chạy

**Terminal 1 — Backend API (bắt buộc):**

```bash
cd /path/to/Day09-2A202600713
uv run python lab_ui/server.py
# hoặc: bash lab_ui/start.sh
```

**Terminal 2 — Vite:**

```bash
cd lab_ui/vite-demo
npm install
npm run dev
```

Mở **http://localhost:5173**

## UI giống bản gốc

- Sidebar: Tổng quan, Phần 0–6, Exercise 2/4
- Nút **▶ Chạy** / **▶ Chạy Test Client** / **Khởi động Services** / **Dừng Services**
- Toggle **⚡ Tối ưu latency**
- Terminal log: **Clear**, **Copy**, **Auto-scroll**
- Trace A2A (Stage 5)
- Phần học tập markdown từ `LAB_PROGRESS.md`

## Build

```bash
npm run build
npm run preview
```
