from __future__ import annotations

from aiogram.types import InlineKeyboardButton

from app.keyboards.factory import PremiumButtonFactory
from app.utils.callback_data import NOOP, PageCb
from app.utils.pagination import PageInfo


def pagination_row(
    factory: PremiumButtonFactory, info: PageInfo, sid: str, k: int
) -> list[InlineKeyboardButton]:
    """[Oldingi] [p / P] [Keyingi] — birinchi/oxirgi sahifada tegishli tugma chiqmaydi."""
    row: list[InlineKeyboardButton] = []
    if not info.is_first:
        row.append(factory.previous(PageCb(s=sid, k=k, p=info.page - 1).pack()))
    row.append(factory.page_indicator(f"{info.page} / {info.total_pages}", NOOP))
    if not info.is_last:
        row.append(factory.next(PageCb(s=sid, k=k, p=info.page + 1).pack()))
    return row
