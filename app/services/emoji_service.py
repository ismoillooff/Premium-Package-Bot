"""Custom emoji'larni aniqlash va ularning pack'larini topish.

Oqim: entity -> custom_emoji_id -> getCustomEmojiStickers -> set_name -> getStickerSet.
Telegram javoblari tekshirib olinadi; hech qanday ma'lumot taxmin qilinmaydi.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Sequence

from aiogram.exceptions import TelegramAPIError
from aiogram.types import MessageEntity

from app.constants import MAX_SETS_PER_MESSAGE
from app.models.emoji import EmojiItem, EmojiPack, LookupResult
from app.services.sticker_set_service import (
    StickerApi,
    StickerSetService,
    is_valid_emoji_id,
    sticker_to_item,
)
from app.utils.telegram_limits import CUSTOM_EMOJI_IDS_PER_REQUEST

logger = logging.getLogger(__name__)

VIRTUAL_PACK_TITLE = "Yuborilgan emoji'lar"


class EmojiLookupError(Exception):
    """Telegram'dan emoji ma'lumotini olib bo'lmadi."""


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


def browsable_packs(result: LookupResult) -> list[EmojiPack]:
    """Explorer'da ko'rsatiladigan pack'lar: haqiqiy setlar + setsiz emoji'lar guruhi."""
    packs = list(result.packs)
    if result.orphans:
        packs.append(EmojiPack(name="", title=VIRTUAL_PACK_TITLE, items=tuple(result.orphans), is_virtual=True))
    return packs


class EmojiService:
    def __init__(self, api: StickerApi, sets: StickerSetService) -> None:
        self._api = api
        self._sets = sets

    async def lookup(self, emoji_ids: Sequence[str]) -> LookupResult:
        ids = [i for i in dict.fromkeys(emoji_ids) if is_valid_emoji_id(i)][:CUSTOM_EMOJI_IDS_PER_REQUEST]
        result = LookupResult()
        if not ids:
            return result

        try:
            stickers = await self._api.get_custom_emoji_stickers(custom_emoji_ids=ids)
        except TelegramAPIError as exc:
            logger.error("getCustomEmojiStickers failed: %s", exc)
            raise EmojiLookupError from exc

        wanted = set(ids)
        by_id: dict[str, EmojiItem] = {}
        for sticker in stickers or ():
            item = sticker_to_item(sticker)
            # Biz so'ramagan ID javobda kelsa — ishonmaymiz.
            if item is not None and item.custom_emoji_id in wanted:
                by_id.setdefault(item.custom_emoji_id, item)

        result.requested = [by_id[i] for i in ids if i in by_id]
        result.missing_ids = [i for i in ids if i not in by_id]

        set_names = list(dict.fromkeys(i.set_name for i in result.requested if i.set_name))
        to_load = set_names[:MAX_SETS_PER_MESSAGE]
        result.skipped_sets = set_names[MAX_SETS_PER_MESSAGE:]

        # Har bir set faqat bir marta, parallel so'raladi.
        packs = await asyncio.gather(*(self._sets.get_pack_safe(name) for name in to_load))
        loaded: dict[str, EmojiPack] = {}
        for name, pack in zip(to_load, packs):
            if pack is None:
                result.failed_sets.append(name)
            else:
                loaded[name] = pack
                result.packs.append(pack)

        for item in result.requested:
            pack = loaded.get(item.set_name or "")
            if pack is None or not any(e.custom_emoji_id == item.custom_emoji_id for e in pack.items):
                result.orphans.append(item)

        return result
