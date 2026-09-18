from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import (
    AnswerCallbackQuery,
    DeleteMessage,
    EditMessageText,
    GetCustomEmojiStickers,
    GetStickerSet,
    SendChatAction,
    SendDocument,
    SendMessage,
    SendRichMessage,
    TelegramMethod,
)
from aiogram.types import (
    CallbackQuery,
    Chat,
    Document,
    InlineKeyboardMarkup,
    Message,
    MessageEntity,
    Sticker,
    StickerSet,
    Update,
    User,
)

from app.config import Settings
from app.bot import create_dispatcher
from app.premium_emojis import PremiumEmojiRegistry

USER_ID = 7001
OTHER_USER_ID = 7002
CHAT_ID = 7001
BASE_ID = 5368324170671200000


def eid(n: int) -> str:
    return str(BASE_ID + n)


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


@dataclass
class Stored:
    text: str | None
    rich: Any
    markup: InlineKeyboardMarkup | None
    document: Any = None


@dataclass
class FakeTelegram:
    """Soxta Telegram server holati va xatti-harakati."""

    stickers: dict[str, Sticker] = field(default_factory=dict)
    sets: dict[str, StickerSet] = field(default_factory=dict)
    fail_lookup: bool = False
    reject_rich: bool = False
    reject_icons: bool = False
    drop_icons: bool = False
    drop_custom_emoji: bool = False
    deleted: set[int] = field(default_factory=set)
    messages: dict[int, Stored] = field(default_factory=dict)
    calls: list[TelegramMethod] = field(default_factory=list)
    set_calls: list[str] = field(default_factory=list)


class FakeBot(Bot):
    def __init__(self, tg: FakeTelegram) -> None:
        super().__init__(token="123456:" + "A" * 35)
        self.tg = tg
        self._ids = itertools.count(100)

    # --- yordamchilar ---
    def _message(self, message_id: int, text: str | None, markup: InlineKeyboardMarkup | None) -> Message:
        entities = None
        if text and "<tg-emoji" in text and not self.tg.drop_custom_emoji:
            entities = [MessageEntity(type="custom_emoji", offset=0, length=2, custom_emoji_id="1")]
        if markup is not None and self.tg.drop_icons:
            markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [b.model_copy(update={"icon_custom_emoji_id": None}) for b in row] for row in markup.inline_keyboard
                ]
            )
        return Message(
            message_id=message_id,
            date=0,
            chat=Chat(id=CHAT_ID, type="private"),
            text=text,
            entities=entities,
            reply_markup=markup,
        ).as_(self)

    def _check_icons(self, method: TelegramMethod, markup: InlineKeyboardMarkup | None) -> None:
        if self.tg.reject_icons and markup and any(b.icon_custom_emoji_id for r in markup.inline_keyboard for b in r):
            raise TelegramBadRequest(method, "Bad Request: BUTTON_ICON_INVALID")

    async def __call__(self, method: TelegramMethod, request_timeout: int | None = None) -> Any:  # type: ignore[override]
        tg = self.tg
        tg.calls.append(method)
        if isinstance(method, GetCustomEmojiStickers):
            if tg.fail_lookup:
                raise TelegramNetworkError(method, "boom")
            return [tg.stickers[i] for i in method.custom_emoji_ids if i in tg.stickers]
        if isinstance(method, GetStickerSet):
            tg.set_calls.append(method.name)
            if method.name not in tg.sets:
                raise TelegramBadRequest(method, "Bad Request: STICKERSET_INVALID")
            return tg.sets[method.name]
        if isinstance(method, (AnswerCallbackQuery, SendChatAction)):
            return True
        if isinstance(method, SendDocument):
            mid = next(self._ids)
            tg.messages[mid] = Stored(None, None, method.reply_markup, document=method.document)
            return self._message(mid, None, method.reply_markup)
        if isinstance(method, DeleteMessage):
            if method.message_id not in tg.messages:
                raise TelegramBadRequest(method, "Bad Request: message to delete not found")
            tg.deleted.add(method.message_id)
            del tg.messages[method.message_id]
            return True
        if isinstance(method, SendRichMessage):
            if tg.reject_rich:
                raise TelegramBadRequest(method, "Bad Request: rich messages are not supported")
            self._check_icons(method, method.reply_markup)
            mid = next(self._ids)
            tg.messages[mid] = Stored(None, method.rich_message, method.reply_markup)
            return self._message(mid, None, method.reply_markup)
        if isinstance(method, SendMessage):
            self._check_icons(method, method.reply_markup)
            mid = next(self._ids)
            tg.messages[mid] = Stored(method.text, None, method.reply_markup)
            return self._message(mid, method.text, method.reply_markup)
        if isinstance(method, EditMessageText):
            mid = method.message_id
            if mid in tg.deleted or mid not in tg.messages:
                raise TelegramBadRequest(method, "Bad Request: message to edit not found")
            if method.rich_message is not None and tg.reject_rich:
                raise TelegramBadRequest(method, "Bad Request: rich messages are not supported")
            self._check_icons(method, method.reply_markup)
            new = Stored(method.text, method.rich_message, method.reply_markup)
            if new == tg.messages[mid]:
                raise TelegramBadRequest(method, "Bad Request: message is not modified")
            tg.messages[mid] = new
            return self._message(mid, method.text, method.reply_markup)
        raise AssertionError(f"unexpected method {type(method).__name__}")


def _detach_routers() -> None:
    """aiogram router'i faqat bitta Dispatcher'ga ulanadi; testlarda har safar yangi Dispatcher yaratiladi."""
    from app.handlers import code_generator, emoji_input, emoji_select, pagination, start

    for module in (start, pagination, emoji_select, code_generator, emoji_input):
        module.router._parent_router = None


class Harness:
    """Dispatcher orqali haqiqiy update'larni o'tkazish."""

    def __init__(self, tg: FakeTelegram, registry: PremiumEmojiRegistry | None = None) -> None:
        self.tg = tg
        self.bot = FakeBot(tg)
        self.registry = registry or PremiumEmojiRegistry()
        _detach_routers()
        self.dp = create_dispatcher(self.bot, Settings(bot_token=self.bot.token), self.registry)
        self._update_ids = itertools.count(1)
        self._msg_ids = itertools.count(1)

    async def send_text(self, text: str, entities: list[MessageEntity] | None = None, user_id: int = USER_ID) -> None:
        message = Message(
            message_id=next(self._msg_ids),
            date=0,
            chat=Chat(id=CHAT_ID, type="private"),
            from_user=User(id=user_id, is_bot=False, first_name="U"),
            text=text,
            entities=entities,
        )
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), message=message))

    async def click(self, data: str, message_id: int | None = None, user_id: int = USER_ID) -> None:
        mid = message_id if message_id is not None else self.last_message_id
        stored = self.tg.messages[mid]
        message = Message(
            message_id=mid,
            date=0,
            chat=Chat(id=CHAT_ID, type="private"),
            text=None if stored.document else (stored.text or "rich"),
            document=Document(file_id="doc", file_unique_id="doc") if stored.document else None,
            reply_markup=stored.markup,
        )
        callback = CallbackQuery(
            id=str(next(self._update_ids)),
            from_user=User(id=user_id, is_bot=False, first_name="U"),
            chat_instance="ci",
            message=message,
            data=data,
        )
        await self.dp.feed_update(self.bot, Update(update_id=next(self._update_ids), callback_query=callback))

    @property
    def last_message_id(self) -> int:
        return max(self.tg.messages)

    @property
    def last(self) -> Stored:
        return self.tg.messages[self.last_message_id]

    def buttons(self, message_id: int | None = None) -> list[Any]:
        markup = self.tg.messages[message_id or self.last_message_id].markup
        return [b for row in markup.inline_keyboard for b in row] if markup else []

    def button(self, text: str, message_id: int | None = None) -> Any:
        for b in self.buttons(message_id):
            if b.text == text:
                return b
        raise AssertionError(f"button {text!r} not found in {[b.text for b in self.buttons(message_id)]}")

    def answers(self) -> list[AnswerCallbackQuery]:
        return [c for c in self.tg.calls if isinstance(c, AnswerCallbackQuery)]


def pack_tg(n: int, name: str = "Animals", title: str = "Animals Premium", **kw: Any) -> FakeTelegram:
    ids = [eid(i) for i in range(n)]
    tg = FakeTelegram(**kw)
    tg.sets[name] = make_set(name, ids, title=title)
    for i in ids:
        tg.stickers[i] = make_sticker(i, set_name=name)
    return tg


@pytest.fixture
def harness_factory():
    def factory(tg: FakeTelegram, registry: PremiumEmojiRegistry | None = None) -> Harness:
        return Harness(tg, registry)

    return factory
