"""群聊「爬楼总结」：把最近一批群消息整理成简报。"""
from __future__ import annotations

import logging

log = logging.getLogger("qqbot.summary")

SUMMARY_PROMPT = """你是一个群聊助手。下面是一个 QQ 群最近的聊天记录，请输出一份中文「爬楼总结」。

要求：
1. 用 3~6 条要点说明大家在聊什么，每条一句话，尽量带上话题和结论。
2. 如果有明确的信息、决定、待办、约定的时间地点，单独用一行「📌 重点」列出。
3. 最后用一句话概括整个群聊（不超过 20 字）。
4. 不要逐条复述，不要编造记录里没有的内容；提到人时用他们的名字。
5. 直接输出总结正文，不要客套开场白。
"""

# 非文本消息段的占位符
NON_TEXT = {
    "image": "[图片]",
    "face": "[表情]",
    "record": "[语音]",
    "video": "[视频]",
    "file": "[文件]",
    "json": "[卡片]",
    "xml": "[卡片]",
    "reply": "",
    "at": "@",
}


def format_message(msg: dict) -> str:
    sender = msg.get("sender") or {}
    name = str(
        sender.get("card") or sender.get("nickname") or msg.get("user_id") or "某人"
    ).strip()

    segments = msg.get("message")
    if isinstance(segments, str):
        content = segments
    else:
        parts = []
        for seg in segments or []:
            if not isinstance(seg, dict):
                continue
            seg_type = seg.get("type")
            if seg_type == "text":
                parts.append(str(seg.get("data", {}).get("text", "")))
            else:
                parts.append(NON_TEXT.get(seg_type, ""))
        content = "".join(parts)

    content = content.replace("\n", " ").strip()
    return f"{name}: {content}" if content else ""


def format_history(messages: list[dict], max_chars: int) -> tuple[str, int]:
    """把消息列表格式化成文本；从最新往回收，保证不超过 max_chars。"""
    lines = [format_message(m) for m in messages]
    lines = [ln for ln in lines if ln]

    kept: list[str] = []
    total = 0
    for line in reversed(lines):
        if total + len(line) > max_chars and kept:
            break
        kept.append(line)
        total += len(line) + 1
    kept.reverse()
    return "\n".join(kept), len(kept)


class Summarizer:
    def __init__(self, llm, count: int = 200, max_chars: int = 6000):
        self.llm = llm
        self.count = count
        self.max_chars = max_chars

    async def summarize(self, messages: list[dict]) -> str:
        text, n = format_history(messages, self.max_chars)
        if n == 0:
            return "群里最近好像没聊什么诶～"

        payload = [
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": f"群聊记录（共 {n} 条，按时间先后排列）：\n{text}"},
        ]
        return await self.llm.complete(payload, temperature=0.3, max_tokens=800)
