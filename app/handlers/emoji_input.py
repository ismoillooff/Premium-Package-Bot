"""Foydalanuvchi yuborgan xabardan custom emoji'larni olish va explorer'ni ochish."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.handlers.common import expired

from app.models.emoji import LookupResult
from app.services.emoji_service import (
    EmojiLookupError,
    EmojiService,
    browsable_packs,
    extract_custom_emoji_ids,
)
from app.services.presenter import Presenter, Render
from app.services.session_service import SessionStore
from app.utils.pagination import get_page
from app.utils.telegram_limits import CUSTOM_EMOJI_IDS_PER_REQUEST
from app.views import Views

logger = logging.getLogger(__name__)
router = Router(name="emoji_input")


def build_notes(result: LookupResult, truncated: bool) -> list[str]:
    notes: list[str] = []
    if truncated:
        notes.append(f"Bitta xabardan ko'pi bilan {CUSTOM_EMOJI_IDS_PER_REQUEST} ta emoji tekshiriladi.")
    if result.missing_ids:
        notes.append(f"Telegram {len(result.missing_ids)} ta emoji bo'yicha ma'lumot bermadi.")
    if result.failed_sets:
        notes.append(
            "Telegram Bot API quyidagi set(lar) uchun to'liq pack ma'lumotini bermadi: "
            + ", ".join(result.failed_sets)
        )
    if result.skipped_sets:
        notes.append(f"Yana {len(result.skipped_sets)} ta set yuklanmadi — ularning emoji'larini alohida yuboring.")
    return notes


@router.message(F.text | F.caption)
async def on_emoji_message(
    message: Message,
    emoji_service: EmojiService,
    sessions: SessionStore,
    presenter: Presenter,
    views: Views,
) -> None:
    assert message.bot is not None
    bot, chat_id = message.bot, message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    entities = message.entities if message.text is not None else message.caption_entities
    ids = extract_custom_emoji_ids(entities)

    if not ids:
        await presenter.send(bot, chat_id, views.not_custom)
        return

    truncated = len(ids) > CUSTOM_EMOJI_IDS_PER_REQUEST
    ids = ids[:CUSTOM_EMOJI_IDS_PER_REQUEST]
    logger.info("user=%s | custom emoji received | count=%d", user_id, len(ids))

    # Darhol javob — pack yuklanguncha foydalanuvchi kutib qolmasin; keyin shu xabar tahrirlanadi.
    status = await presenter.send(bot, chat_id, views.loading)

    async def display(render: Render) -> None:
        if status is not None:
            await presenter.edit(status, render)
        else:
            await presenter.send(bot, chat_id, render)

    try:
        result = await emoji_service.lookup(ids)
    except EmojiLookupError:
        await display(views.api_error)
        return

    packs = browsable_packs(result)
    if not packs:
        await display(lambda: views.not_found(ids))
        return

    session = sessions.create(user_id, packs, build_notes(result, truncated), sent=result.requested)
    for pack in packs:
        logger.info("user=%s | set=%s | emojis=%d", user_id, pack.name or "-", pack.total)

    if len(packs) == 1:
        info = get_page(packs[0].total, 1)
        await display(lambda: views.explorer(session, 0, info))
    else:
        await display(lambda: views.pack_list(session))


@router.message()
async def on_other(message: Message, presenter: Presenter, views: Views) -> None:
    # Stiker, rasm (izohsiz), ovozli xabar va boshqalar.
    assert message.bot is not None
    await presenter.send(message.bot, message.chat.id, views.not_custom)


@router.callback_query()
async def on_unknown_callback(callback: CallbackQuery, presenter: Presenter, views: Views) -> None:
    # Noma'lum yoki eski formatdagi tugma (masalan bot yangilanishidan oldingi menyu) — spinner qotmasin.
    logger.info("user=%s | unknown callback", callback.from_user.id)
    await expired(callback, presenter, views)
