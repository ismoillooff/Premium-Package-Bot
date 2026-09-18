from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

from app.handlers.common import show
from app.services.presenter import Presenter
from app.services.session_service import SessionStore
from app.utils.callback_data import NOOP, RESTART, ListCreateCb
from app.views import Views

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message, presenter: Presenter, views: Views) -> None:
    assert message.bot is not None
    await presenter.send(message.bot, message.chat.id, views.start)


@router.message(Command("help"))
async def cmd_help(message: Message, presenter: Presenter, views: Views) -> None:
    assert message.bot is not None
    await presenter.send(message.bot, message.chat.id, views.help)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, presenter: Presenter, views: Views, sessions: SessionStore) -> None:
    assert message.bot is not None
    existed = sessions.drop(message.from_user.id) if message.from_user else False
    await presenter.send(message.bot, message.chat.id, lambda: views.cancelled(existed))


@router.callback_query(F.data == RESTART)
async def on_restart(callback: CallbackQuery, presenter: Presenter, views: Views, sessions: SessionStore) -> None:
    await callback.answer()
    sessions.drop(callback.from_user.id)
    await show(callback, presenter, views.start)


@router.callback_query(ListCreateCb.filter())
async def on_list_create(callback: CallbackQuery) -> None:
    # Funksiyasi keyinroq qo'shiladi.
    await callback.answer("Ro'yxat yaratish tez orada qo'shiladi")


@router.callback_query(F.data == NOOP)
async def on_noop(callback: CallbackQuery) -> None:
    # Sahifa ko'rsatkichi va Button Preview'dagi test tugma.
    await callback.answer()
