"""Callback data hajmi va Dispatcher orqali to'liq UX ssenariylari (soxta Telegram server bilan)."""

from aiogram.methods import AnswerCallbackQuery, SendDocument
from aiogram.types import BufferedInputFile

from app.utils.callback_data import (
    CodeCb,
    CodeFileCb,
    EmojiCb,
    ListCreateCb,
    PacksCb,
    PageCb,
    PreviewCb,
    TableFileCb,
)
from app.utils.telegram_limits import CALLBACK_DATA_MAX_BYTES
from tests.conftest import OTHER_USER_ID, FakeTelegram, Harness, ce, eid, make_set, make_sticker, pack_tg


def test_callback_data_within_limit_worst_case() -> None:
    sid = "A" * 8
    samples = [
        PageCb(s=sid, k=99, p=9999),
        EmojiCb(s=sid, k=99, i=99999, p=9999),
        CodeCb(s=sid, k=99, i=99999, l="curl", p=9999),
        CodeFileCb(s=sid, k=99, i=99999, l="java"),
        PreviewCb(s=sid, k=99, i=99999, p=9999),
        PacksCb(s=sid),
        ListCreateCb(s=sid, k=99, i=99999, p=9999),
        TableFileCb(s=sid, k=99, p=9999),
    ]
    for cb in samples:
        assert len(cb.pack().encode()) <= CALLBACK_DATA_MAX_BYTES


def _all_callback_sizes(h: Harness) -> list[int]:
    return [len(b.callback_data.encode()) for b in h.buttons() if b.callback_data]


# ---------- 41. asosiy UX acceptance ----------


async def test_acceptance_main_flow() -> None:
    h = Harness(pack_tg(120))
    await h.send_text("🔥", [ce(eid(0))])

    # Loading xabari tahrirlanib, native jadval bo'ldi (bitta xabar — spam yo'q).
    assert len(h.tg.messages) == 1
    explorer_id = h.last_message_id
    rich = h.last.rich
    table = next(b for b in rich.blocks if b.type == "table")
    assert len(table.cells) == 5 and all(len(row) == 5 for row in table.cells)
    number, _, emoji = table.cells[0][0].text
    assert number.text == "1" and emoji.custom_emoji_id == eid(0)
    assert [row[0].text[0].text for row in table.cells] == ["1", "6", "11", "16", "21"]
    texts = [b.text for b in h.buttons()]
    assert texts[:25] == [str(i) for i in range(1, 26)]
    assert texts[25:27] == ["1 / 5", "Keyingi"]
    assert "Hammasini ko'rish" not in texts
    # Yuborilgan emoji: jadvaldan oldin ID, va nusxalash tugmasi.
    blocks = [b.type for b in rich.blocks]
    assert any(
        getattr(t, "text", None) == eid(0) for b in rich.blocks[: blocks.index("table")] for t in (b.text if isinstance(b.text, list) else [])
    )
    assert h.button("Yuborilgan emojni nusxalash").copy_text.text == eid(0)
    assert all(size <= 64 for size in _all_callback_sizes(h))

    # [1] -> detail (edit)
    await h.click(h.button("1").callback_data)
    assert h.last_message_id == explorer_id and len(h.tg.messages) == 1
    assert "<b>Custom Emoji</b>" in h.last.text and f"<code>{eid(0)}</code>" in h.last.text
    assert h.button("ID'ni nusxalash").copy_text.text == eid(0)
    for label in ("Python", "JavaScript", "TypeScript", "PHP", "Java", "Go", "cURL", "Button Preview", "Jadvalga qaytish"):
        h.button(label)

    # Python -> kod (edit)
    await h.click(h.button("Python").callback_data)
    assert "Python / aiogram 3.x" in h.last.text
    assert '<pre><code class="language-python">' in h.last.text
    assert "icon_custom_emoji_id=&quot;" not in h.last.text  # HTML escape faqat <>&
    assert f'icon_custom_emoji_id="{eid(0)}"' in h.last.text
    assert h.button("Button kodini nusxalash").copy_text.text.count(eid(0)) == 1
    h.button("Kodni fayl sifatida olish")
    h.button("Emoji ma'lumotlari")

    # Jadvalga qaytish -> aynan o'sha pack va sahifa
    await h.click(h.button("Jadvalga qaytish").callback_data)
    assert h.last.rich is not None and h.last_message_id == explorer_id

    # Har bir callback javoblandi (spinner qolmaydi).
    assert len(h.answers()) == 3


# ---------- 42. "Hammasini ko'rish" + pagination + back navigation ----------


async def test_pagination_and_back_to_same_page() -> None:
    h = Harness(pack_tg(120))
    await h.send_text("🔥", [ce(eid(0))])
    texts = [b.text for b in h.buttons()]
    assert texts[:25] == [str(i) for i in range(1, 26)]
    assert texts[25:27] == ["1 / 5", "Keyingi"]

    await h.click(h.button("Keyingi").callback_data)
    await h.click(h.button("Keyingi").callback_data)
    await h.click(h.button("Keyingi").callback_data)  # 4-sahifa
    texts = [b.text for b in h.buttons()]
    assert texts[:25] == [str(i) for i in range(76, 101)]
    assert texts[25:28] == ["Oldingi", "4 / 5", "Keyingi"]
    table = next(b for b in h.last.rich.blocks if b.type == "table")
    assert len(table.cells) == 5
    assert [c.text[0].text for c in table.cells[0]] == ["76", "77", "78", "79", "80"]
    assert table.cells[-1][-1].text[0].text == "100"

    # Yuborilgan emoji ma'lumoti va nusxa tugmasi boshqa sahifada ham turadi.
    h.button("Yuborilgan emojni nusxalash")

    # emoji #90 -> Python -> Jadvalga qaytish => 4-sahifa
    await h.click(h.button("90").callback_data)
    assert "<b>№ 90</b>" in h.last.text
    await h.click(h.button("Python").callback_data)
    await h.click(h.button("Emoji ma'lumotlari").callback_data)
    assert "<b>№ 90</b>" in h.last.text
    await h.click(h.button("Jadvalga qaytish").callback_data)
    assert [b.text for b in h.buttons()][25:28] == ["Oldingi", "4 / 5", "Keyingi"]

    # Oxirgi sahifa: 101–120 (20 ta)
    await h.click(h.button("Keyingi").callback_data)
    assert [b.text for b in h.buttons()][20:22] == ["Oldingi", "5 / 5"]


async def test_small_pack_quick_selector() -> None:
    h = Harness(pack_tg(8))
    await h.send_text("🔥", [ce(eid(3))])
    assert [b.text for b in h.buttons()] == [
        *map(str, range(1, 9)),
        "Yuborilgan emojni nusxalash",
        "Ro'yxat yaratish",
        "Jadval",
    ]


# ---------- xato holatlari ----------


async def test_normal_text_and_unicode_emoji() -> None:
    h = Harness(FakeTelegram())
    await h.send_text("hello")
    assert "Custom Emoji topilmadi" in h.last.text
    await h.send_text("😀")
    assert "Custom Emoji topilmadi" in h.last.text


async def test_lookup_failure_friendly() -> None:
    h = Harness(FakeTelegram(fail_lookup=True))
    await h.send_text("🔥", [ce(eid(0))])
    assert "xatolik yuz berdi" in h.last.text and "boom" not in h.last.text


async def test_unknown_id_not_invented() -> None:
    h = Harness(FakeTelegram())
    await h.send_text("🔥", [ce("404")])
    assert "ma'lumot bermadi" in h.last.text and "<code>404</code>" in h.last.text


async def test_multiple_packs_selector() -> None:
    tg = FakeTelegram(
        stickers={"1": make_sticker("1", set_name="A"), "9": make_sticker("9", set_name="B")},
        sets={"A": make_set("A", ["1", "2"], title="Animals"), "B": make_set("B", ["9", "8", "7"], title="Reactions")},
    )
    h = Harness(tg)
    await h.send_text("x y", [ce("1"), ce("9", 2), ce("1", 4)])
    assert "2 ta Emoji Pack topildi" in h.last.text
    assert [b.text for b in h.buttons()] == ["Animals — 2", "Reactions — 3"]
    await h.click(h.button("Reactions — 3").callback_data)
    assert h.last.rich is not None
    h.button("Packlar ro'yxati")


async def test_expired_session_and_foreign_user() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("🔥", [ce(eid(0))])
    first_button = h.button("1").callback_data

    # Boshqa foydalanuvchi bu menyuni boshqara olmaydi.
    await h.click(first_button, user_id=OTHER_USER_ID)
    assert "Bu menyu eskirgan" in h.last.text
    h.button("Boshidan boshlash")

    # Yangi emoji yuborilgach eski menyu eskiradi.
    await h.send_text("🔥", [ce(eid(1))])
    await h.click(first_button, message_id=min(h.tg.messages))
    assert "Bu menyu eskirgan" in h.tg.messages[min(h.tg.messages)].text


async def test_invalid_callback_values() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("🔥", [ce(eid(0))])
    sid = h.button("1").callback_data.split(":")[1]
    mid = h.last_message_id
    await h.click(EmojiCb(s=sid, k=0, i=999, p=1).pack(), message_id=mid)  # index yo'q
    assert "eskirgan" in h.last.text
    await h.send_text("🔥", [ce(eid(0))])
    sid = h.button("1").callback_data.split(":")[1]
    await h.click(PageCb(s=sid, k=5, p=1).pack())  # pack yo'q
    assert "eskirgan" in h.last.text
    await h.send_text("🔥", [ce(eid(0))])
    sid = h.button("1").callback_data.split(":")[1]
    await h.click(PageCb(s=sid, k=0, p=77).pack())  # sahifa chegaradan tashqari -> oxirgi sahifa
    assert "2 / 2" in [b.text for b in h.buttons()]
    await h.click(CodeCb(s=sid, k=0, i=1, l="rust", p=1).pack())
    assert any(a.show_alert for a in h.answers())


async def test_restart_and_cancel() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("🔥", [ce(eid(0))])
    old = h.button("1").callback_data
    await h.send_text("/cancel")
    assert "Sessiya tozalandi" in h.last.text
    await h.click(old, message_id=min(h.tg.messages))
    assert "eskirgan" in h.tg.messages[min(h.tg.messages)].text
    await h.click(h.button("Boshidan boshlash", min(h.tg.messages)).callback_data, message_id=min(h.tg.messages))
    assert "Custom Emoji Explorer" in h.tg.messages[min(h.tg.messages)].text


async def test_deleted_message_sends_new() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("🔥", [ce(eid(0))])
    mid = h.last_message_id
    data = h.button("1").callback_data
    h.tg.deleted.add(mid)
    await h.click(data, message_id=mid)
    assert h.last_message_id != mid and "<b>Custom Emoji</b>" in h.last.text


async def test_not_modified_does_not_crash() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("🔥", [ce(eid(0))])
    data = h.button("1").callback_data
    await h.click(data)
    before = h.last.text
    await h.click(data)  # bir xil ekran -> "message is not modified"
    assert h.last.text == before


async def test_rich_rejected_falls_back_to_html_table() -> None:
    h = Harness(pack_tg(7, reject_rich=True))
    await h.send_text("🔥", [ce(eid(0))])
    text = h.last.text
    assert h.last.rich is None and "Animals Premium" in text
    lines = [line for line in text.splitlines() if line.startswith("<code>")]
    assert len(lines) == 2  # 7 ta -> 5 + 2
    assert lines[0].count("<code>") == 5 and lines[1].count("<code>") == 2
    assert lines[1].startswith("<code>6</code>") and "<code>7</code>" in lines[1]
    assert not h.registry.rich.supported


async def test_code_file_and_ids_file() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("🔥", [ce(eid(0))])
    explorer = h.last_message_id
    await h.click(h.button("1", explorer).callback_data, message_id=explorer)
    await h.click(h.button("Java", explorer).callback_data, message_id=explorer)
    await h.click(h.button("Kodni fayl sifatida olish", explorer).callback_data, message_id=explorer)
    assert explorer in h.tg.messages  # kod fayli xabarni o'chirmaydi
    docs = [c for c in h.tg.calls if isinstance(c, SendDocument)]
    assert len(docs) == 1
    (java_file,) = (d.document for d in docs)
    assert isinstance(java_file, BufferedInputFile)
    assert java_file.filename == "CustomEmojiButton.java" and eid(0).encode() in java_file.data


async def test_button_preview_real_icon() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("🔥", [ce(eid(0))])
    await h.click(h.button("5").callback_data)
    await h.click(h.button("Button Preview").callback_data)
    assert h.button("Test button").icon_custom_emoji_id == eid(4)
    assert "Button Preview" in h.last.text


async def test_button_preview_rejected_or_dropped() -> None:
    h = Harness(pack_tg(30, reject_icons=True))
    await h.send_text("🔥", [ce(eid(0))])
    await h.click(h.button("1").callback_data)
    await h.click(h.button("Button Preview").callback_data)
    assert "Button Preview yaratilmadi" in h.last.text

    h2 = Harness(pack_tg(30, drop_icons=True))
    await h2.send_text("🔥", [ce(eid(0))])
    await h2.click(h2.button("1").callback_data)
    await h2.click(h2.button("Button Preview").callback_data)
    assert "tugma ikonkasini ko'rsatmadi" in h2.last.text


async def test_every_callback_answered() -> None:
    h = Harness(pack_tg(45))
    await h.send_text("🔥", [ce(eid(0))])
    clicks = 0
    for label in ("Keyingi", "30", "PHP", "Emoji ma'lumotlari", "Jadvalga qaytish"):
        await h.click(h.button(label).callback_data)
        clicks += 1
    assert len([c for c in h.tg.calls if isinstance(c, AnswerCallbackQuery)]) == clicks


async def test_multiple_sent_emojis_copy_all() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("x y z", [ce(eid(3)), ce(eid(7), 2), ce(eid(3), 4)])
    assert h.button("Yuborilgan emojilarni nusxalash").copy_text.text == f"{eid(3)}\n{eid(7)}"


async def test_old_callback_format_is_expired_not_stuck() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("x", [ce(eid(0))])
    await h.click("e:oldsid:0:1:q:1")  # eski formatdagi (rejimli) tugma
    assert "eskirgan" in h.last.text
    assert len(h.answers()) == 1


async def test_list_create_button_left_of_table_button() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("x", [ce(eid(0))])
    await h.click(h.button("3").callback_data)
    screens = ["detail"]
    for label in ("Python", "Emoji ma'lumotlari", "Button Preview"):
        rows = h.tg.messages[h.last_message_id].markup.inline_keyboard
        assert [b.text for b in rows[-1]] == ["Ro'yxat yaratish", "Jadvalga qaytish"], screens[-1]
        await h.click(h.button(label).callback_data)
        screens.append(label)
    rows = h.tg.messages[h.last_message_id].markup.inline_keyboard
    assert [b.text for b in rows[-1]] == ["Ro'yxat yaratish", "Jadvalga qaytish"]

    before = h.last.text
    await h.click(h.button("Ro'yxat yaratish").callback_data)
    assert h.answers()[-1].text == "Ro'yxat yaratish tez orada qo'shiladi"
    assert h.last.text == before  # xabar o'zgarmaydi


async def test_explorer_list_create_and_table_row() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("x", [ce(eid(0))])
    rows = h.last.markup.inline_keyboard
    row = next(r for r in rows if any(b.text == "Jadval" for b in r))
    assert [b.text for b in row] == ["Ro'yxat yaratish", "Jadval"]
    await h.click(h.button("Ro'yxat yaratish").callback_data)
    assert h.answers()[-1].text == "Ro'yxat yaratish tez orada qo'shiladi"


async def test_table_button_deletes_message_sends_txt_and_returns_to_same_page() -> None:
    h = Harness(pack_tg(60))
    await h.send_text("x", [ce(eid(0))])
    await h.click(h.button("Keyingi").callback_data)  # 2-sahifa
    explorer_id = h.last_message_id
    await h.click(h.button("Jadval").callback_data)

    # Jadval xabari o'chirildi, o'rniga .txt jadval + "Jadvalga qaytish".
    assert explorer_id in h.tg.deleted and explorer_id not in h.tg.messages
    doc_id = h.last_message_id
    doc = h.tg.messages[doc_id].document
    assert doc.filename == "Animals_jadval.txt"
    text = doc.data.decode()
    lines = text.splitlines()
    assert lines[0] == "Animals Premium (Animals)" and lines[1] == "60 ta Custom Emoji"
    assert lines[3].split(" | ") == [" №", "ID                 ", "Emoji"]
    assert lines[5] == f" 1 | {eid(0)} | 🔥" and lines[-1] == f"60 | {eid(59)} | 🔥"
    assert len(lines) == 5 + 60
    assert [b.text for b in h.buttons(doc_id)] == ["Jadvalga qaytish"]

    # Jadvalga qaytish: fayl o'chadi, aynan 2-sahifa qaytadi.
    await h.click(h.button("Jadvalga qaytish", doc_id).callback_data, message_id=doc_id)
    assert doc_id in h.tg.deleted
    assert h.last.rich is not None
    assert "2 / 3" in [b.text for b in h.buttons()]


async def test_admin_button_opens_admin_profile() -> None:
    h = Harness(pack_tg(30))
    h.dp["views"].admin_url = "https://t.me/admin_username"
    await h.send_text("x", [ce(eid(0))])
    rows = h.last.markup.inline_keyboard
    assert [b.text for b in rows[-1]] == ["Admin"]  # eng pastki qator
    admin = rows[-1][0]
    assert admin.url == "https://t.me/admin_username" and admin.callback_data is None
    assert "Ro'yxat" not in [b.text for b in h.buttons()]


async def test_admin_button_hidden_without_admin() -> None:
    h = Harness(pack_tg(30))
    await h.send_text("x", [ce(eid(0))])
    assert "Admin" not in [b.text for b in h.buttons()]
