from __future__ import annotations

import asyncio

from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import GetCustomEmojiStickers, GetStickerSet
from aiogram.types import MessageEntity, Sticker, StickerSet


def make_sticker(
    emoji_id: str | None,
    emoji: str | None = "🔥",
    set_name: str | None = "PackA",
    type_: str = "custom_emoji",
    animated: bool = False,
    video: bool = False,
) -> Sticker:
    return Sticker(
        file_id=f"file_{emoji_id}",
        file_unique_id=f"uniq_{emoji_id}",
        type=type_,
        width=100,
        height=100,
        is_animated=animated,
        is_video=video,
        emoji=emoji,
        set_name=set_name,
        custom_emoji_id=emoji_id,
    )


def make_set(name: str, ids: list[str], title: str | None = None, sticker_type: str = "custom_emoji") -> StickerSet:
    return StickerSet(
        name=name,
        title=title or f"{name} title",
        sticker_type=sticker_type,
        stickers=[make_sticker(i, set_name=name) for i in ids],
    )


def ce(emoji_id: str, offset: int = 0, length: int = 2) -> MessageEntity:
    return MessageEntity(type="custom_emoji", offset=offset, length=length, custom_emoji_id=emoji_id)


class FakeApi:
    """getCustomEmojiStickers / getStickerSet ning soxta implementatsiyasi."""

    def __init__(
        self,
        stickers: dict[str, Sticker] | None = None,
        sets: dict[str, StickerSet] | None = None,
        fail_lookup: bool = False,
        fail_sets: set[str] | None = None,
        delay: float = 0,
    ) -> None:
        self.stickers = stickers or {}
        self.sets = sets or {}
        self.fail_lookup = fail_lookup
        self.fail_sets = fail_sets or set()
        self.delay = delay
        self.lookup_calls: list[list[str]] = []
        self.set_calls: list[str] = []

    async def get_custom_emoji_stickers(self, custom_emoji_ids: list[str]) -> list[Sticker]:
        self.lookup_calls.append(list(custom_emoji_ids))
        if self.fail_lookup:
            raise TelegramNetworkError(GetCustomEmojiStickers(custom_emoji_ids=custom_emoji_ids), "boom")
        return [self.stickers[i] for i in custom_emoji_ids if i in self.stickers]

    async def get_sticker_set(self, name: str) -> StickerSet:
        self.set_calls.append(name)
        if self.delay:
            await asyncio.sleep(self.delay)
        if name in self.fail_sets or name not in self.sets:
            raise TelegramBadRequest(GetStickerSet(name=name), "Bad Request: STICKERSET_INVALID")
        return self.sets[name]
