"""Tax Agent LangGraph definition.

Uses create_react_agent with a tax-specialised system prompt.
No tools — it answers purely from LLM knowledge.
"""

from __future__ import annotations

import os

from langgraph.prebuilt import create_react_agent

from common.llm import get_llm

TAX_SYSTEM_PROMPT_FAST = (
    "Luật sư thuế. Trả lời tối đa 80 từ, dạng gạch đầu dòng. "
    "Chỉ mang tính giáo dục. Trả lời bằng tiếng Việt."
)

TAX_SYSTEM_PROMPT = """Bạn là luật sư thuế và CPA, chuyên:
- Luật thuế doanh nghiệp (liên bang, bang, quốc tế)
- Trốn thuế vs. tránh thuế — phân biệt pháp lý và hậu quả
- IRS, kiểm tra, chuyển hồ sơ hình sự
- Phạt theo IRC §§ 6651, 6662, 6663
- FBAR/FATCA, transfer pricing (IRC § 482)
- Tội gian lận thuế (18 U.S.C. § 7201–7207)
- Trách nhiệm công ty và cá nhân (lãnh đạo)

Khi trả lời, nêu rõ:
1. Phạt dân sự vs. hình sự và mức phạt
2. Thời hiệu (6 năm / không giới hạn nếu gian lận)
3. Cơ quan liên quan (IRS, DOJ Tax Division, FinCEN)
4. Trách nhiệm công ty vs. cá nhân

Trả lời ngắn gọn trong tối đa 2 câu, bằng tiếng Việt.
Ghi chú: chỉ mang tính giáo dục, nên hỏi luật sư có chứng chỉ.
"""


def create_graph():
    """Return a compiled LangGraph create_react_agent for tax questions."""
    llm = get_llm()
    prompt = (
        TAX_SYSTEM_PROMPT_FAST
        if os.getenv("LATENCY_OPTIMIZED", "").lower() in ("1", "true", "yes")
        else TAX_SYSTEM_PROMPT
    )
    graph = create_react_agent(
        model=llm,
        tools=[],
        prompt=prompt,
    )
    return graph
