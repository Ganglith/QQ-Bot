"""调用 DeepSeek（OpenAI 兼容接口），并支持人设文件热更新。"""
from __future__ import annotations

import logging
import os

from openai import AsyncOpenAI

log = logging.getLogger("qqbot.llm")


class LLM:
    def __init__(self, cfg):
        self.client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
        self.model = cfg.model
        self.temperature = cfg.temperature
        self.max_tokens = cfg.max_tokens

        self.persona_path = getattr(cfg, "persona_path", None)
        self._fallback_prompt = getattr(cfg, "system_prompt", "") or ""
        self._prompt = self._fallback_prompt
        self._mtime: float | None = None
        self._load_persona(initial=True)

    # ---------------- 人设（热更新） ----------------
    def _load_persona(self, initial: bool = False) -> None:
        """persona.md 一改动就自动重载，无需重启服务。"""
        if not self.persona_path or not os.path.exists(self.persona_path):
            if initial:
                self._prompt = self._fallback_prompt
            return
        try:
            mtime = os.path.getmtime(self.persona_path)
        except OSError:
            return
        if mtime == self._mtime and not initial:
            return
        try:
            with open(self.persona_path, encoding="utf-8") as f:
                content = f.read().strip()
        except OSError as e:
            log.warning("读取人设文件失败：%s", e)
            return
        self._mtime = mtime
        if content:
            self._prompt = content
            log.info("人设已%s", "加载" if initial else "热更新")

    def persona(self) -> str:
        """每次取用时检查一次，改完人设立即生效。"""
        self._load_persona()
        return self._prompt

    # ---------------- 调用 ----------------
    async def complete(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature if temperature is None else temperature,
            max_tokens=self.max_tokens if max_tokens is None else max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
