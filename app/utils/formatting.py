"""HTML formatlash yordamchilari. Barcha dinamik qiymatlar escape qilinadi."""

from __future__ import annotations

from html import escape

from app.models.emoji import EmojiItem
from app.premium_emojis import PremiumEmoji, PremiumEmojiRegistry


def h(value: object) -> str:
    return escape(str(value), quote=False)


def attr(value: object) -> str:
    return escape(str(value), quote=True)


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def premium_emoji(emoji_id: str, fallback_text: str) -> str:
    """Telegram HTML custom emoji markup'i (<tg-emoji>). fallback_text — Telegram talab qiladigan alternativ emoji."""
    return f'<tg-emoji emoji-id="{attr(emoji_id)}">{h(fallback_text)}</tg-emoji>'


def ui_icon(registry: PremiumEmojiRegistry, role: PremiumEmoji) -> str:
    """UI ikonkasi + bo'sh joy, yoki bo'sh satr (Unicode emoji fallback YO'Q)."""
    icon = registry.text_icon(role)
    if icon is None:
        return ""
    return premium_emoji(*icon) + " "


def content_emoji(item: EmojiItem) -> str:
    """Pack ichidagi emoji'ning o'zi: custom emoji entity, alternativ sifatida Sticker.emoji."""
    if not item.emoji:
        return ""
    return premium_emoji(item.custom_emoji_id, item.emoji)


def pack_link(name: str) -> str:
    return f"https://t.me/addemoji/{name}"
