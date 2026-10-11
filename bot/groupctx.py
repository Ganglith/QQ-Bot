"""群聊上下文：记录一个群里最近的所有发言（含机器人自己的），
让机器人在群里"看得见大家在聊什么"，而不是只记得跟某一个人的对话。
"""
from __future__ import annotations

import time
from collections import deque


class GroupContext:
    def __init__(self, size: int = 30, ttl_seconds: int = 1800):
        self.size = max(int(size), 2)
        self.ttl = int(ttl_seconds)
        self._data: dict[str, dict] = {}

    def _expired(self, item: dict) -> bool:
        return self.ttl > 0 and (time.time() - item["ts"] > self.ttl)

    def add(self, group_id, name: str, content: str, is_bot: bool = False) -> None:
        key = str(group_id)
        item = self._data.get(key)
        if item and not self._expired(item):
            msgs = deque(item["messages"], maxlen=self.size)
        else:
            msgs = deque(maxlen=self.size)
        msgs.append({
            "role": "assistant" if is_bot else "user",
            "name": name,
            "content": content,
        })
        self._data[key] = {"messages": msgs, "ts": time.time()}

    def get(self, group_id) -> list[dict]:
        key = str(group_id)
        item = self._data.get(key)
        if not item:
            return []
        if self._expired(item):
            self._data.pop(key, None)
            return []
        return list(item["messages"])
