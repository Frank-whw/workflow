import os
from typing import Dict


def summarize_card(info: Dict) -> Dict:
    title = "最近活动摘要"
    summary = ""
    if info.get("window_titles"):
        summary += ", ".join(info["window_titles"][:3])
    if info.get("ocr_text"):
        t = info["ocr_text"].strip()
        if t:
            summary += f" | 文本: {t[:120]}"
    return {
        "title": title,
        "summary": summary or "无可用文本",
        "apps": info.get("apps", []),
        "domains": info.get("domains", []),
    }