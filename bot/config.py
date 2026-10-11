"""加载配置：config.yaml + persona.md + .env"""
from __future__ import annotations

import os
from dataclasses import dataclass

import yaml
from dotenv import load_dotenv

# 项目根目录（本文件在 bot/ 下）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Config:
    # OneBot
    ws_url: str
    access_token: str
    # LLM
    api_key: str
    base_url: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt: str
    persona_path: str
    # 行为
    private_reply: bool
    group_need_at: bool
    wake_words: list
    whitelist: list
    max_split: int
    min_delay: float
    delay_per_char: float
    # 群聊
    group_context_size: int
    group_context_ttl: int
    group_max_split: int
    bot_name: str
    log_all_events: bool
    # 爬楼总结
    summarize_enabled: bool
    summarize_keywords: list
    summarize_count: int
    summarize_max_chars: int
    summarize_cooldown: int
    # 记忆
    memory_max_turns: int
    memory_ttl: int


def load_config(config_path: str | None = None, persona_path: str | None = None) -> Config:
    load_dotenv(os.path.join(BASE_DIR, ".env"))

    config_path = config_path or os.path.join(BASE_DIR, "config.yaml")
    persona_path = persona_path or os.path.join(BASE_DIR, "persona.md")

    with open(config_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    onebot = raw.get("onebot", {}) or {}
    llm = raw.get("llm", {}) or {}
    behavior = raw.get("behavior", {}) or {}
    memory = raw.get("memory", {}) or {}
    summarize = raw.get("summarize", {}) or {}

    system_prompt = ""
    if os.path.exists(persona_path):
        with open(persona_path, encoding="utf-8") as f:
            system_prompt = f.read().strip()
    if not system_prompt:
        system_prompt = "你是一个友好的聊天助手，说话口语化、简短，不要暴露自己是 AI。"

    api_key = os.getenv("DEEPSEEK_API_KEY") or llm.get("api_key", "")
    if not api_key:
        raise SystemExit(
            "缺少 DeepSeek API Key。请把 .env.example 复制为 .env，"
            "并填入 DEEPSEEK_API_KEY=sk-xxxx 后重试。"
        )

    access_token = os.getenv("ONEBOT_ACCESS_TOKEN") or onebot.get("access_token", "")

    return Config(
        ws_url=str(onebot.get("ws_url", "ws://127.0.0.1:3001")),
        access_token=str(access_token or ""),
        api_key=str(api_key),
        base_url=str(llm.get("base_url", "https://api.deepseek.com")),
        model=str(llm.get("model", "deepseek-chat")),
        temperature=float(llm.get("temperature", 1.1)),
        max_tokens=int(llm.get("max_tokens", 800)),
        system_prompt=system_prompt,
        persona_path=persona_path,
        private_reply=bool(behavior.get("private_reply", True)),
        group_need_at=bool(behavior.get("group_need_at", True)),
        wake_words=list(behavior.get("wake_words") or []),
        whitelist=[str(x) for x in (behavior.get("whitelist") or [])],
        max_split=int(behavior.get("max_split", 3)),
        min_delay=float(behavior.get("min_delay", 0.5)),
        delay_per_char=float(behavior.get("delay_per_char", 0.03)),
        group_context_size=int(behavior.get("group_context_size", 30)),
        group_context_ttl=int(behavior.get("group_context_ttl", 1800)),
        group_max_split=int(behavior.get("group_max_split", 2)),
        bot_name=str(behavior.get("bot_name", "机器人")),
        log_all_events=bool(behavior.get("log_all_events", False)),
        summarize_enabled=bool(summarize.get("enabled", True)),
        summarize_keywords=list(summarize.get("keywords") or ["总结一下", "总结", "爬楼", "复盘", "简报"]),
        summarize_count=int(summarize.get("count", 200)),
        summarize_max_chars=int(summarize.get("max_chars", 6000)),
        summarize_cooldown=int(summarize.get("cooldown", 30)),
        memory_max_turns=int(memory.get("max_turns", 12)),
        memory_ttl=int(memory.get("ttl_seconds", 1800)),
    )
