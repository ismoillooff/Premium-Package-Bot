"""Qayta ishlatiladigan pagination hisob-kitoblari. Index'lar global va 1 dan boshlanadi."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

from app.constants import EMOJIS_PER_PAGE

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class PageInfo:
    page: int
    total_pages: int
    total: int
    start: int  # 0-based, inclusive
    end: int  # 0-based, exclusive

    @property
    def first_index(self) -> int:
        """Sahifadagi birinchi elementning global raqami (1-based)."""
        return self.start + 1

    @property
    def is_first(self) -> bool:
        return self.page <= 1

    @property
    def is_last(self) -> bool:
        return self.page >= self.total_pages

    @property
    def indices(self) -> list[int]:
        return list(range(self.start + 1, self.end + 1))


def total_pages(total: int, per_page: int = EMOJIS_PER_PAGE) -> int:
    if total <= 0:
        return 0
    return math.ceil(total / per_page)


def clamp_page(page: int, total: int, per_page: int = EMOJIS_PER_PAGE) -> int:
    pages = total_pages(total, per_page)
    if pages == 0:
        return 1
    return min(max(page, 1), pages)


def get_page(total: int, page: int, per_page: int = EMOJIS_PER_PAGE) -> PageInfo:
    """Sahifa ma'lumoti. Chegaradan tashqaridagi sahifa uchun ValueError."""
    pages = total_pages(total, per_page)
    if pages == 0:
        raise ValueError("empty collection has no pages")
    if not 1 <= page <= pages:
        raise ValueError(f"page {page} out of range 1..{pages}")
    start = (page - 1) * per_page
    return PageInfo(page=page, total_pages=pages, total=total, start=start, end=min(start + per_page, total))


def page_of_index(index: int, per_page: int = EMOJIS_PER_PAGE) -> int:
    return (index - 1) // per_page + 1


def chunked(items: Sequence[T], size: int) -> list[list[T]]:
    return [list(items[i : i + size]) for i in range(0, len(items), size)]
