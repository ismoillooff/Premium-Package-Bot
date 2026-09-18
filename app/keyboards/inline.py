from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

AGAIN_CALLBACK = "again"


class IdsCallback(CallbackData, prefix="ids"):
    token: str


def result_keyboard(token: str, copy_text: str | None, copy_label: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 ID larni olish", callback_data=IdsCallback(token=token).pack()))
    if copy_text:
        # Bot API 7.11+: bosilganda matn to'g'ridan-to'g'ri clipboard'ga ko'chiriladi (1–256 belgi).
        builder.row(InlineKeyboardButton(text=copy_label, copy_text=CopyTextButton(text=copy_text)))
    builder.row(InlineKeyboardButton(text="🔄 Boshqa emoji tekshirish", callback_data=AGAIN_CALLBACK))
    return builder.as_markup()


def again_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Boshqa emoji tekshirish", callback_data=AGAIN_CALLBACK))
    return builder.as_markup()
