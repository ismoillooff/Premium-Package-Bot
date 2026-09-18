"""Barcha inline tugmalar shu yerda yaratiladi.

Tugma matni — faqat toza matn. Ikonka — faqat icon_custom_emoji_id orqali (registry'dan).
ID sozlanmagan yoki Telegram rad etgan bo'lsa, tugma ikonkasiz qoladi (Unicode emoji qo'shilmaydi).
"""

from __future__ import annotations

from aiogram.types import CopyTextButton, InlineKeyboardButton

from app.premium_emojis import PremiumEmoji, PremiumEmojiRegistry
from app.utils.telegram_limits import COPY_TEXT_MAX_CHARS


class PremiumButtonFactory:
    def __init__(self, registry: PremiumEmojiRegistry) -> None:
        self._registry = registry

    def button(
        self,
        text: str,
        *,
        role: PremiumEmoji | None = None,
        callback_data: str | None = None,
        copy_text: str | None = None,
        url: str | None = None,
        icon_custom_emoji_id: str | None = None,
    ) -> InlineKeyboardButton:
        icon = icon_custom_emoji_id or self._registry.button_icon(role)
        if copy_text is not None:
            if not 0 < len(copy_text) <= COPY_TEXT_MAX_CHARS:
                raise ValueError("copy_text must be 1-256 characters")
            return InlineKeyboardButton(text=text, copy_text=CopyTextButton(text=copy_text), icon_custom_emoji_id=icon)
        if url is not None:
            return InlineKeyboardButton(text=text, url=url, icon_custom_emoji_id=icon)
        return InlineKeyboardButton(text=text, callback_data=callback_data, icon_custom_emoji_id=icon)

    def plain(self, text: str, callback_data: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=text, callback_data=callback_data)

    def back(self, callback_data: str, text: str) -> InlineKeyboardButton:
        return self.button(text, role=PremiumEmoji.BACK, callback_data=callback_data)

    def table(self, callback_data: str) -> InlineKeyboardButton:
        return self.button("Jadvalga qaytish", role=PremiumEmoji.TABLE, callback_data=callback_data)

    def list_create(self, callback_data: str) -> InlineKeyboardButton:
        return self.button("Ro'yxat yaratish", role=PremiumEmoji.LIST_CREATE, callback_data=callback_data)

    def table_file(self, callback_data: str) -> InlineKeyboardButton:
        return self.button("Jadval", role=PremiumEmoji.TABLE, callback_data=callback_data)

    def admin(self, url: str) -> InlineKeyboardButton:
        return self.button("Admin", role=PremiumEmoji.ADMIN, url=url)

    def page_indicator(self, text: str, callback_data: str) -> InlineKeyboardButton:
        return self.button(text, role=PremiumEmoji.PAGE, callback_data=callback_data)

    def next(self, callback_data: str) -> InlineKeyboardButton:
        return self.button("Keyingi", role=PremiumEmoji.NEXT, callback_data=callback_data)

    def previous(self, callback_data: str) -> InlineKeyboardButton:
        return self.button("Oldingi", role=PremiumEmoji.PREVIOUS, callback_data=callback_data)

    def copy(self, text: str, value: str) -> InlineKeyboardButton:
        return self.button(text, role=PremiumEmoji.COPY, copy_text=value)

    def language(self, label: str, role: PremiumEmoji, callback_data: str) -> InlineKeyboardButton:
        return self.button(label, role=role, callback_data=callback_data)

    def file(self, text: str, callback_data: str) -> InlineKeyboardButton:
        return self.button(text, role=PremiumEmoji.FILE, callback_data=callback_data)

    def refresh(self, callback_data: str, text: str = "Boshidan boshlash") -> InlineKeyboardButton:
        return self.button(text, role=PremiumEmoji.REFRESH, callback_data=callback_data)
