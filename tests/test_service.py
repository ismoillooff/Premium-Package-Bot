import asyncio
import unittest

from app.services.emoji_service import MAX_SETS_PER_MESSAGE, EmojiLookupError, EmojiService
from tests.helpers import FakeApi, make_set, make_sticker


class LookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_emoji_with_full_pack(self) -> None:
        api = FakeApi(
            stickers={"1": make_sticker("1", set_name="PackA")},
            sets={"PackA": make_set("PackA", ["1", "2", "3"])},
        )
        result = await EmojiService(api).lookup(["1"])
        self.assertEqual([i.custom_emoji_id for i in result.requested], ["1"])
        self.assertEqual(len(result.packs), 1)
        self.assertEqual([e.custom_emoji_id for e in result.packs[0].emojis], ["1", "2", "3"])
        self.assertEqual(result.orphans, [])
        self.assertEqual(result.all_ids, ["1", "2", "3"])

    async def test_same_pack_requested_once(self) -> None:
        api = FakeApi(
            stickers={i: make_sticker(i, set_name="PackA") for i in ("1", "2", "3")},
            sets={"PackA": make_set("PackA", ["1", "2", "3", "4"])},
        )
        result = await EmojiService(api).lookup(["1", "2", "3", "2"])
        self.assertEqual(api.set_calls, ["PackA"])
        self.assertEqual(api.lookup_calls, [["1", "2", "3"]])  # duplicate olib tashlangan
        self.assertEqual(len(result.packs), 1)

    async def test_different_packs_grouped(self) -> None:
        api = FakeApi(
            stickers={"1": make_sticker("1", set_name="PackA"), "9": make_sticker("9", set_name="PackB")},
            sets={"PackA": make_set("PackA", ["1", "2"]), "PackB": make_set("PackB", ["9", "8"])},
        )
        result = await EmojiService(api).lookup(["9", "1"])
        self.assertEqual([p.name for p in result.packs], ["PackB", "PackA"])
        self.assertEqual(result.all_ids, ["9", "8", "1", "2"])

    async def test_no_set_name(self) -> None:
        api = FakeApi(stickers={"1": make_sticker("1", set_name=None)})
        result = await EmojiService(api).lookup(["1"])
        self.assertEqual(api.set_calls, [])
        self.assertEqual(result.packs, [])
        self.assertEqual([o.custom_emoji_id for o in result.orphans], ["1"])

    async def test_lookup_api_error(self) -> None:
        with self.assertRaises(EmojiLookupError):
            await EmojiService(FakeApi(fail_lookup=True)).lookup(["1"])

    async def test_set_fetch_error_keeps_emoji(self) -> None:
        api = FakeApi(stickers={"1": make_sticker("1", set_name="Gone")})
        result = await EmojiService(api).lookup(["1"])
        self.assertEqual(result.failed_sets, ["Gone"])
        self.assertEqual([o.custom_emoji_id for o in result.orphans], ["1"])
        self.assertEqual(result.all_ids, ["1"])

    async def test_missing_ids_reported_not_invented(self) -> None:
        api = FakeApi(stickers={"1": make_sticker("1", set_name=None)})
        result = await EmojiService(api).lookup(["1", "404"])
        self.assertEqual(result.missing_ids, ["404"])
        self.assertNotIn("404", result.all_ids)

    async def test_unrequested_ids_in_response_ignored(self) -> None:
        class Liar(FakeApi):
            async def get_custom_emoji_stickers(self, custom_emoji_ids):  # type: ignore[override]
                return [make_sticker("666", set_name=None), make_sticker("1", set_name=None)]

        result = await EmojiService(Liar()).lookup(["1"])
        self.assertEqual(result.all_ids, ["1"])

    async def test_non_custom_items_filtered_from_set(self) -> None:
        pack = make_set("PackA", ["1", "2"])
        pack.stickers.append(make_sticker("3", type_="regular", set_name="PackA"))
        pack.stickers.append(make_sticker(None, set_name="PackA"))
        pack.stickers.append(make_sticker("1", set_name="PackA"))  # duplicate
        api = FakeApi(stickers={"1": make_sticker("1")}, sets={"PackA": pack})
        result = await EmojiService(api).lookup(["1"])
        self.assertEqual([e.custom_emoji_id for e in result.packs[0].emojis], ["1", "2"])

    async def test_regular_sticker_set_rejected(self) -> None:
        api = FakeApi(
            stickers={"1": make_sticker("1", set_name="Reg")},
            sets={"Reg": make_set("Reg", ["1"], sticker_type="regular")},
        )
        result = await EmojiService(api).lookup(["1"])
        self.assertEqual(result.packs, [])
        self.assertEqual(result.failed_sets, ["Reg"])

    async def test_cache_between_lookups(self) -> None:
        api = FakeApi(stickers={"1": make_sticker("1")}, sets={"PackA": make_set("PackA", ["1"])})
        service = EmojiService(api, set_cache_ttl=600)
        await service.lookup(["1"])
        await service.lookup(["1"])
        self.assertEqual(api.set_calls, ["PackA"])

    async def test_concurrent_requests_share_one_fetch(self) -> None:
        api = FakeApi(stickers={"1": make_sticker("1")}, sets={"PackA": make_set("PackA", ["1"])}, delay=0.05)
        service = EmojiService(api, set_cache_ttl=0)  # keshsiz — faqat in-flight birlashtirish
        results = await asyncio.gather(*(service.lookup(["1"]) for _ in range(5)))
        self.assertEqual(api.set_calls, ["PackA"])
        self.assertTrue(all(len(r.packs) == 1 for r in results))

    async def test_set_limit(self) -> None:
        n = MAX_SETS_PER_MESSAGE + 2
        stickers = {str(i): make_sticker(str(i), set_name=f"P{i}") for i in range(n)}
        sets = {f"P{i}": make_set(f"P{i}", [str(i)]) for i in range(n)}
        result = await EmojiService(FakeApi(stickers=stickers, sets=sets)).lookup(list(stickers))
        self.assertEqual(len(result.packs), MAX_SETS_PER_MESSAGE)
        self.assertEqual(result.skipped_sets, [f"P{MAX_SETS_PER_MESSAGE}", f"P{MAX_SETS_PER_MESSAGE + 1}"])
        self.assertEqual(len(result.orphans), 2)

    async def test_large_pack(self) -> None:
        ids = [str(5368324170671200000 + i) for i in range(200)]
        api = FakeApi(stickers={ids[0]: make_sticker(ids[0], set_name="Big")}, sets={"Big": make_set("Big", ids)})
        result = await EmojiService(api).lookup([ids[0]])
        self.assertEqual(len(result.packs[0].emojis), 200)


if __name__ == "__main__":
    unittest.main()
