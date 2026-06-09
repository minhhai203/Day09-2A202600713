"""Compliance Agent LangGraph definition.

Uses create_react_agent with a regulatory-compliance-specialised system prompt.
No tools — it answers purely from LLM knowledge.
"""

from __future__ import annotations

import os

from langgraph.prebuilt import create_react_agent

from common.llm import get_llm

COMPLIANCE_SYSTEM_PROMPT_FAST = (
    "Chuyên viên tuân thủ quy định. Trả lời tối đa 80 từ, dạng gạch đầu dòng. "
    "Chỉ mang tính giáo dục. Trả lời bằng tiếng Việt."
)

COMPLIANCE_SYSTEM_PROMPT = """Bạn là chuyên viên tuân thủ quy định và luật sư doanh nghiệp, chuyên:
- SEC, SOX, FTC, FCPA, AML/BSA
- GDPR, CCPA, bảo vệ dữ liệu
- Quản trị doanh nghiệp, nghĩa vụ fiduciaries
- Cơ chế báo cáo nội bộ, bảo vệ whistleblower
- Cấm tham gia hợp đồng chính phủ (debarment)

Khi trả lời, nêu rõ:
1. Cơ quan có thẩm quyền (SEC, FTC, DOJ, EPA, FinCEN…)
2. Biện pháp hành chính, dân sự, hình sự
3. Trách nhiệm cá nhân (C-suite, HĐQT, compliance officer)
4. Yếu tố giảm nhẹ: tự công bố, hợp tác, khắc phục
5. Rủi ro xuyên biên giới với công ty đa quốc gia

Trả lời bằng tiếng Việt.
Ghi chú: chỉ mang tính giáo dục, nên hỏi luật sư có chứng chỉ.
"""


def create_graph():
    """Return a compiled LangGraph create_react_agent for compliance questions."""
    llm = get_llm()
    prompt = (
        COMPLIANCE_SYSTEM_PROMPT_FAST
        if os.getenv("LATENCY_OPTIMIZED", "").lower() in ("1", "true", "yes")
        else COMPLIANCE_SYSTEM_PROMPT
    )
    graph = create_react_agent(
        model=llm,
        tools=[],
        prompt=prompt,
    )
    return graph
