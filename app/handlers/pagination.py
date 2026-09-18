"""Explorer jadvali: sahifalar, pack ro'yxati, jadval fayli."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from app.handlers.common import expired, resolve, show
from app.services.presenter import Presenter
from app.services.session_service import SessionStore
from app.keyboards.emoji_keyboard import table_file_keyboard
from app.utils.callback_data import PacksCb, PageCb, TableFileCb
from app.utils.formatting import h, ui_icon
from app.utils.pagination import clamp_page, get_page
from app.utils.table import build_ids_text_table
from app.premium_emojis import PremiumEmoji
from app.views import Views

logger = logging.getLogger(__name__)
router = Router(name="pagination")


@router.callback_query(PageCb.filter())
async def on_page(
    callback: CallbackQuery, callback_data: PageCb, sessions: SessionStore, presenter: Presenter, views: Views
) -> None:
    resolved = await resolve(callback, callback_data.s, callback_data.k, sessions, presenter, views)
    if resolved is None:
        return
    session, pack = resolved
    await callback.answer()
    # Chegaradan tashqari sahifa (eski/soxta callback) — eng yaqin mavjud sahifa.
    page = clamp_page(callback_data.p, pack.total)
    info = get_page(pack.total, page)
    logger.info("user=%s | set=%s | page=%d", callback.from_user.id, pack.name or "-", page)
    await show(callback, presenter, lambda: views.explorer(session, callback_data.k, info))


@router.callback_query(PacksCb.filter())
async def on_pack_list(
    callback: CallbackQuery, callback_data: PacksCb, sessions: SessionStore, presenter: Presenter, views: Views
) -> None:
    session = sessions.get(callback.from_user.id, callback_data.s)
    if session is None:
        await expired(callback, presenter, views)
        return
    await callback.answer()
    await show(callback, presenter, lambda: views.pack_list(session))


@router.callback_query(TableFileCb.filter())
async def on_table_file(
    callback: CallbackQuery, callback_data: TableFileCb, sessions: SessionStore, presenter: Presenter, views: Views
) -> None:
    """Jadval xabarini o'chirib, ID'lar jadvalini .txt qilib yuboradi (ostida "Jadvalga qaytish")."""
    cb = callback_data
    resolved = await resolve(callback, cb.s, cb.k, sessions, presenter, views)
    if resolved is None or callback.message is None or callback.bot is None:
        return
    session, pack = resolved
    await callback.answer("Jadval tayyorlanmoqda")
    chat_id = callback.message.chat.id
    if isinstance(callback.message, Message):
        try:
            await callback.message.delete()
        except TelegramBadRequest as exc:  # 48 soatdan eski yoki allaqachon o'chirilgan
            logger.info("user=%s | could not delete explorer message | %s", callback.from_user.id, exc.message)
    logger.info("user=%s | set=%s | table file", callback.from_user.id, pack.name or "-")
    await callback.bot.send_document(
        chat_id,
        BufferedInputFile(build_ids_text_table(pack).encode("utf-8"), filename=f"{pack.name or 'custom_emojis'}_jadval.txt"),
        caption=f"{ui_icon(views.registry, PremiumEmoji.TABLE)}<b>{h(pack.title)}</b>\n{pack.total} ta Custom Emoji ID",
        reply_markup=table_file_keyboard(views.buttons, session.sid, cb.k, cb.p),
    )
