"""Custom emoji aniqlash, getCustomEmojiStickers / getStickerSet va pack yig'ish."""

import asyncio

import pytest
from aiogram.types import Message, MessageEntity

from app.constants import MAX_SETS_PER_MESSAGE
from app.services.emoji_service import EmojiLookupError, EmojiService, browsable_packs, extract_custom_emoji_ids
from app.services.sticker_set_service import StickerSetService, sticker_to_item
from tests.conftest import FakeBot, FakeTelegram, ce, eid, make_set, make_sticker


def service(tg: FakeTelegram, ttl: float = 600) -> EmojiService:
    bot = FakeBot(tg)
    return EmojiService(bot, StickerSetService(bot, cache_ttl=ttl))


# ---------- 1–5: parsing ----------


def test_normal_text() -> None:
    assert extract_custom_emoji_ids(None) == []
    assert extract_custom_emoji_ids([]) == []


def test_unicode_emoji_has_no_custom_entity() -> None:
    msg = Message.model_validate({"message_id": 1, "date": 0, "chat": {"id": 1, "type": "private"}, "text": "😀"})
    assert extract_custom_emoji_ids(msg.entities) == []


def test_single_custom_emoji() -> None:
    assert extract_custom_emoji_ids([ce("5368324170671202286")]) == ["5368324170671202286"]


def test_multiple_and_duplicates_keep_order() -> None:
    ents = [ce("3", 0), ce("1", 2), ce("3", 4), ce("2", 6), ce("1", 8)]
    assert extract_custom_emoji_ids(ents) == ["3", "1", "2"]


def test_mixed_entities_and_invalid_ids() -> None:
    ents = [
        MessageEntity(type="bold", offset=0, length=5),
        ce("111", 6),
        MessageEntity(type="custom_emoji", offset=20, length=2),  # ID yo'q
        ce("abc<script>"),
        ce(""),
    ]
    assert extract_custom_emoji_ids(ents) == ["111"]


def test_caption_entities_and_utf16_text() -> None:
    msg = Message.model_validate(
        {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 1, "type": "private"},
            "caption": "Salom 👨‍👩‍👧 привет 🔥",
            "caption_entities": [{"type": "custom_emoji", "offset": 22, "length": 2, "custom_emoji_id": "77"}],
        }
    )
    assert extract_custom_emoji_ids(msg.caption_entities) == ["77"]


def test_sticker_to_item_filters() -> None:
    assert sticker_to_item(make_sticker("5", type_="regular")) is None
    assert sticker_to_item(make_sticker(None)) is None
    item = sticker_to_item(make_sticker("5", emoji=None, set_name="bad name!", video=True))
    assert item is not None and item.emoji is None and item.set_name is None and item.kind == "video"


# ---------- 6–9: pack detection ----------


async def test_one_pack_loaded_once() -> None:
    tg = FakeTelegram(sets={"A": make_set("A", ["1", "2", "3", "4"])})
    tg.stickers = {i: make_sticker(i, set_name="A") for i in ("1", "2", "3")}
    result = await service(tg).lookup(["1", "2", "3", "2"])
    assert tg.set_calls == ["A"]
    assert [p.name for p in result.packs] == ["A"]
    assert [e.custom_emoji_id for e in result.packs[0].items] == ["1", "2", "3", "4"]  # original tartib


async def test_multiple_packs() -> None:
    tg = FakeTelegram(
        stickers={"1": make_sticker("1", set_name="A"), "9": make_sticker("9", set_name="B")},
        sets={"A": make_set("A", ["1", "2"]), "B": make_set("B", ["9", "8"])},
    )
    result = await service(tg).lookup(["9", "1"])
    assert [p.name for p in result.packs] == ["B", "A"]


async def test_set_name_missing() -> None:
    tg = FakeTelegram(stickers={"1": make_sticker("1", set_name=None)})
    result = await service(tg).lookup(["1"])
    assert tg.set_calls == [] and result.packs == []
    packs = browsable_packs(result)
    assert len(packs) == 1 and packs[0].is_virtual and packs[0].items[0].custom_emoji_id == "1"


async def test_empty_pack_is_failed_not_invented() -> None:
    tg = FakeTelegram(stickers={"1": make_sticker("1", set_name="E")}, sets={"E": make_set("E", [])})
    result = await service(tg).lookup(["1"])
    assert result.packs == [] and result.failed_sets == ["E"]
    assert [o.custom_emoji_id for o in result.orphans] == ["1"]


async def test_regular_sticker_set_rejected() -> None:
    tg = FakeTelegram(
        stickers={"1": make_sticker("1", set_name="R")}, sets={"R": make_set("R", ["1"], sticker_type="regular")}
    )
    result = await service(tg).lookup(["1"])
    assert result.failed_sets == ["R"]


async def test_get_sticker_set_failure_keeps_emoji() -> None:
    tg = FakeTelegram(stickers={"1": make_sticker("1", set_name="Gone")})
    result = await service(tg).lookup(["1"])
    assert result.failed_sets == ["Gone"] and [o.custom_emoji_id for o in result.orphans] == ["1"]


async def test_lookup_failure_raises() -> None:
    with pytest.raises(EmojiLookupError):
        await service(FakeTelegram(fail_lookup=True)).lookup(["1"])


async def test_missing_and_unrequested_ids() -> None:
    tg = FakeTelegram(stickers={"1": make_sticker("1", set_name=None), "666": make_sticker("666", set_name=None)})

    class Liar(FakeBot):
        async def get_custom_emoji_stickers(self, custom_emoji_ids, request_timeout=None):  # type: ignore[override]
            return [tg.stickers["666"], tg.stickers["1"]]

    bot = Liar(tg)
    result = await EmojiService(bot, StickerSetService(bot)).lookup(["1", "404"])
    assert result.missing_ids == ["404"]
    assert [i.custom_emoji_id for i in result.requested] == ["1"]


async def test_non_custom_items_filtered_and_deduped() -> None:
    pack = make_set("A", ["1", "2"])
    pack.stickers.append(make_sticker("3", type_="regular", set_name="A"))
    pack.stickers.append(make_sticker(None, set_name="A"))
    pack.stickers.append(make_sticker("1", set_name="A"))
    tg = FakeTelegram(stickers={"1": make_sticker("1", set_name="A")}, sets={"A": pack})
    result = await service(tg).lookup(["1"])
    assert [e.custom_emoji_id for e in result.packs[0].items] == ["1", "2"]


async def test_cache_and_concurrent_dedupe() -> None:
    tg = FakeTelegram(stickers={"1": make_sticker("1", set_name="A")}, sets={"A": make_set("A", ["1"])})
    svc = service(tg)
    await asyncio.gather(*(svc.lookup(["1"]) for _ in range(10)))
    await svc.lookup(["1"])
    assert tg.set_calls == ["A"]


async def test_set_limit() -> None:
    n = MAX_SETS_PER_MESSAGE + 2
    tg = FakeTelegram(
        stickers={str(i): make_sticker(str(i), set_name=f"P{i}") for i in range(n)},
        sets={f"P{i}": make_set(f"P{i}", [str(i)]) for i in range(n)},
    )
    result = await service(tg).lookup([str(i) for i in range(n)])
    assert len(result.packs) == MAX_SETS_PER_MESSAGE and len(result.skipped_sets) == 2


async def test_large_pack() -> None:
    ids = [eid(i) for i in range(250)]
    tg = FakeTelegram(stickers={ids[0]: make_sticker(ids[0], set_name="Big")}, sets={"Big": make_set("Big", ids)})
    result = await service(tg).lookup([ids[0]])
    assert result.packs[0].total == 250
