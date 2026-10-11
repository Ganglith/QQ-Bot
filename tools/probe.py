#!/usr/bin/env python3
"""
OneBot 连接探针：直连 NapCat 的 WebSocket，把收到的所有原始事件打印出来。
用来排查「连接成功但发消息机器人没反应」——到底是消息没到，还是机器人没处理。

用法（在项目根目录）：
    # 建议先停掉机器人，避免抢连接
    systemctl stop qqbot
    ./.venv/bin/python tools/probe.py
    # 如果 NapCat 配了 access_token：
    ./.venv/bin/python tools/probe.py ws://127.0.0.1:3001 你的token

然后：用另一个 QQ 给机器人发一条消息（群里就 @ 它），
观察本脚本有没有打印出事件。
"""
from __future__ import annotations

import asyncio
import json
import sys
from urllib.parse import quote

import websockets


def build_url(ws_url: str, token: str) -> str:
    if not token:
        return ws_url
    sep = "&" if "?" in ws_url else "?"
    return f"{ws_url}{sep}access_token={quote(token)}"


async def main() -> None:
    ws_url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:3001"
    token = sys.argv[2] if len(sys.argv) > 2 else ""
    url = build_url(ws_url, token)

    print(f"正在连接 {ws_url} ...")
    async with websockets.connect(url, ping_interval=None, max_size=2 ** 23) as ws:
        print("已连接 ✅")

        # 1) 验证「请求-响应」通道是否正常
        await ws.send(json.dumps(
            {"action": "get_login_info", "params": {}, "echo": "probe-login"},
            ensure_ascii=False,
        ))

        print("=" * 60)
        print("现在用【另一个 QQ】给机器人发一条消息（群里就 @ 它）")
        print("下面会实时打印收到的原始内容，Ctrl+C 退出")
        print("=" * 60)

        async for raw in ws:
            try:
                data = json.loads(raw)
            except Exception:  # noqa: BLE001
                print("（非 JSON）", str(raw)[:300])
                continue

            echo = data.get("echo")
            if echo == "probe-login":
                info = data.get("data") or {}
                print(f"\n[通道测试] 登录信息：{json.dumps(info, ensure_ascii=False)}")
                if info.get("user_id"):
                    print(">>> WebSocket 通道正常，机器人账号已登录\n")
                else:
                    print(">>> 通道能通，但拿不到登录信息（账号可能没登录）\n")
                continue

            if echo is not None:
                print(f"\n[API响应 echo={echo}] {json.dumps(data, ensure_ascii=False)[:300]}")
                continue

            post_type = data.get("post_type")
            if post_type == "message":
                print("\n>>> 收到消息事件：")
                print(f"    类型: {data.get('message_type')} / {data.get('sub_type')}")
                print(f"    用户: {data.get('user_id')}  群: {data.get('group_id')}")
                print(f"    原始: {data.get('raw_message')}")
            elif post_type == "meta_event":
                print(f"[元事件] {data.get('meta_event_type')}")
            else:
                print(f"[其他事件] {json.dumps(data, ensure_ascii=False)[:300]}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n已退出")
    except Exception as e:  # noqa: BLE001
        print(f"连接失败：{e}")
        print("检查：NapCat 是否在线、ws_url 端口是否正确、access_token 是否填对")
