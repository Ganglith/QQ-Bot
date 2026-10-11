"""按用户维护短期对话记忆（内存版，重启即清空）。"""
from __future__ import annotations

import time
from collections import deque


class MemoryStore:
    def __init__(self, max_turns: int, ttl_seconds: int):
        self.max_messages = max(int(max_turns), 1) * 2  # 一问一答算 2 条
        self.ttl = int(ttl_seconds)
        self._data: dict[str, dict] = {}

    def _expired(self, item: dict) -> bool:
        return self.ttl > 0 and (time.time() - item["ts"] > self.ttl)

    def get(self, key: str) -> list[dict]:
        item = self._data.get(key)
        if not item:
            return []
        if self._expired(item):
            self._data.pop(key, None)
            return []
        return list(item["messages"])

    def add(self, key: str, role: str, content: str) -> None:
        item = self._data.get(key)
        if item and not self._expired(item):
            msgs: deque = item["messages"]
        else:
            msgs = deque()
        msgs.append({"role": role, "content": content})
        while len(msgs) > self.max_messages:
            msgs.popleft()
        self._data[key] = {"messages": msgs, "ts": time.time()}
