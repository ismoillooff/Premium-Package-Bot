from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from collections.abc import Sequence

from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.keyboards.inline import AGAIN_CALLBACK, IdsCallback, again_keyboard, result_keyboard
from app.services.emoji_service import (
    MAX_IDS_PER_REQUEST,
    EmojiLookupError,
    EmojiService,
    LookupResult,
    extract_custom_emoji_ids,
)
from app.utils.cache import TTLCache
from app.utils.formatting import (
    copy_payload,
    format_ids_messages,
    format_orphans_messages,
    format_pack_messages,
    format_summary,
    format_warnings,
    h,
)

logger = logging.getLogger(__name__)
router = Router(name="emoji")

# "📋 ID larni olish" tugmasi uchun natijalar (callback_data 64 baytdan oshmasligi uchun token).
_results: TTLCache[str, LookupResult] = TTLCache(ttl=3600, max_size=2000)

NOT_CUSTOM_TEXT = (
    "❌ Bu Custom/Premium Emoji emas.\n\n"
    "Telegram Premium Custom Emoji yuboring."
)
API_ERROR_TEXT = (
    "⚠️ Telegram'dan emoji ma'lumotlarini olishda xatolik yuz berdi.\n"
    "Keyinroq qayta urinib ko'ring."
)
EXPIRED_TEXT = "Natija eskirdi. Emoji'ni qaytadan yuboring."


# Katta packlar (masalan 997 ta emoji ≈ 20 xabar) bitta chatga flood limitdan oshmasin.
_BURST_SIZE = 5
_PACE_DELAY = 0.5
_MAX_RETRIES = 3


async def _send(message: Message, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Xabar yuborish; flood limitda Telegram aytgan vaqtcha kutib qayta urinadi."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            await message.answer(text, reply_markup=reply_markup)
            return
        except TelegramRetryAfter as exc:
            if attempt == _MAX_RETRIES:
                raise
            logger.warning("Flood control: waiting %s s", exc.retry_after)
            await asyncio.sleep(exc.retry_after)


async def _send_all(message: Message, texts: Sequence[str], reply_markup: InlineKeyboardMarkup | None) -> None:
    """Xabarlarni ketma-ket yuboradi; klaviatura oxirgisiga biriktiriladi."""
    last = len(texts) - 1
    for idx, text in enumerate(texts):
        if idx >= _BURST_SIZE:
            await asyncio.sleep(_PACE_DELAY)
        await _send(message, text, reply_markup if idx == last else None)


@router.message(F.text | F.caption)
async def handle_emoji_message(message: Message, emoji_service: EmojiService) -> None:
    entities = message.entities if message.text is not None else message.caption_entities
    ids = extract_custom_emoji_ids(entities)
    user_id = message.from_user.id if message.from_user else 0

    if not ids:
        await message.answer(NOT_CUSTOM_TEXT)
        return

    truncated = len(ids) > MAX_IDS_PER_REQUEST
    ids = ids[:MAX_IDS_PER_REQUEST]
    logger.info("User %s sent %d custom emojis", user_id, len(ids))

    if message.bot is not None:
        with contextlib.suppress(TelegramAPIError):
            await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    try:
        result = await emoji_service.lookup(ids)
    except EmojiLookupError:
        await message.answer(API_ERROR_TEXT)
        return

    if not result.requested:
        text = (
            "⚠️ Telegram Bot API ushbu emoji uchun ma'lumot bermadi.\n\n"
            "<b>Emoji ID:</b>\n" + "\n".join(f"<code>{h(i)}</code>" for i in ids)
        )
        await message.answer(text, reply_markup=again_keyboard())
        return

    for pack in result.packs:
        logger.info("Custom emoji set detected: %s", pack.name)
    logger.info("%d custom emojis extracted for user %s", len(result.all_ids), user_id)

    texts = [format_summary(result, truncated)]
    numbered = len(result.packs) > 1
    for number, pack in enumerate(result.packs, start=1):
        texts.extend(format_pack_messages(pack, number if numbered else None))
    # Summary allaqachon setsiz emoji'larni ko'rsatadi; qo'shimcha ro'yxat faqat packlar bilan aralash bo'lsa.
    if result.orphans and result.packs:
        texts.extend(format_orphans_messages(result.orphans))

    token = secrets.token_urlsafe(9)
    _results.set(token, result)
    requested_ids = [i.custom_emoji_id for i in result.requested]
    copy_label = "📎 ID ni nusxalash" if len(requested_ids) == 1 else "📎 Yuborilgan ID larni nusxalash"
    keyboard = result_keyboard(token, copy_payload(requested_ids), copy_label)

    await _send_all(message, texts, keyboard)


@router.message()
async def handle_other(message: Message) -> None:
    # Stiker, rasm (izohsiz), ovozli xabar va boshqalar.
    await message.answer(NOT_CUSTOM_TEXT)


@router.callback_query(IdsCallback.filter())
async def on_ids(callback: CallbackQuery, callback_data: IdsCallback) -> None:
    result = _results.get(callback_data.token)
    if result is None or not isinstance(callback.message, Message):
        await callback.answer(EXPIRED_TEXT, show_alert=True)
        return
    await callback.answer()
    texts = format_ids_messages(result)
    warnings = format_warnings(result)
    if warnings:
        texts.append(warnings)
    await _send_all(callback.message, texts, None)


@router.callback_query(F.data == AGAIN_CALLBACK)
async def on_again(callback: CallbackQuery) -> None:
    await callback.answer()
    if isinstance(callback.message, Message):
        await callback.message.answer("👇 Yangi Custom/Premium Emoji yuboring.")
