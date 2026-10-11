#!/usr/bin/env python3
"""
把「酒馆（SillyTavern）角色卡」转成本项目可用的 persona.md。

支持的输入：
  - .json   角色卡 JSON（V1 平铺格式 / V2 / V3）
  - .png    内嵌角色卡的 PNG（tEXt / iTXt 里的 chara 或 ccv3 数据块）

用法：
  python tools/card2persona.py 卡片.png                 # 打印到屏幕
  python tools/card2persona.py 卡片.png -o persona.md   # 直接写入人设文件

纯标准库实现，不需要 Pillow，也不需要酒馆。
"""
from __future__ import annotations

import argparse
import base64
import json
import struct
import zlib
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"


# ----------------------------------------------------------------------
# PNG 里读取角色卡
# ----------------------------------------------------------------------
def _decode_card_blob(raw: bytes) -> dict | None:
    """卡块内容通常是 base64(JSON)，也兼容直接是明文 JSON。"""
    text = raw.strip()
    for attempt in (
        lambda: json.loads(base64.b64decode(text).decode("utf-8")),
        lambda: json.loads(text.decode("utf-8")),
    ):
        try:
            obj = attempt()
            if isinstance(obj, dict):
                return obj
        except Exception:  # noqa: BLE001
            continue
    return None


def _iter_png_text_chunks(path: Path):
    data = path.read_bytes()
    if data[:8] != PNG_SIG:
        return
    pos = 8
    while pos + 8 <= len(data):
        (length,) = struct.unpack(">I", data[pos:pos + 4])
        ctype = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length

        if ctype == b"tEXt":
            keyword, _, text = chunk.partition(b"\x00")
            yield keyword.decode("latin-1", "ignore"), text
        elif ctype == b"iTXt":
            # keyword \0 flag method lang \0 translated \0 text
            parts = chunk.split(b"\x00", 4)
            if len(parts) == 5:
                keyword = parts[0].decode("latin-1", "ignore")
                compressed = parts[1][:1] == b"\x01"
                text = parts[4]
                if compressed:
                    try:
                        text = zlib.decompress(text)
                    except zlib.error:
                        continue
                yield keyword, text
        elif ctype == b"IEND":
            return


def load_card(path: Path) -> dict:
    if path.suffix.lower() == ".json":
        card = json.loads(path.read_text(encoding="utf-8"))
    else:
        found: dict[str, dict] = {}
        for keyword, raw in _iter_png_text_chunks(path):
            if keyword in ("chara", "ccv3"):
                decoded = _decode_card_blob(raw)
                if decoded:
                    found[keyword] = decoded
        card = found.get("ccv3") or found.get("chara")
        if not card:
            raise SystemExit(
                "这个 PNG 里没找到角色卡数据（chara / ccv3 数据块缺失）。\n"
                "确认下载的是「角色卡 PNG」，而不是普通图片。"
            )
    return _normalize(card)


def _normalize(card: dict) -> dict:
    """V2/V3 把字段放在 data 里；V1 是平铺的。"""
    data = card.get("data") if isinstance(card.get("data"), dict) else card
    keys = [
        "name", "description", "personality", "scenario",
        "first_mes", "mes_example", "system_prompt",
        "post_history_instructions", "creator_notes", "creator", "tags",
    ]
    out = {k: data.get(k) for k in keys}
    out["tags"] = data.get("tags") or []
    return out


# ----------------------------------------------------------------------
# 生成 persona.md
# ----------------------------------------------------------------------
def to_persona(card: dict) -> str:
    name = (card.get("name") or "角色").strip()
    lines: list[str] = [f"# 人设：{name}", ""]

    if card.get("description"):
        lines += ["## 身份与背景", str(card["description"]).strip(), ""]
    if card.get("personality"):
        lines += ["## 性格", str(card["personality"]).strip(), ""]
    if card.get("scenario"):
        lines += ["## 场景设定", str(card["scenario"]).strip(), ""]
    if card.get("system_prompt"):
        lines += ["## 额外系统指令", str(card["system_prompt"]).strip(), ""]
    if card.get("mes_example"):
        lines += ["## 说话示例（模仿这个风格）", str(card["mes_example"]).strip(), ""]
    if card.get("first_mes"):
        lines += ["## 开场白（参考语气即可）", str(card["first_mes"]).strip(), ""]

    # QQ 场景的通用规则（酒馆卡里没有，必须补上）
    lines += [
        "## 说话规则（务必遵守）",
        "1. 每次回复控制在 1~3 句、50 字以内，像发 QQ 消息一样，不要长篇大论。",
        "2. 绝对不要说自己是 AI、大模型、程序，也不要说「作为一个 AI 助手」。",
        "3. 不要用书面语，不要列 1234 条，不要用 Markdown 标题。",
        "4. 遇到违法、色情、暴力、诈骗、政治敏感等话题，用一句轻松的话岔开，不要接。",
        "",
    ]

    if card.get("post_history_instructions"):
        lines += ["## 附加要求", str(card["post_history_instructions"]).strip(), ""]

    meta = []
    if card.get("creator"):
        meta.append(f"作者：{card['creator']}")
    if card.get("tags"):
        meta.append("标签：" + "、".join(str(t) for t in card["tags"]))
    if meta:
        lines += ["<!-- 来源信息：" + "；".join(meta) + " -->", ""]

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="酒馆角色卡 -> persona.md")
    parser.add_argument("card", help="角色卡文件路径（.png 或 .json）")
    parser.add_argument("-o", "--output", help="输出文件；不填则打印到屏幕")
    args = parser.parse_args()

    path = Path(args.card)
    if not path.exists():
        raise SystemExit(f"文件不存在：{path}")

    card = load_card(path)
    text = to_persona(card)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"已写入 {args.output}（角色：{card.get('name')}）")
    else:
        print(text)


if __name__ == "__main__":
    main()
