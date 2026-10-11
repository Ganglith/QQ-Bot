"""
QQ AI 机器人（路线 B：个人 QQ 小号）

链路： QQ小号  <->  NapCatQQ(OneBot v11 正向WS)  <->  本程序  <->  DeepSeek API

启动： python main.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from urllib.parse import quote

import websockets

from bot.config import load_config
from bot.groupctx import GroupContext
from bot.llm import LLM
from bot.memory import MemoryStore
from bot.splitter import split_text
from bot.summarizer import Summarizer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("qqbot")

# 私聊场景补充指令
PRIVATE_STYLE = """

## 当前场景：一对一私聊
你现在在和一个朋友单独聊天，可以放松、贴心一点，记得他之前说过的话。
"""

# 群聊场景补充指令（解决「在群里说话像私聊」的问题）
GROUP_STYLE = """

## 当前场景：QQ 群聊（不是私聊！）
你正在一个多人群里，下面会给你**群里最近的聊天记录**，你能看到每个人在说什么。
请务必遵守：
1. 说话更短：**1~2 句、40 字以内**，像群里随手插一句话，不要长篇大论。
2. 你能看到群里其他人的发言，可以**接着大家的话题聊**、能接梗、能回应@你的人。
3. 用群里大家的名字称呼他们，别用"您"这种客服腔。
4. 不要每条消息都回，也不要在没被叫的时候抢话。
5. 不要像私聊那样一问一答、追着人聊天；群里可以只回一句就走。
6. 绝不刷屏：需要展开的一次说完，不要拆成很多条。
"""


def build_ws_url(ws_url: str, access_token: str) -> str:
    """把 access_token 拼到 URL 上（避免不同 websockets 版本头参数差异）。"""
    if not access_token:
        return ws_url
    sep = "&" if "?" in ws_url else "?"
    return f"{ws_url}{sep}access_token={quote(access_token)}"


class Bot:
    def __init__(self, cfg):
        self.cfg = cfg
        self.llm = LLM(cfg)
        self.memory = MemoryStore(cfg.memory_max_turns, cfg.memory_ttl)
        self.groupctx = GroupContext(cfg.group_context_size, cfg.group_context_ttl)
        self.summarizer = Summarizer(self.llm, cfg.summarize_count, cfg.summarize_max_chars)
        self.ws = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._pending: dict[str, asyncio.Future] = {}
        self._last_summary: dict[str, float] = {}

    # ---------------- 基础收发 ----------------
    async def _call(self, action: str, params: dict) -> None:
        if self.ws is None:
            return
        await self.ws.send(json.dumps({"action": action, "params": params}, ensure_ascii=False))

    async def _request(self, action: str, params: dict, timeout: float = 15.0) -> dict | None:
        """发送一个需要响应的 API 调用（靠 echo 配对），返回响应整体。"""
        if self.ws is None:
            return None
        echo = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[echo] = fut
        try:
            await self.ws.send(
                json.dumps({"action": action, "params": params, "echo": echo}, ensure_ascii=False)
            )
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            log.warning("请求 %s 超时", action)
            return None
        finally:
            self._pending.pop(echo, None)

    async def _fetch_group_history(self, group_id) -> list[dict]:
        """从 NapCat 拉取群历史消息；失败则返回空列表（调用方会回退到内存上下文）。"""
        resp = await self._request(
            "get_group_msg_history",
            {"group_id": group_id, "count": self.cfg.summarize_count},
        )
        if not resp:
            return []
        data = resp.get("data") or {}
        msgs = data.get("messages") or data.get("message") or []
        if not isinstance(msgs, list):
            return []
        try:
            msgs = sorted(msgs, key=lambda m: (m or {}).get("time") or 0)
        except Exception:  # noqa: BLE001
            pass
        return msgs

    async def _do_summary(self, group_id) -> None:
        key = str(group_id)
        now = time.time()
        if now - self._last_summary.get(key, 0.0) < self.cfg.summarize_cooldown:
            await self._reply("group", group_id, "刚总结过啦，歇会儿再总结～", 1)
            return
        self._last_summary[key] = now

        await self._reply("group", group_id, "稍等，我爬一下楼…", 1)

        messages = await self._fetch_group_history(group_id)
        if not messages:
            # 回退：用内存里记录的群上下文
            messages = [
                {
                    "sender": {"nickname": m["name"]},
                    "message": [{"type": "text", "data": {"text": m["content"]}}],
                }
                for m in self.groupctx.get(group_id)
                if m["role"] == "user"
            ]

        try:
            summary = await self.summarizer.summarize(messages)
        except Exception as e:  # noqa: BLE001
            log.exception("群聊总结失败：%s", e)
            await self._reply("group", group_id, "总结的时候出错了，等会儿再试试～", 1)
            return

        if not summary:
            return
        self.groupctx.add(group_id, self.cfg.bot_name, summary, is_bot=True)
        log.info("[summary:%s] %s", group_id, summary.replace("\n", " ")[:60])
        await self._reply("group", group_id, summary, max(3, self.cfg.group_max_split))

    async def _reply(self, message_type: str, target_id: int, text: str, max_split: int) -> None:
        parts = split_text(text, max_split)
        for part in parts:
            delay = min(self.cfg.min_delay + len(part) * self.cfg.delay_per_char, 3.0)
            await asyncio.sleep(delay)  # 模拟“打字中”
            if message_type == "group":
                await self._call("send_group_msg", {"group_id": target_id, "message": part})
            else:
                await self._call("send_private_msg", {"user_id": target_id, "message": part})

    # ---------------- 消息解析 ----------------
    @staticmethod
    def extract_text(message) -> str:
        if isinstance(message, str):
            return message.strip()
        texts = []
        for seg in message or []:
            if isinstance(seg, dict) and seg.get("type") == "text":
                texts.append(str(seg.get("data", {}).get("text", "")))
        return "".join(texts).strip()

    @staticmethod
    def is_at_bot(message, self_id) -> bool:
        for seg in message or []:
            if isinstance(seg, dict) and seg.get("type") == "at":
                if str(seg.get("data", {}).get("qq")) == str(self_id):
                    return True
        return False

    @staticmethod
    def _merge_consecutive(messages: list[dict]) -> list[dict]:
        """合并相邻同角色消息，兼容部分接口对 role 交替的要求。"""
        merged: list[dict] = []
        for m in messages:
            if merged and merged[-1]["role"] == m["role"]:
                merged[-1]["content"] += "\n" + m["content"]
            else:
                merged.append(dict(m))
        return merged

    def _build_messages(self, style: str, history: list[dict], final_user: str) -> list[dict]:
        messages = [{"role": "system", "content": self.llm.persona() + style}]
        messages.extend(self._merge_consecutive(history))
        messages.append({"role": "user", "content": final_user})
        return messages

    # ---------------- 事件处理 ----------------
    async def handle_event(self, event: dict) -> None:
        if event.get("post_type") != "message":
            return

        message_type = event.get("message_type")
        user_id = event.get("user_id")
        group_id = event.get("group_id")
        self_id = event.get("self_id")

        # 忽略机器人自己发的消息，避免自问自答
        if str(user_id) == str(self_id):
            return

        message = event.get("message")
        text = self.extract_text(message)

        if self.cfg.log_all_events:
            log.info(
                "收到事件 type=%s user=%s group=%s text=%r",
                message_type, user_id, group_id, text[:50],
            )

        if not text:
            return

        sender = event.get("sender") or {}
        speaker = str(sender.get("card") or sender.get("nickname") or user_id).strip()

        if message_type == "private":
            if not self.cfg.private_reply:
                return
            if self.cfg.whitelist and str(user_id) not in self.cfg.whitelist:
                return
            session_key = f"private:{user_id}"
            history = self.memory.get(session_key)
            system_extra = PRIVATE_STYLE
            final_user = text
            max_split = self.cfg.max_split
            target_id = user_id

        elif message_type == "group":
            at_bot = self.is_at_bot(message, self_id)
            wake = next((w for w in self.cfg.wake_words if w and w in text), None)
            triggered = (not self.cfg.group_need_at) or at_bot or (wake is not None)

            # 不管要不要回复，都先把这条群消息记进群上下文（这才叫"看得到群里在聊啥"）
            if not triggered:
                self.groupctx.add(group_id, speaker, text, is_bot=False)
                return

            if self.cfg.whitelist and str(user_id) not in self.cfg.whitelist:
                self.groupctx.add(group_id, speaker, text, is_bot=False)
                return

            # 只有「靠唤醒词」触发时才去掉唤醒词；被 @ 时保持原文不动
            if not at_bot and wake:
                stripped = text.replace(wake, "", 1).strip()
                text = stripped or text

            # 取"当前这条之前"的群聊记录作为上下文
            ctx = self.groupctx.get(group_id)
            self.groupctx.add(group_id, speaker, text, is_bot=False)

            # 爬楼总结：@机器人 + 说「总结一下」之类
            if self.cfg.summarize_enabled and any(k in text for k in self.cfg.summarize_keywords):
                await self._do_summary(group_id)
                return

            history = []
            for m in ctx:
                if m["role"] == "assistant":
                    history.append({"role": "assistant", "content": m["content"]})
                else:
                    history.append({"role": "user", "content": f'{m["name"]}：{m["content"]}'})

            session_key = f"group:{group_id}:{user_id}"
            system_extra = GROUP_STYLE
            prefix = f"{speaker}（@了你）" if at_bot else speaker
            final_user = f"{prefix}：{text}"
            max_split = self.cfg.group_max_split
            target_id = group_id

        else:
            return

        lock = self._locks.setdefault(session_key, asyncio.Lock())
        async with lock:
            try:
                answer = await self.llm.complete(
                    self._build_messages(system_extra, history, final_user)
                )
            except Exception as e:  # noqa: BLE001
                log.exception("调用大模型失败：%s", e)
                return
            if not answer:
                return

            if message_type == "private":
                self.memory.add(session_key, "user", text)
                self.memory.add(session_key, "assistant", answer)
            else:
                self.groupctx.add(group_id, self.cfg.bot_name, answer, is_bot=True)

            log.info(
                "[%s] %s -> %s",
                session_key,
                final_user.replace("\n", " ")[:50],
                answer.replace("\n", " ")[:50],
            )
            await self._reply(message_type, target_id, answer, max_split)


async def main() -> None:
    cfg = load_config()
    bot = Bot(cfg)
    url = build_ws_url(cfg.ws_url, cfg.access_token)

    while True:
        try:
            log.info("正在连接 OneBot：%s", cfg.ws_url)
            async with websockets.connect(
                url, ping_interval=30, ping_timeout=30, max_size=2 ** 23
            ) as ws:
                bot.ws = ws
                log.info("连接成功，开始监听消息（Ctrl+C 退出）")
                async for raw in ws:
                    try:
                        data = json.loads(raw)
                    except Exception:  # noqa: BLE001
                        continue
                    # API 响应（带 echo）→ 交给等待它的请求
                    echo = data.get("echo")
                    if echo is not None:
                        fut = bot._pending.get(echo)
                        if fut is not None and not fut.done():
                            fut.set_result(data)
                        continue
                    if data.get("post_type"):
                        asyncio.create_task(bot.handle_event(data))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.warning("连接断开：%s；5 秒后重连", e)
        finally:
            bot.ws = None
            # 断线时唤醒所有在等待的请求，避免一直挂着
            for fut in list(bot._pending.values()):
                if not fut.done():
                    fut.set_result(None)
        await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("已退出")
