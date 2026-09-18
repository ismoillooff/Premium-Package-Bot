"""Jadvaldan emoji tanlash -> emoji tafsiloti."""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import CallbackQuery

from app.handlers.common import resolve, show
from app.services.presenter import Presenter
from app.services.session_service import SessionStore
from app.utils.callback_data import EmojiCb
from app.views import Views

logger = logging.getLogger(__name__)
router = Router(name="emoji_select")


@router.callback_query(EmojiCb.filter())
async def on_emoji(
    callback: CallbackQuery, callback_data: EmojiCb, sessions: SessionStore, presenter: Presenter, views: Views
) -> None:
    cb = callback_data
    resolved = await resolve(callback, cb.s, cb.k, sessions, presenter, views, index=cb.i)
    if resolved is None:
        return
    session, pack = resolved
    await callback.answer()
    logger.info("user=%s | set=%s | selected=%d", callback.from_user.id, pack.name or "-", cb.i)
    await show(callback, presenter, lambda: views.detail(session, cb.k, cb.i, cb.p))
