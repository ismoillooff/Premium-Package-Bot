"""getStickerSet orqali custom emoji pack'larni yuklash (TTL kesh + bir vaqtdagi so'rovlarni birlashtirish)."""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Protocol

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import Sticker, StickerSet

from app.constants import PACK_CACHE_MAX_SIZE
from app.models.emoji import EmojiItem, EmojiPack
from app.services.cache_service import TTLCache

logger = logging.getLogger(__name__)

_EMOJI_ID_RE = re.compile(r"^\d{1,32}$")
# Telegram set nomi: harf, raqam, pastki chiziq; 1–64 belgi.
_SET_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

_MISSING = object()


class StickerApi(Protocol):
    """aiogram.Bot shu interfeysni qondiradi; testlarda soxta obyekt beriladi."""

    async def get_custom_emoji_stickers(self, custom_emoji_ids: list[str]) -> list[Sticker]: ...

    async def get_sticker_set(self, name: str) -> StickerSet: ...


def is_valid_emoji_id(value: object) -> bool:
    return isinstance(value, str) and bool(_EMOJI_ID_RE.fullmatch(value))


def is_valid_set_name(value: object) -> bool:
    return isinstance(value, str) and bool(_SET_NAME_RE.fullmatch(value))


def sticker_to_item(sticker: Sticker) -> EmojiItem | None:
    """Sticker'ni EmojiItem ga aylantiradi; custom emoji bo'lmasa None."""
    if sticker.type != "custom_emoji" or not is_valid_emoji_id(sticker.custom_emoji_id):
        return None
    if sticker.is_video:
        kind = "video"
    elif sticker.is_animated:
        kind = "animated"
    else:
        kind = "static"
    emoji = sticker.emoji if isinstance(sticker.emoji, str) and sticker.emoji.strip() else None
    set_name = sticker.set_name if is_valid_set_name(sticker.set_name) else None
    return EmojiItem(
        custom_emoji_id=sticker.custom_emoji_id,  # type: ignore[arg-type]
        emoji=emoji,
        set_name=set_name,
        kind=kind,
        needs_repainting=bool(sticker.needs_repainting),
    )


class StickerSetService:
    def __init__(self, api: StickerApi, cache_ttl: float = 600) -> None:
        self._api = api
        self._cache: TTLCache[str, EmojiPack | None] = TTLCache(ttl=cache_ttl, max_size=PACK_CACHE_MAX_SIZE)
        self._inflight: dict[str, asyncio.Future[EmojiPack | None]] = {}

    async def get_pack_safe(self, name: str) -> EmojiPack | None:
        """Tarmoq/API xatosida None qaytaradi (xato logga yoziladi)."""
        try:
            return await self.get_pack(name)
        except TelegramAPIError as exc:
            logger.warning("getStickerSet failed | set=%s | %s", name, exc)
            return None

    async def get_pack(self, name: str) -> EmojiPack | None:
        """Pack'ni keshdan yoki Telegram'dan oladi. Bir vaqtdagi bir xil so'rovlar birlashtiriladi."""
        cached = self._cache.get(name, _MISSING)  # type: ignore[arg-type]
        if cached is not _MISSING:
            return cached  # type: ignore[return-value]

        future = self._inflight.get(name)
        if future is None:
            future = asyncio.ensure_future(self._fetch(name))
            self._inflight[name] = future
            future.add_done_callback(lambda _f: self._inflight.pop(name, None))
        # shield: bitta foydalanuvchi so'rovi bekor qilinsa, umumiy so'rov to'xtamasin.
        return await asyncio.shield(future)

    async def _fetch(self, name: str) -> EmojiPack | None:
        try:
            sticker_set = await self._api.get_sticker_set(name=name)
        except TelegramBadRequest as exc:
            # Set o'chirilgan / topilmadi — kesh muddati davomida qayta so'ramaymiz.
            logger.warning("Sticker set not available | set=%s | %s", name, exc.message)
            self._cache.set(name, None)
            return None

        items: dict[str, EmojiItem] = {}
        for sticker in sticker_set.stickers or ():
            item = sticker_to_item(sticker)
            if item is not None:
                items.setdefault(item.custom_emoji_id, item)

        if sticker_set.sticker_type != "custom_emoji" or not items:
            logger.warning(
                "Not a usable custom emoji set | set=%s | type=%s | emojis=%d",
                name,
                sticker_set.sticker_type,
                len(items),
            )
            self._cache.set(name, None)
            return None

        title = sticker_set.title if isinstance(sticker_set.title, str) and sticker_set.title.strip() else name
        pack = EmojiPack(name=name, title=title, items=tuple(items.values()))
        self._cache.set(name, pack)
        logger.info("Custom emoji set loaded | set=%s | emojis=%d", name, pack.total)
        return pack
