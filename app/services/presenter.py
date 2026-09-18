"""Ekranni yuborish/tahrirlash. Telegram imkoniyatlari bo'yicha bosqichma-bosqich fallback.

1. rich (native jadval) -> rad etilsa HTML;
2. tugma ikonkalari -> rad etilsa ikonkasiz;
3. matndagi premium ikonkalar -> rad etilsa yoki Telegram ularni olib tashlasa, ikonkasiz qayta chizish
   (Telegram entity'ni olib tashlaganda alternativ Unicode belgi ko'rinib qoladi — UI qoidasiga zid).

Navigatsiya faqat edit orqali; xabar tahrirlab bo'lmasa (o'chirilgan/eskirgan) — yangi xabar.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.methods import SendRichMessage
from aiogram.types import InlineKeyboardMarkup, Message

from app.premium_emojis import PremiumEmojiRegistry
from app.views import Screen

logger = logging.getLogger(__name__)

Render = Callable[[], Screen]

_MAX_RETRY_AFTER = 30


def _is_not_modified(exc: TelegramBadRequest) -> bool:
    return "message is not modified" in exc.message.lower()


def _is_uneditable(exc: TelegramBadRequest) -> bool:
    text = exc.message.lower()
    return any(
        marker in text
        for marker in (
            "message to edit not found",
            "message can't be edited",
            "message_id_invalid",
            "there is no text in the message to edit",
            "message can't be found",
        )
    )


def keyboard_has_icons(markup: InlineKeyboardMarkup | None) -> bool:
    return bool(markup) and any(b.icon_custom_emoji_id for row in markup.inline_keyboard for b in row)


def strip_icons(markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup | None:
    if markup is None:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[b.model_copy(update={"icon_custom_emoji_id": None}) for b in row] for row in markup.inline_keyboard]
    )


@dataclass(frozen=True, slots=True)
class _Attempt:
    use_rich: bool
    strip_icons: bool
    screen: Screen


class Presenter:
    def __init__(self, registry: PremiumEmojiRegistry) -> None:
        self.registry = registry

    async def send(self, bot: Bot, chat_id: int, render: Render) -> Message | None:
        return await self._deliver(bot, chat_id, None, render)

    async def edit(self, message: Message, render: Render) -> Message | None:
        """Xabarni tahrirlaydi; imkoni bo'lmasa shu chatga yangi xabar yuboradi."""
        assert message.bot is not None
        return await self._deliver(message.bot, message.chat.id, message.message_id, render)

    async def _deliver(self, bot: Bot, chat_id: int, message_id: int | None, render: Render) -> Message | None:
        screen = render()
        try:
            return await self._deliver_screen(bot, chat_id, message_id, screen, render)
        except TelegramBadRequest:
            # Oxirgi chora: matndagi premium ikonkalarni o'chirib, qayta chizamiz.
            if "<tg-emoji" not in screen.html or not self.registry.text.supported:
                raise
            self.registry.text.disable("Telegram rejected message with custom emoji")
            fixed = render()
            if fixed == screen:
                raise
            return await self._deliver_screen(bot, chat_id, message_id, fixed, render)

    async def _deliver_screen(
        self, bot: Bot, chat_id: int, message_id: int | None, screen: Screen, render: Render
    ) -> Message | None:
        attempts = self._attempts(screen)
        last_exc: TelegramBadRequest | None = None
        for n, attempt in enumerate(attempts):
            try:
                result = await self._call(bot, chat_id, message_id, attempt)
            except TelegramBadRequest as exc:
                if _is_not_modified(exc):
                    return None
                if message_id is None or not _is_uneditable(exc):
                    last_exc = exc
                    logger.warning("Delivery attempt %d/%d failed | %s", n + 1, len(attempts), exc.message)
                    continue
                logger.info("Message not editable, sending new | chat=%s | %s", chat_id, exc.message)
                message_id = None
                try:
                    result = await self._call(bot, chat_id, None, attempt)
                except TelegramBadRequest as exc2:
                    last_exc = exc2
                    logger.warning("Delivery attempt %d/%d failed | %s", n + 1, len(attempts), exc2.message)
                    continue
            if n > 0:
                self._learn(attempts[0], attempt)
            await self._verify(bot, chat_id, attempt, result, render)
            return result if isinstance(result, Message) else None
        assert last_exc is not None
        raise last_exc

    def _attempts(self, screen: Screen) -> list[_Attempt]:
        """Urinishlar tartibi: [rich] [rich, ikonkasiz] [html] [html, ikonkasiz]."""
        icons = keyboard_has_icons(screen.keyboard)
        variants: list[_Attempt] = []
        if screen.rich is not None and self.registry.rich.supported:
            variants.append(_Attempt(True, False, screen))
            if icons:
                variants.append(_Attempt(True, True, screen))
        variants.append(_Attempt(False, False, screen))
        if icons:
            variants.append(_Attempt(False, True, screen))
        return variants

    def _learn(self, first: _Attempt, success: _Attempt) -> None:
        if first.use_rich and not success.use_rich:
            self.registry.rich.disable("sendRichMessage/editMessageText(rich) rejected")
        if success.strip_icons:
            self.registry.icons.disable("button icon_custom_emoji_id rejected")

    async def _call(self, bot: Bot, chat_id: int, message_id: int | None, attempt: _Attempt) -> Message | bool:
        screen = attempt.screen
        markup = strip_icons(screen.keyboard) if attempt.strip_icons else screen.keyboard
        for retry in range(2):
            try:
                if message_id is None:
                    if attempt.use_rich:
                        return await bot(SendRichMessage(chat_id=chat_id, rich_message=screen.rich, reply_markup=markup))
                    return await bot.send_message(chat_id, screen.html, reply_markup=markup)
                if attempt.use_rich:
                    return await bot.edit_message_text(
                        chat_id=chat_id, message_id=message_id, rich_message=screen.rich, reply_markup=markup
                    )
                return await bot.edit_message_text(
                    chat_id=chat_id, message_id=message_id, text=screen.html, reply_markup=markup
                )
            except TelegramRetryAfter as exc:
                if retry or exc.retry_after > _MAX_RETRY_AFTER:
                    raise
                logger.warning("Flood control: waiting %s s", exc.retry_after)
                await asyncio.sleep(exc.retry_after)
        raise AssertionError("unreachable")

    async def _verify(self, bot: Bot, chat_id: int, attempt: _Attempt, result: Message | bool, render: Render) -> None:
        """Telegram premium elementlarni jimgina olib tashlaganini aniqlash."""
        if not isinstance(result, Message):
            return
        markup = result.reply_markup
        if keyboard_has_icons(attempt.screen.keyboard) and not attempt.strip_icons and not keyboard_has_icons(markup):
            # Tugmalar ikonkasiz ko'rinadi — bu ruxsat etilgan fallback (faqat matn); faqat keyingi safar uchun eslab qolamiz.
            self.registry.icons.disable("Telegram dropped icon_custom_emoji_id (bot owner without Premium?)")

        if attempt.use_rich or "<tg-emoji" not in attempt.screen.html:
            return
        if any(e.type == "custom_emoji" for e in result.entities or ()):
            return
        # Telegram custom emoji entity'larini olib tashladi: alternativ Unicode belgilar ko'rinib qoldi.
        self.registry.text.disable("Telegram dropped custom emoji entities")
        fixed = render()
        if fixed.html != attempt.screen.html:
            try:
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=result.message_id, text=fixed.html, reply_markup=result.reply_markup
                )
            except TelegramBadRequest as exc:
                logger.warning("Could not re-render without premium icons: %s", exc.message)


    async def edit_strict(self, message: Message, screen: Screen) -> Message | None:
        """Fallback'siz tahrirlash (Button Preview uchun: ikonka olib tashlanmasligi kerak)."""
        assert message.bot is not None
        try:
            result = await self._call(message.bot, message.chat.id, message.message_id, _Attempt(False, False, screen))
        except TelegramBadRequest as exc:
            if _is_not_modified(exc):
                return None
            raise
        return result if isinstance(result, Message) else None
