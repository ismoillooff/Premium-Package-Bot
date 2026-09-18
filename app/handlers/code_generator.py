"""Kod generatori, kodni fayl sifatida yuborish va Button Preview."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.handlers.common import resolve, show
from app.services.code_generator_service import (
    LANGUAGES,
    CodeGeneratorService,
    UnsupportedLanguageError,
    parse_language,
)
from app.services.presenter import Presenter
from app.services.session_service import SessionStore
from app.utils.callback_data import CodeCb, CodeFileCb, PreviewCb
from app.utils.formatting import h, ui_icon
from app.views import Views

logger = logging.getLogger(__name__)
router = Router(name="code_generator")


@router.callback_query(CodeCb.filter())
async def on_code(
    callback: CallbackQuery,
    callback_data: CodeCb,
    sessions: SessionStore,
    presenter: Presenter,
    views: Views,
    code_generator: CodeGeneratorService,
) -> None:
    cb = callback_data
    resolved = await resolve(callback, cb.s, cb.k, sessions, presenter, views, index=cb.i)
    if resolved is None:
        return
    session, pack = resolved
    try:
        language = parse_language(cb.l)
    except UnsupportedLanguageError:
        await callback.answer("Bu dasturlash tili qo'llanmaydi", show_alert=True)
        return
    await callback.answer()
    item = pack.items[cb.i - 1]
    generated = code_generator.generate(language, item.custom_emoji_id)
    logger.info("user=%s | selected=%d | language=%s", callback.from_user.id, cb.i, language.value)
    await show(callback, presenter, lambda: views.code(session, cb.k, cb.i, cb.p, generated))


@router.callback_query(CodeFileCb.filter())
async def on_code_file(
    callback: CallbackQuery,
    callback_data: CodeFileCb,
    sessions: SessionStore,
    presenter: Presenter,
    views: Views,
    code_generator: CodeGeneratorService,
) -> None:
    cb = callback_data
    resolved = await resolve(callback, cb.s, cb.k, sessions, presenter, views, index=cb.i)
    if resolved is None or callback.message is None or callback.bot is None:
        return
    _, pack = resolved
    try:
        language = parse_language(cb.l)
    except UnsupportedLanguageError:
        await callback.answer("Bu dasturlash tili qo'llanmaydi", show_alert=True)
        return
    await callback.answer("Fayl tayyorlanmoqda")
    generated = code_generator.generate(language, pack.items[cb.i - 1].custom_emoji_id)
    caption = f"{ui_icon(views.registry, LANGUAGES[language].icon)}<b>{h(generated.title)}</b>"
    await callback.bot.send_document(
        callback.message.chat.id,
        BufferedInputFile(generated.code.encode("utf-8"), filename=generated.file_name),
        caption=caption,
    )


@router.callback_query(PreviewCb.filter())
async def on_preview(
    callback: CallbackQuery, callback_data: PreviewCb, sessions: SessionStore, presenter: Presenter, views: Views
) -> None:
    cb = callback_data
    resolved = await resolve(callback, cb.s, cb.k, sessions, presenter, views, index=cb.i)
    if resolved is None:
        return
    session, pack = resolved
    await callback.answer()
    item = pack.items[cb.i - 1]
    logger.info("user=%s | selected=%d | preview", callback.from_user.id, cb.i)

    if not isinstance(callback.message, Message):
        await show(callback, presenter, lambda: views.preview(session, cb.k, cb.i, cb.p))
        return
    try:
        # Fallback'siz: ikonka olib tashlansa, preview ma'nosiz bo'ladi.
        result = await presenter.edit_strict(callback.message, views.preview(session, cb.k, cb.i, cb.p))
    except TelegramBadRequest as exc:
        logger.warning("user=%s | preview rejected | %s", callback.from_user.id, exc.message)
        await show(callback, presenter, lambda: views.preview_failed(session, cb.k, cb.i, cb.p))
        return

    if result is not None and result.reply_markup is not None:
        first = result.reply_markup.inline_keyboard[0][0]
        if first.icon_custom_emoji_id != item.custom_emoji_id:
            note = (
                "Telegram tugma ikonkasini ko'rsatmadi. icon_custom_emoji_id faqat Fragment'dan qo'shimcha "
                "username sotib olgan botlarda yoki bot egasida Telegram Premium bo'lganda ishlaydi."
            )
            await show(callback, presenter, lambda: views.preview(session, cb.k, cb.i, cb.p, note=note))

