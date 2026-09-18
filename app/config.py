"""Loyiha sozlamalari (.env dan o'qiladi)."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from dotenv import load_dotenv

_TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


class ConfigError(RuntimeError):
    """Sozlamalar noto'g'ri yoki yetishmayapti."""


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    log_level: str = "INFO"
    set_cache_ttl: int = 600

    def __repr__(self) -> str:  # token hech qachon repr/log orqali chiqmasin
        return f"Settings(bot_token='***', log_level={self.log_level!r}, set_cache_ttl={self.set_cache_ttl})"


def load_settings() -> Settings:
    load_dotenv()

    token = os.getenv("BOT_TOKEN", "").strip()
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN":
        raise ConfigError("BOT_TOKEN .env faylida ko'rsatilmagan")
    if not _TOKEN_RE.fullmatch(token):
        raise ConfigError("BOT_TOKEN formati noto'g'ri")

    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    if log_level not in _LOG_LEVELS:
        log_level = "INFO"

    try:
        ttl = int(os.getenv("SET_CACHE_TTL", "600"))
    except ValueError:
        raise ConfigError("SET_CACHE_TTL butun son bo'lishi kerak") from None
    if ttl < 0:
        raise ConfigError("SET_CACHE_TTL manfiy bo'lishi mumkin emas")

    return Settings(bot_token=token, log_level=log_level, set_cache_ttl=ttl)
