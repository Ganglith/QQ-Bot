"""把一段长回复拆成几条短消息，模拟真人连打；同时保留原有的换行排版。"""
from __future__ import annotations

_SENT_END = set("。！？!?…～~")


def split_text(text: str, max_parts: int = 3, max_len: int = 120) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    # 1) 先切成 (句子, 该句之后是否换行)
    units: list[tuple[str, bool]] = []
    buf = ""
    for ch in text:
        if ch == "\n":
            if buf.strip():
                units.append((buf.strip(), True))
                buf = ""
            elif units:
                units[-1] = (units[-1][0], True)
        else:
            buf += ch
            if ch in _SENT_END:
                units.append((buf.strip(), False))
                buf = ""
    if buf.strip():
        units.append((buf.strip(), False))

    # 1.5) 超长单句（没有标点）硬切，避免撑爆单条消息
    normalized: list[tuple[str, bool]] = []
    for sentence, line_break in units:
        while len(sentence) > max_len:
            normalized.append((sentence[:max_len], False))
            sentence = sentence[max_len:]
        if sentence:
            normalized.append((sentence, line_break))
    units = normalized

    # 2) 合并成不超过 max_len 的块；同段内直接连，跨段保留换行
    chunks: list[str] = []
    cur = ""
    prev_break = False  # 上一句之后是否换行
    for sentence, line_break in units:
        if not cur:
            cur = sentence
        elif len(cur) + len(sentence) <= max_len:
            cur += ("\n" if prev_break else "") + sentence
        else:
            chunks.append(cur)
            cur = sentence
        prev_break = line_break
    if cur:
        chunks.append(cur)

    # 3) 超过 max_parts 就把多余的部分并到最后一条
    if len(chunks) > max_parts:
        head = chunks[: max_parts - 1]
        head.append("\n".join(chunks[max_parts - 1:]))
        chunks = head

    return chunks
