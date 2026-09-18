"""Handlerlar uchun umumiy yordamchilar: sessiya/egalik tekshiruvi va ekranni callback xabarida ko'rsatish."""

from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

from app.models.emoji import EmojiPack
from app.services.presenter import Presenter, Render
from app.services.session_service import Session, SessionStore
from app.views import Views

logger = logging.getLogger(__name__)


async def show(callback: CallbackQuery, presenter: Presenter, render: Render) -> Message | None:
    """Callback xabarini tahrirlaydi; xabar eskirgan/o'chirilgan bo'lsa yangisini yuboradi."""
    message = callback.message
    if isinstance(message, Message) and message.document is not None and callback.bot is not None:
        # Fayl xabari (masalan jadval .txt) matnga tahrirlanmaydi: o'chirib, o'rniga ekranni yuboramiz.
        try:
            await message.delete()
        except TelegramBadRequest as exc:
            logger.info("Could not delete document message: %s", exc.message)
        return await presenter.send(callback.bot, message.chat.id, render)
    if isinstance(message, Message):
        return await presenter.edit(message, render)
    if message is not None and callback.bot is not None:  # InaccessibleMessage (48 soatdan eski)
        return await presenter.send(callback.bot, message.chat.id, render)
    return None


async def expired(callback: CallbackQuery, presenter: Presenter, views: Views) -> None:
    await callback.answer("Menyu eskirgan")
    await show(callback, presenter, views.expired)


async def resolve(
    callback: CallbackQuery,
    sid: str,
    k: int,
    sessions: SessionStore,
    presenter: Presenter,
    views: Views,
    *,
    index: int | None = None,
) -> tuple[Session, EmojiPack] | None:
    """Sessiya egasi, pack va parametrlarni tekshiradi. Noto'g'ri/eskirgan bo'lsa — foydalanuvchiga xabar."""
    session = sessions.get(callback.from_user.id, sid)
    pack = session.pack(k) if session is not None else None
    valid = (
        pack is not None
        and (index is None or pack.item(index) is not None)
    )
    if not valid:
        logger.info("user=%s | stale or invalid callback", callback.from_user.id)
        await expired(callback, presenter, views)
        return None
    assert session is not None and pack is not None
    return session, pack
