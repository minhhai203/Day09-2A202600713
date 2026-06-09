#!/bin/bash
cd "$(dirname "$0")/.."
source "$HOME/.local/bin/env" 2>/dev/null || true
echo "🚀 Lab Dashboard → http://localhost:8765"
uv run python lab_ui/server.py
