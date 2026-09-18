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
    cache_ttl: int = 600
    admin_id: int | None = None

    def __repr__(self) -> str:  # token hech qachon repr/log orqali chiqmasin
        return f"Settings(bot_token='***', log_level={self.log_level!r}, cache_ttl={self.cache_ttl}, admin_id={self.admin_id})"


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
        # SET_CACHE_TTL — eski nom, moslik uchun qo'llanadi.
        ttl = int(os.getenv("CACHE_TTL_SECONDS") or os.getenv("SET_CACHE_TTL") or "600")
    except ValueError:
        raise ConfigError("CACHE_TTL_SECONDS butun son bo'lishi kerak") from None
    if ttl < 0:
        raise ConfigError("CACHE_TTL_SECONDS manfiy bo'lishi mumkin emas")

    admin_raw = os.getenv("ADMIN_ID", "").strip()
    if admin_raw and not admin_raw.isdigit():
        raise ConfigError("ADMIN_ID musbat butun son bo'lishi kerak")

    return Settings(
        bot_token=token, log_level=log_level, cache_ttl=ttl, admin_id=int(admin_raw) if admin_raw else None
    )
