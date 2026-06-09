"""Bridge tới Day08 personal project (2A202600713_DangMinhHai)."""

from __future__ import annotations

import sys
from pathlib import Path

# Day09 repo root
DAY09_ROOT = Path(__file__).resolve().parents[1]
# Day08 sibling repo
DAY08_ROOT = DAY09_ROOT.parent / "Day08_2A202600713"
DAY08_PERSONAL = DAY08_ROOT / "personal_project" / "2A202600713_DangMinhHai"

for path in (str(DAY09_ROOT), str(DAY08_PERSONAL)):
    if path not in sys.path:
        sys.path.insert(0, path)


def ensure_day08_available() -> Path:
    if not DAY08_PERSONAL.exists():
        raise FileNotFoundError(
            f"Không tìm thấy Day08 project tại {DAY08_PERSONAL}. "
            "Clone/đặt Day08_2A202600713 cạnh Day09 repo."
        )
    return DAY08_PERSONAL


def load_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(DAY09_ROOT / ".env")
    load_dotenv(DAY08_ROOT / ".env", override=False)
