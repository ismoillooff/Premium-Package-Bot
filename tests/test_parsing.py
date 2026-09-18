import unittest

from aiogram.types import Message, MessageEntity

from app.services.emoji_service import extract_custom_emoji_ids, sticker_to_info
from tests.helpers import ce, make_sticker


class ExtractIdsTests(unittest.TestCase):
    def test_plain_text(self) -> None:
        self.assertEqual(extract_custom_emoji_ids(None), [])
        self.assertEqual(extract_custom_emoji_ids([]), [])

    def test_unicode_emoji_has_no_custom_entity(self) -> None:
        # Oddiy 😀 uchun Telegram custom_emoji entity bermaydi.
        msg = Message.model_validate(
            {"message_id": 1, "date": 0, "chat": {"id": 1, "type": "private"}, "text": "😀"}
        )
        self.assertEqual(extract_custom_emoji_ids(msg.entities), [])

    def test_single(self) -> None:
        self.assertEqual(extract_custom_emoji_ids([ce("5368324170671202286")]), ["5368324170671202286"])

    def test_multiple_and_duplicates_keep_order(self) -> None:
        ents = [ce("3", 0), ce("1", 2), ce("3", 4), ce("2", 6), ce("1", 8)]
        self.assertEqual(extract_custom_emoji_ids(ents), ["3", "1", "2"])

    def test_mixed_entities(self) -> None:
        ents = [
            MessageEntity(type="bold", offset=0, length=5),
            ce("111", 6),
            MessageEntity(type="url", offset=9, length=10),
            MessageEntity(type="custom_emoji", offset=20, length=2),  # ID yo'q — skip
        ]
        self.assertEqual(extract_custom_emoji_ids(ents), ["111"])

    def test_invalid_id_skipped(self) -> None:
        self.assertEqual(extract_custom_emoji_ids([ce("abc<script>"), ce(""), ce("42")]), ["42"])

    def test_real_message_with_utf16_offsets(self) -> None:
        # Custom emoji'dan oldin surrogate-pair emoji va kirill matn: offset'lar UTF-16 da.
        text = "Salom 👨‍👩‍👧 привет 🔥 va ❤️"
        msg = Message.model_validate(
            {
                "message_id": 1,
                "date": 0,
                "chat": {"id": 1, "type": "private"},
                "text": text,
                "entities": [
                    {"type": "custom_emoji", "offset": 22, "length": 2, "custom_emoji_id": "900"},
                    {"type": "custom_emoji", "offset": 28, "length": 2, "custom_emoji_id": "901"},
                ],
            }
        )
        self.assertEqual(extract_custom_emoji_ids(msg.entities), ["900", "901"])

    def test_caption_entities(self) -> None:
        msg = Message.model_validate(
            {
                "message_id": 1,
                "date": 0,
                "chat": {"id": 1, "type": "private"},
                "caption": "🔥",
                "caption_entities": [{"type": "custom_emoji", "offset": 0, "length": 2, "custom_emoji_id": "77"}],
            }
        )
        self.assertEqual(extract_custom_emoji_ids(msg.caption_entities), ["77"])


class StickerToInfoTests(unittest.TestCase):
    def test_custom_emoji(self) -> None:
        info = sticker_to_info(make_sticker("5", emoji="😎", set_name="P", video=True))
        assert info is not None
        self.assertEqual((info.custom_emoji_id, info.emoji, info.set_name, info.kind), ("5", "😎", "P", "video"))

    def test_regular_sticker_rejected(self) -> None:
        self.assertIsNone(sticker_to_info(make_sticker("5", type_="regular")))

    def test_missing_id_rejected(self) -> None:
        self.assertIsNone(sticker_to_info(make_sticker(None)))

    def test_missing_emoji_and_bad_set_name(self) -> None:
        info = sticker_to_info(make_sticker("5", emoji=None, set_name="bad name!"))
        assert info is not None
        self.assertIsNone(info.emoji)
        self.assertIsNone(info.set_name)


if __name__ == "__main__":
    unittest.main()
