"""Emoji jadvali: N ustun, har bir katakda (global raqam, element).

Standart — 5 ustun, chapdan o'ngga (raqamli tanlash tugmalari bilan bir xil joylashuv):

    25 ta:  1  2  3  4  5        7 ta:  1  2  3  4  5
            6  7  8  9 10               6  7  .  .  .
           11 12 13 14 15
           16 17 18 19 20
           21 22 23 24 25

vertical=True — ustun bo'yicha to'ldirish (masalan 2 ustun: 1..10 | 11..20).
Oxirgi qatordagi bo'sh joylar None.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypeVar

from app.constants import TABLE_COLUMNS
from app.models.emoji import EmojiPack

T = TypeVar("T")

Cell = tuple[int, T]


def build_emoji_table(
    items: Sequence[T],
    start_index: int,
    columns: int = TABLE_COLUMNS,
    *,
    vertical: bool = False,
) -> list[list[Cell[T] | None]]:
    """Qatorlar ro'yxati; har bir qator uzunligi `columns`, bo'sh kataklar None."""
    if columns < 1:
        raise ValueError("columns must be >= 1")
    n = len(items)
    row_count = math.ceil(n / columns)
    rows: list[list[Cell[T] | None]] = []
    for r in range(row_count):
        row: list[Cell[T] | None] = []
        for c in range(columns):
            pos = c * row_count + r if vertical else r * columns + c
            row.append((start_index + pos, items[pos]) if pos < n else None)
        rows.append(row)
    return rows


def build_ids_text_table(pack: EmojiPack) -> str:
    """Pack'dagi barcha emoji'lar: № | ID | Emoji (.txt uchun, monospace'da tekis).

    Emoji ustuni oxirida — uning kengligi shriftga bog'liq, tekislashni buzmasin.
    """
    num_w = max(len("№"), len(str(pack.total)))
    id_w = max([len("ID"), *(len(item.custom_emoji_id) for item in pack.items)])
    title = pack.title if pack.is_virtual else f"{pack.title} ({pack.name})"
    lines = [
        title,
        f"{pack.total} ta Custom Emoji",
        "",
        f"{'№':>{num_w}} | {'ID':<{id_w}} | Emoji",
        f"{'-' * num_w}-+-{'-' * id_w}-+-------",
    ]
    lines += [
        f"{n:>{num_w}} | {item.custom_emoji_id:<{id_w}} | {item.emoji or ''}".rstrip()
        for n, item in enumerate(pack.items, start=1)
    ]
    return "\n".join(lines) + "\n"
