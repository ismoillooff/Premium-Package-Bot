"""Custom emoji va ularning setlari haqida ma'lumot olish.

Oqim: entity -> custom_emoji_id -> getCustomEmojiStickers -> set_name -> getStickerSet.
Telegram javoblari tekshirib olinadi; hech qanday ma'lumot taxmin qilinmaydi.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import MessageEntity, Sticker, StickerSet

from app.utils.cache import TTLCache

logger = logging.getLogger(__name__)

# getCustomEmojiStickers bir so'rovda ko'pi bilan 200 ta ID qabul qiladi.
MAX_IDS_PER_REQUEST = 200
# Bitta xabar uchun yuklanadigan setlar soni (spam va flood'dan himoya).
MAX_SETS_PER_MESSAGE = 10

_EMOJI_ID_RE = re.compile(r"^\d{1,32}$")
# Telegram set nomi: harf, raqam, pastki chiziq; 1–64 belgi.
_SET_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

_NOT_FOUND = object()


class EmojiLookupError(Exception):
    """Telegram'dan emoji ma'lumotini olib bo'lmadi."""


class StickerApi(Protocol):
    """aiogram.Bot shu interfeysni qondiradi; testlarda soxta obyekt beriladi."""

    async def get_custom_emoji_stickers(self, custom_emoji_ids: list[str]) -> list[Sticker]: ...

    async def get_sticker_set(self, name: str) -> StickerSet: ...


@dataclass(frozen=True, slots=True)
class EmojiInfo:
    custom_emoji_id: str
    emoji: str | None = None
    set_name: str | None = None
    kind: str = "static"  # static | animated | video
    needs_repainting: bool = False


@dataclass(frozen=True, slots=True)
class EmojiPack:
    name: str
    title: str
    emojis: tuple[EmojiInfo, ...]


@dataclass(slots=True)
class LookupResult:
    requested: list[EmojiInfo] = field(default_factory=list)
    """Foydalanuvchi yuborgan va Telegram tasdiqlagan emoji'lar (yuborilgan tartibda)."""
    missing_ids: list[str] = field(default_factory=list)
    """Telegram hech qanday ma'lumot bermagan ID'lar."""
    packs: list[EmojiPack] = field(default_factory=list)
    orphans: list[EmojiInfo] = field(default_factory=list)
    """Seti aniqlanmagan yoki yuklanmagan emoji'lar."""
    failed_sets: list[str] = field(default_factory=list)
    skipped_sets: list[str] = field(default_factory=list)

    @property
    def all_ids(self) -> list[str]:
        """Natijadagi barcha unikal ID'lar (packlar + setsiz emoji'lar)."""
        seen: dict[str, None] = {}
        for pack in self.packs:
            for item in pack.emojis:
                seen.setdefault(item.custom_emoji_id, None)
        for item in self.orphans:
            seen.setdefault(item.custom_emoji_id, None)
        return list(seen)


def is_valid_emoji_id(value: object) -> bool:
    return isinstance(value, str) and bool(_EMOJI_ID_RE.fullmatch(value))


def is_valid_set_name(value: object) -> bool:
    return isinstance(value, str) and bool(_SET_NAME_RE.fullmatch(value))


def extract_custom_emoji_ids(entities: Iterable[MessageEntity] | None) -> list[str]:
    """Entity'lardan unikal custom_emoji_id larni yuborilgan tartibda qaytaradi.

    ID entity obyektining o'zida bo'ladi, shuning uchun matnni UTF-16 offset
    bo'yicha kesish shart emas (offset xatolari xavfi yo'q).
    """
    result: dict[str, None] = {}
    for entity in entities or ():
        if entity.type != "custom_emoji":
            continue
        emoji_id = entity.custom_emoji_id
        if is_valid_emoji_id(emoji_id):
            result.setdefault(emoji_id, None)  # type: ignore[arg-type]
    return list(result)


def sticker_to_info(sticker: Sticker) -> EmojiInfo | None:
    """Sticker'ni EmojiInfo ga aylantiradi; custom emoji bo'lmasa None."""
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
    return EmojiInfo(
        custom_emoji_id=sticker.custom_emoji_id,  # type: ignore[arg-type]
        emoji=emoji,
        set_name=set_name,
        kind=kind,
        needs_repainting=bool(sticker.needs_repainting),
    )


class EmojiService:
    def __init__(self, api: StickerApi, set_cache_ttl: float = 600) -> None:
        self._api = api
        self._sets: TTLCache[str, object] = TTLCache(ttl=set_cache_ttl, max_size=512)
        self._inflight: dict[str, asyncio.Future[EmojiPack | None]] = {}

    async def lookup(self, emoji_ids: Sequence[str]) -> LookupResult:
        ids = [i for i in dict.fromkeys(emoji_ids) if is_valid_emoji_id(i)][:MAX_IDS_PER_REQUEST]
        result = LookupResult()
        if not ids:
            return result

        try:
            stickers = await self._api.get_custom_emoji_stickers(custom_emoji_ids=ids)
        except TelegramAPIError as exc:
            logger.error("getCustomEmojiStickers failed: %s", exc)
            raise EmojiLookupError from exc

        wanted = set(ids)
        by_id: dict[str, EmojiInfo] = {}
        for sticker in stickers or ():
            info = sticker_to_info(sticker)
            # Biz so'ramagan ID javobda kelsa — ishonmaymiz.
            if info is not None and info.custom_emoji_id in wanted:
                by_id.setdefault(info.custom_emoji_id, info)

        result.requested = [by_id[i] for i in ids if i in by_id]
        result.missing_ids = [i for i in ids if i not in by_id]

        set_names = list(dict.fromkeys(i.set_name for i in result.requested if i.set_name))
        to_load = set_names[:MAX_SETS_PER_MESSAGE]
        result.skipped_sets = set_names[MAX_SETS_PER_MESSAGE:]

        # Har bir set faqat bir marta, parallel so'raladi.
        packs = await asyncio.gather(*(self._get_pack_safe(name) for name in to_load))
        loaded: dict[str, EmojiPack] = {}
        for name, pack in zip(to_load, packs):
            if pack is None:
                result.failed_sets.append(name)
            else:
                loaded[name] = pack
                result.packs.append(pack)

        for info in result.requested:
            pack = loaded.get(info.set_name or "")
            if pack is None or not any(e.custom_emoji_id == info.custom_emoji_id for e in pack.emojis):
                result.orphans.append(info)

        return result

    async def _get_pack_safe(self, name: str) -> EmojiPack | None:
        try:
            return await self.get_pack(name)
        except TelegramAPIError as exc:
            logger.warning("getStickerSet failed for %s: %s", name, exc)
            return None

    async def get_pack(self, name: str) -> EmojiPack | None:
        """Set'ni keshdan yoki Telegram'dan oladi. Bir vaqtdagi bir xil so'rovlar birlashtiriladi."""
        cached = self._sets.get(name, _NOT_FOUND)
        if cached is not _NOT_FOUND:
            return cached  # type: ignore[return-value]

        future = self._inflight.get(name)
        if future is None:
            future = asyncio.ensure_future(self._fetch_pack(name))
            self._inflight[name] = future
            future.add_done_callback(lambda _f: self._inflight.pop(name, None))
        # shield: bitta foydalanuvchi so'rovi bekor qilinsa, umumiy so'rov to'xtamasin.
        return await asyncio.shield(future)

    async def _fetch_pack(self, name: str) -> EmojiPack | None:
        try:
            sticker_set = await self._api.get_sticker_set(name=name)
        except TelegramBadRequest as exc:
            # Set o'chirilgan / topilmadi — qisqa muddat qayta so'ramaymiz.
            logger.warning("Sticker set %s not available: %s", name, exc.message)
            self._sets.set(name, None)
            return None

        emojis: dict[str, EmojiInfo] = {}
        for sticker in sticker_set.stickers or ():
            info = sticker_to_info(sticker)
            if info is not None:
                emojis.setdefault(info.custom_emoji_id, info)

        if sticker_set.sticker_type != "custom_emoji" or not emojis:
            logger.warning(
                "Set %s is not a custom emoji set (type=%s, emojis=%d)",
                name,
                sticker_set.sticker_type,
                len(emojis),
            )
            self._sets.set(name, None)
            return None

        title = sticker_set.title if isinstance(sticker_set.title, str) and sticker_set.title.strip() else name
        pack = EmojiPack(name=name, title=title, emojis=tuple(emojis.values()))
        self._sets.set(name, pack)
        logger.info("Custom emoji set loaded: %s (%d emojis)", name, len(pack.emojis))
        return pack
