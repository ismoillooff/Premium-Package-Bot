"""Ixcham callback_data (Telegram limiti: 64 bayt).

Set nomi va emoji ID callback'ga yozilmaydi — ular sessiyadan olinadi.
Navigatsiya konteksti (pack, sahifa, tanlangan emoji) callback'ning o'zida,
shuning uchun "Jadvalga qaytish" har doim aynan o'sha sahifaga qaytaradi.

Maydonlar: s — sessiya ID, k — pack raqami, p — sahifa,
i — emoji global raqami, l — dasturlash tili.
"""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

NOOP = "x"
RESTART = "r"


class PageCb(CallbackData, prefix="p"):
    s: str
    k: int
    p: int


class EmojiCb(CallbackData, prefix="e"):
    s: str
    k: int
    i: int
    p: int


class CodeCb(CallbackData, prefix="c"):
    s: str
    k: int
    i: int
    l: str  # noqa: E741
    p: int


class CodeFileCb(CallbackData, prefix="f"):
    s: str
    k: int
    i: int
    l: str  # noqa: E741


class PreviewCb(CallbackData, prefix="v"):
    s: str
    k: int
    i: int
    p: int


class ListCreateCb(CallbackData, prefix="y"):
    """"Ro'yxat yaratish" — funksiyasi keyinroq aniqlanadi; kontekst hozirdan saqlanadi."""

    s: str
    k: int
    i: int
    p: int


class TableFileCb(CallbackData, prefix="t"):
    """"Jadval": explorer xabari o'chiriladi, ID'lar jadvali .txt bo'lib keladi (p — qaytish uchun sahifa)."""

    s: str
    k: int
    p: int


class PacksCb(CallbackData, prefix="l"):
    s: str

