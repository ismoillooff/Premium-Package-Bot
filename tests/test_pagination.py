import pytest

from app.keyboards.factory import PremiumButtonFactory
from app.keyboards.pagination_keyboard import pagination_row
from app.premium_emojis import PremiumEmojiRegistry
from app.utils.pagination import clamp_page, get_page, page_of_index, total_pages
from app.utils.table import build_emoji_table


@pytest.mark.parametrize(
    ("total", "pages"),
    [(0, 0), (1, 1), (5, 1), (6, 1), (15, 1), (16, 1), (19, 1), (20, 1), (21, 1), (24, 1), (25, 1), (26, 2),
     (49, 2), (50, 2), (51, 3), (100, 4), (120, 5), (200, 8), (201, 9), (997, 40)],
)
def test_total_pages(total: int, pages: int) -> None:
    assert total_pages(total) == pages


@pytest.mark.parametrize(
    ("total", "page", "first", "last"),
    [(1, 1, 1, 1), (25, 1, 1, 25), (26, 2, 26, 26), (51, 3, 51, 51), (120, 4, 76, 100), (200, 8, 176, 200)],
)
def test_page_bounds(total: int, page: int, first: int, last: int) -> None:
    info = get_page(total, page)
    assert info.indices[0] == first and info.indices[-1] == last


@pytest.mark.parametrize(("total", "page"), [(0, 1), (25, 0), (25, 2), (51, 4), (100, -1)])
def test_invalid_page(total: int, page: int) -> None:
    with pytest.raises(ValueError):
        get_page(total, page)


def test_clamp_page() -> None:
    assert clamp_page(99, 51) == 3
    assert clamp_page(-5, 51) == 1
    assert clamp_page(1, 0) == 1


@pytest.mark.parametrize(
    ("total", "page", "expected"),
    [
        (8, 1, list(range(1, 9))),  # bo'sh 9–25 tugma yo'q
        (25, 1, list(range(1, 26))),
        (100, 2, list(range(26, 51))),  # global index
        (51, 3, [51]),
    ],
)
def test_page_indices_for_select_buttons(total: int, page: int, expected: list[int]) -> None:
    assert get_page(total, page).indices == expected


def test_page_of_index() -> None:
    assert [page_of_index(i) for i in (1, 25, 26, 50, 51, 90)] == [1, 1, 2, 2, 3, 4]


# ---------- jadval ----------


def _layout(n: int, start: int = 1, columns: int = 5, vertical: bool = False) -> list[list[int | None]]:
    rows = build_emoji_table(list(range(n)), start, columns, vertical=vertical)
    return [[cell[0] if cell else None for cell in row] for row in rows]


def test_table_five_columns_row_major() -> None:
    assert _layout(0) == []
    assert _layout(1) == [[1, None, None, None, None]]
    assert _layout(5) == [[1, 2, 3, 4, 5]]
    assert _layout(6) == [[1, 2, 3, 4, 5], [6, None, None, None, None]]
    assert _layout(7) == [[1, 2, 3, 4, 5], [6, 7, None, None, None]]
    assert _layout(20) == [list(range(r, r + 5)) for r in (1, 6, 11, 16)]


def test_table_matches_select_buttons() -> None:
    # Jadval qatorlari raqamli tugmalar (5 ustun) bilan bir xil.
    from app.constants import SELECT_COLUMNS, TABLE_COLUMNS

    assert TABLE_COLUMNS == SELECT_COLUMNS


def test_table_global_start_index() -> None:
    assert _layout(20, start=21)[0] == [21, 22, 23, 24, 25]
    assert _layout(20, start=21)[-1] == [36, 37, 38, 39, 40]


def test_table_vertical_option() -> None:
    assert _layout(5, columns=2, vertical=True) == [[1, 4], [2, 5], [3, None]]
    assert _layout(20, columns=2, vertical=True) == [[i, i + 10] for i in range(1, 11)]


def test_table_keeps_items_and_rejects_bad_columns() -> None:
    assert build_emoji_table(["a", "b", "c"], 1, 2) == [[(1, "a"), (2, "b")], [(3, "c"), None]]
    with pytest.raises(ValueError):
        build_emoji_table(["a"], 1, 0)


# ---------- pagination tugmalari ----------


def _row_texts(total: int, page: int) -> list[str]:
    factory = PremiumButtonFactory(PremiumEmojiRegistry())
    return [b.text for b in pagination_row(factory, get_page(total, page), "sid", 0)]


def test_pagination_first_middle_last() -> None:
    assert _row_texts(120, 1) == ["1 / 5", "Keyingi"]
    assert _row_texts(120, 3) == ["Oldingi", "3 / 5", "Keyingi"]
    assert _row_texts(120, 5) == ["Oldingi", "5 / 5"]
    assert _row_texts(10, 1) == ["1 / 1"]
