"""Bot UI uchun Premium / Custom Emoji registry'si — yagona manba.

Qoida: UI'da oddiy Unicode emoji ishlatilmaydi.
  * ID sozlangan va Telegram ruxsat bersa -> premium custom emoji;
  * aks holda -> faqat matn (Unicode emoji fallback YO'Q).

ID'larni o'rnatish: quyidagi PREMIUM_EMOJIS ni to'ldiring yoki .env da
EMOJI_<ROLE>_ID=... (masalan EMOJI_COPY_ID=5368...) bering. .env ustun turadi.
ID'larni botning o'zidan olish mumkin: botga emoji yuboring va ID'ni nusxalang.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Mapping
from enum import StrEnum

from aiogram.exceptions import TelegramAPIError

from app.constants import CAPABILITY_RETRY_SECONDS
from app.services.sticker_set_service import StickerApi, sticker_to_item

logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^\d{1,32}$")


class PremiumEmoji(StrEnum):
    HOME = "home"
    PACK = "pack"
    VIEW = "view"
    LIST = "list"
    LIST_CREATE = "list_create"
    COPY = "copy"
    FILE = "file"
    BACK = "back"
    TABLE = "table"
    NEXT = "next"
    PREVIOUS = "previous"
    PAGE = "page"
    CODE = "code"
    PREVIEW = "preview"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    PHP = "php"
    JAVA = "java"
    GO = "go"
    CURL = "curl"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    REFRESH = "refresh"
    SETTINGS = "settings"
    LOADING = "loading"
    ADMIN = "admin"


REQUIRED_ROLES: frozenset[PremiumEmoji] = frozenset(
    {
        PremiumEmoji.PACK,
        PremiumEmoji.VIEW,
        PremiumEmoji.COPY,
        PremiumEmoji.BACK,
        PremiumEmoji.NEXT,
        PremiumEmoji.PREVIOUS,
        PremiumEmoji.CODE,
        PremiumEmoji.PYTHON,
        PremiumEmoji.JAVASCRIPT,
        PremiumEmoji.TYPESCRIPT,
        PremiumEmoji.PHP,
        PremiumEmoji.JAVA,
        PremiumEmoji.CURL,
        PremiumEmoji.SUCCESS,
        PremiumEmoji.ERROR,
        PremiumEmoji.WARNING,
        PremiumEmoji.INFO,
    }
)

# --- Faqat shu lug'atni tahrirlang. Soxta ID yozmang: bo'sh qolsa, UI faqat matn bilan ishlaydi. ---
PREMIUM_EMOJIS: dict[PremiumEmoji, str] = {
    PremiumEmoji.HOME: "",
    PremiumEmoji.PACK: "",
    PremiumEmoji.VIEW: "",
    PremiumEmoji.LIST_CREATE: "6041919344995209164",  # "Ro'yxat yaratish"
    PremiumEmoji.LIST: "5766994197705921104",  # "Packlar ro'yxati"
    PremiumEmoji.COPY: "6034969813032374911",  # barcha nusxalash tugmalari
    PremiumEmoji.FILE: "5766994197705921104",  # "Kodni fayl sifatida olish"
    PremiumEmoji.BACK: "",
    PremiumEmoji.TABLE: "6037475557082403885",  # "Jadvalga qaytish"
    PremiumEmoji.NEXT: "6037622221625626773",
    PremiumEmoji.PREVIOUS: "6039539366177541657",
    PremiumEmoji.PAGE: "5767244474040192942",  # sahifa ko'rsatkichi "2 / 5"
    PremiumEmoji.CODE: "",
    PremiumEmoji.PREVIEW: "6037397706505195857",  # "Button Preview"
    PremiumEmoji.PYTHON: "5300928913956938544",
    PremiumEmoji.JAVASCRIPT: "5300896259320586992",
    PremiumEmoji.TYPESCRIPT: "5300896259320586992",  # JavaScript bilan bir xil (foydalanuvchi tanlovi)
    PremiumEmoji.PHP: "5303045701473671851",
    PremiumEmoji.JAVA: "5301179216061015693",
    PremiumEmoji.GO: "5300888829027165969",
    PremiumEmoji.CURL: "5300884628549149586",
    PremiumEmoji.SUCCESS: "",
    PremiumEmoji.ERROR: "",
    PremiumEmoji.WARNING: "",
    PremiumEmoji.INFO: "",
    PremiumEmoji.REFRESH: "",
    PremiumEmoji.SETTINGS: "",
    PremiumEmoji.LOADING: "",
    PremiumEmoji.ADMIN: "5368424251999134211",  # "Admin"
}


def env_var_name(role: PremiumEmoji) -> str:
    return f"EMOJI_{role.name}_ID"


class Capability:
    """Telegram rad etgan imkoniyatni vaqtincha o'chiradi va keyinroq qayta sinaydi."""

    def __init__(self, name: str, retry_after: float = CAPABILITY_RETRY_SECONDS) -> None:
        self.name = name
        self._retry_after = retry_after
        self._disabled_until = 0.0

    @property
    def supported(self) -> bool:
        return time.monotonic() >= self._disabled_until

    def disable(self, reason: str) -> None:
        if self.supported:
            logger.warning("Premium capability disabled | %s | %s", self.name, reason)
        self._disabled_until = time.monotonic() + self._retry_after


class PremiumEmojiRegistry:
    def __init__(self, ids: Mapping[PremiumEmoji, str] | None = None) -> None:
        self._ids: dict[PremiumEmoji, str] = {}
        self._fallbacks: dict[PremiumEmoji, str] = {}
        self.text = Capability("text custom emoji (tg-emoji)")
        self.icons = Capability("button icon_custom_emoji_id")
        self.rich = Capability("rich message table")
        for role, value in (ids or {}).items():
            self._set_if_valid(role, value)

    @classmethod
    def from_sources(cls, defaults: Mapping[PremiumEmoji, str] = PREMIUM_EMOJIS) -> PremiumEmojiRegistry:
        """PREMIUM_EMOJIS + .env (EMOJI_<ROLE>_ID) — .env ustun."""
        merged: dict[PremiumEmoji, str] = {}
        for role in PremiumEmoji:
            value = os.getenv(env_var_name(role), "").strip() or defaults.get(role, "").strip()
            merged[role] = value
        registry = cls(merged)
        registry.log_problems()
        return registry

    def _set_if_valid(self, role: PremiumEmoji, value: str) -> None:
        value = (value or "").strip()
        if not value:
            return
        if not _ID_RE.fullmatch(value):
            logger.warning("Premium emoji ID for %s is not numeric — ignored", role.name)
            return
        self._ids[role] = value

    def problems(self) -> list[str]:
        issues = [
            f"Premium emoji ID for {role.name} is not configured"
            for role in sorted(REQUIRED_ROLES, key=lambda r: r.name)
            if role not in self._ids
        ]
        seen: dict[str, PremiumEmoji] = {}
        for role, value in self._ids.items():
            if value in seen:
                issues.append(f"Premium emoji ID for {role.name} duplicates {seen[value].name}")
            seen.setdefault(value, role)
        return issues

    def log_problems(self) -> None:
        issues = self.problems()
        missing = sum("not configured" in i for i in issues)
        for issue in issues:
            logger.debug(issue)
        if missing:
            logger.warning(
                "%d required premium emoji IDs are not configured — UI uses clean text for them "
                "(set EMOJI_<ROLE>_ID in .env or app/premium_emojis.py)",
                missing,
            )

    async def verify(self, api: StickerApi) -> None:
        """Sozlangan ID'larni Telegram orqali tekshiradi va tg-emoji uchun zarur alternativ belgini oladi.

        Telegram tanimagan ID'lar o'chiriladi (UI'da matn qoladi).
        """
        ids = sorted(set(self._ids.values()))
        if not ids:
            return
        try:
            stickers = await api.get_custom_emoji_stickers(custom_emoji_ids=ids)
        except TelegramAPIError as exc:
            logger.warning("Premium emoji registry verification failed: %s", exc)
            return
        known: dict[str, str] = {}
        for sticker in stickers or ():
            item = sticker_to_item(sticker)
            if item is not None and item.emoji:
                known[item.custom_emoji_id] = item.emoji
        for role, value in list(self._ids.items()):
            if value in known:
                self._fallbacks[role] = known[value]
            else:
                logger.warning("Premium emoji ID for %s is unknown to Telegram — disabled", role.name)
                del self._ids[role]
        logger.info("Premium emoji registry verified | configured=%d", len(self._ids))

    def assign(self, role: PremiumEmoji, emoji_id: str, alternative: str | None = None) -> None:
        """Runtime'da rol'ga emoji biriktirish (kelajakdagi /set_ui_pack uchun)."""
        self._set_if_valid(role, emoji_id)
        if alternative and role in self._ids:
            self._fallbacks[role] = alternative

    def get(self, role: PremiumEmoji) -> str | None:
        return self._ids.get(role)

    def button_icon(self, role: PremiumEmoji | None) -> str | None:
        """Tugma uchun icon_custom_emoji_id (yoki None — tugma faqat matn bilan)."""
        if role is None or not self.icons.supported:
            return None
        return self._ids.get(role)

    def text_icon(self, role: PremiumEmoji) -> tuple[str, str] | None:
        """Matn ichidagi custom emoji uchun (id, alternativ belgi) yoki None.

        Alternativ belgi Telegram entity'si uchun majburiy; u Telegram'dan olinadi.
        Belgi noma'lum bo'lsa, ikonka umuman chiqarilmaydi (Unicode fallback yo'q).
        """
        if not self.text.supported:
            return None
        emoji_id = self._ids.get(role)
        fallback = self._fallbacks.get(role)
        if emoji_id and fallback:
            return emoji_id, fallback
        return None
