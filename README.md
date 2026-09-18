# Custom Emoji Explorer Bot

Telegram bot. Unga Premium / Custom Emoji yuborasiz, bot quyidagilarni qiladi:

1. `custom_emoji_id` ni aniqlaydi (`MessageEntity.type == "custom_emoji"`);
2. `getCustomEmojiStickers` orqali emoji qaysi set'ga tegishli ekanini (`set_name`) topadi;
3. `getStickerSet` orqali pack'dagi barcha custom emoji'larni oladi;
4. ularni **native jadvalda** (Bot API rich message) 25 tadan ko'rsatadi: 5 ustun × 5 qator, har katakda raqam va emoji,
   tartib raqamli tugmalar bilan bir xil (ustunlar soni: `app/constants.py` → `TABLE_COLUMNS`);
5. raqamli tugma orqali emoji tanlashga imkon beradi;
6. tanlangan emoji ID'sini va Telegram tugmasida shu emoji'ni ikonka qilib ishlatadigan **tayyor kodni** beradi.
   Kod Python, JavaScript, TypeScript, PHP, Java, Go va cURL tillarida;
7. ID va kodni bir bosishda nusxalash (`CopyTextButton`) hamda **Button Preview** imkonini beradi.

> Screenshotlar: `docs/screenshots/explorer.png`, `detail.png`, `code.png` (joy qoldirilgan)

## Oqim

```text
Custom Emoji ─► Pack: yuborilgan emoji + ID (nusxalash tugmasi) ─► 25 ta emoji jadvali (5×5)
   ─► 25 ta raqamli tugma + [Oldingi] [p / P] [Keyingi] + [Ro'yxat yaratish] [Jadval (.txt)] + [Admin]
   ─► Emoji tafsiloti (ID, pack, turi) ─► Python / JS / TS / PHP / Java / Go / cURL
   ─► Kodni nusxalash / fayl ─► Button Preview ─► Jadvalga qaytish (aynan o'sha sahifa)
```

Navigatsiya bitta xabarni tahrirlash (`editMessageText`) orqali ishlaydi, chatga ortiqcha xabar yuborilmaydi.
Yangi xabar faqat fayl so'ralganda yuboriladi.

## Talablar

- Python 3.12+ (serverda 3.14 bilan tekshirilgan)
- aiogram 3.31.0 (Telegram Bot API 10.3)
- python-dotenv 1.2.3
- testlar uchun pytest 9.1.1 va pytest-asyncio 1.4.0

Ma'lumotlar bazasi yo'q. Pack'lar TTL keshda (10 daqiqa, ko'pi bilan 512 ta), sessiyalar xotirada saqlanadi
(1 soat, ko'pi bilan 10 000 foydalanuvchi).

## Bot yaratish (BotFather)

1. [@BotFather](https://t.me/BotFather) → `/newbot` → nom va `..._bot` bilan tugaydigan username kiriting.
2. Berilgan tokenni `.env` ga yozing. Token oshkor bo'lsa, `/revoke` bilan yangilang.

## O'rnatish

```bash
git clone <repo-url> telegram-emoji-explorer
cd telegram-emoji-explorer
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux / macOS:

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
cp .env.example .env      # Windows: copy .env.example .env
```

`.env`:

```env
BOT_TOKEN=123456789:AA...
LOG_LEVEL=INFO
CACHE_TTL_SECONDS=600
ADMIN_ID=7000454062   # "Admin" tugmasi uchun (ixtiyoriy)
```

`ADMIN_ID` berilsa, jadval ostida **Admin** tugmasi chiqadi va admin profilini ochadi. Havola bot ishga tushganda
`getChat(ADMIN_ID)` orqali aniqlanadi: username bo'lsa `https://t.me/<username>`, aks holda `tg://user?id=`.
`tg://user?id=` havolasi adminning maxfiylik sozlamasi ruxsat bersagina ishlaydi, aks holda tugma yashiriladi.
Admin botga kamida bir marta /start bosgan bo'lishi kerak.

## Ishga tushirish

```bash
python main.py
```

`Ctrl+C` / `SIGTERM` bilan to'g'ri to'xtaydi. Buyruqlar: `/start`, `/help`, `/cancel`.

## Testlar

```bash
pytest -v
```

Testlar haqiqiy aiogram `Dispatcher` orqali ishlaydi, Telegram o'rniga soxta server (`tests/conftest.py`) turadi.
U rich xabarni rad etish, ikonkani olib tashlash, "message is not modified", o'chirilgan xabar kabi holatlarni ham taqlid qiladi.

Qamrov:
- parsing, pack aniqlash, kesh;
- pagination chegaralari (0…997);
- jadval algoritmi;
- yuborilgan emoji bo'limi va nusxalash tugmasi;
- orqaga navigatsiya (4-sahifa → #72 → Python → jadval → 4-sahifa);
- 7 ta kod generatori (Python kodi `ast` bilan tekshiriladi, cURL JSON'i parse qilinadi, Go kodi `gofmt`/`go vet`/`go build` bilan tekshirilgan);
- callback_data ≤ 64 bayt;
- eskirgan va begona sessiya;
- HTML escape;
- nusxalash fallback'i;
- "UI'da Unicode emoji yo'q" auditi.

## Arxitektura

```text
app/
├── bot.py                      # Dispatcher, DI, logging (token redaksiyasi), xato handler, polling
├── config.py                   # .env
├── constants.py                # EMOJIS_PER_PAGE=25, TABLE_COLUMNS=5, SELECT_COLUMNS=5
├── premium_emojis.py           # UI premium emoji registry (yagona manba) + validatsiya
├── views.py                    # ekranlar: HTML + native rich jadval + klaviatura
├── models/emoji.py             # EmojiItem, EmojiPack, LookupResult
├── handlers/
│   ├── start.py                # /start /help /cancel, qayta boshlash
│   ├── emoji_input.py          # emoji qabul qilish -> explorer / pack tanlash
│   ├── pagination.py           # sahifalar, pack ro'yxati, ID fayli
│   ├── emoji_select.py         # emoji tafsiloti
│   ├── code_generator.py       # kod, kod fayli, Button Preview
│   └── common.py               # sessiya/egalik tekshiruvi
├── services/
│   ├── emoji_service.py        # entity -> ID -> getCustomEmojiStickers -> pack'lar
│   ├── sticker_set_service.py  # getStickerSet + TTL kesh + so'rovlarni birlashtirish
│   ├── cache_service.py        # TTLCache (hajmi cheklangan)
│   ├── session_service.py      # user_id -> Session (sid bilan)
│   ├── code_generator_service.py / code_templates.py
│   └── presenter.py            # yuborish/tahrirlash + Telegram imkoniyatlari bo'yicha fallback
├── keyboards/                  # PremiumButtonFactory, explorer/detail/code/pagination klaviaturalari
└── utils/                      # formatting, pagination, table, callback_data, telegram_limits
```

**Callback data.** Callback'da set nomi va emoji ID saqlanmaydi. Unda faqat sessiya ID, pack raqami, sahifa,
emoji raqami va til bor, masalan `c:0GzR6A:0:72:py:4`. Shuning uchun "Jadvalga qaytish" har doim aynan
o'sha sahifaga qaytaradi.
Sessiya foydalanuvchiga bog'langan: boshqa foydalanuvchi, eski menyu yoki noma'lum formatdagi tugma
"Bu menyu eskirgan" ekranini ochadi.

**Yangi til qo'shish** (C#, Kotlin, Rust, Telethon, Pyrogram...): `services/code_templates.py` ga shablon yozing va
`code_generator_service.LANGUAGES` ga bitta yozuv qo'shing. Registry'ga ham rol qo'shish mumkin.

## Premium UI emoji'lari

Bot UI'sida oddiy Unicode emoji **ishlatilmaydi** (`tests/test_premium_ui.py` buni tekshiradi). Ikonkalar faqat
premium custom emoji orqali ko'rsatiladi:
- matnda `<tg-emoji emoji-id="...">`;
- tugmada `icon_custom_emoji_id`.

ID sozlanmagan bo'lsa, faqat toza matn chiqadi.

ID'larni o'rnatish:

1. Botga kerakli premium emoji'ni yuboring → "ID'ni nusxalash".
2. Yoki `app/premium_emojis.py` dagi `PREMIUM_EMOJIS` ni to'ldiring, yoki `.env` ga
   `EMOJI_<ROL>_ID=...` yozing (masalan `EMOJI_COPY_ID=5368...`). `.env` ustun turadi.
3. Botni qayta ishga tushiring. Ishga tushishda ID'lar `getCustomEmojiStickers` bilan tekshiriladi.
   Telegram tanimagan ID o'chiriladi. `<tg-emoji>` uchun majburiy alternativ belgi ham Telegram'dan olinadi.

Rollar: ADMIN, LIST_CREATE, HOME, PACK, VIEW, LIST, COPY, FILE, BACK, TABLE, NEXT, PREVIOUS, PAGE, CODE, PREVIEW, PYTHON, JAVASCRIPT, TYPESCRIPT,
PHP, JAVA, GO, CURL, SUCCESS, ERROR, WARNING, INFO, REFRESH, SETTINGS, LOADING.

Hozir sozlangan: Python, JavaScript, TypeScript, PHP, Java, Go, cURL (`dev_emojis_solid`) hamda Oldingi, Keyingi,
sahifa ko'rsatkichi, "Jadvalga qaytish", barcha nusxalash tugmalari, "Ro'yxat" / "Kodni fayl sifatida olish" /
"Packlar ro'yxati" (`tgiosicons`) ikonkalari.

Kelajakdagi `/set_ui_pack` uchun `PremiumEmojiRegistry.assign(role, id, alternative)` tayyor.

## Telegram Bot API cheklovlari

Bot API 10.3 / aiogram 3.31.0 da tekshirilgan (2026-09-18).

| Imkoniyat | Holat |
|---|---|
| `MessageEntity.custom_emoji_id` | native |
| `getCustomEmojiStickers` | native, bir so'rovda ko'pi bilan **200** ID |
| `Sticker.set_name`, `getStickerSet` | native; set o'chirilgan/bo'sh bo'lsa pack uydirilmaydi, faqat emoji'ning o'zi ko'rsatiladi |
| Jadval | native: `sendRichMessage` + `InputRichBlockTable` (Bot API 10.x). Telegram rad etsa, avtomatik `<code>` raqamli HTML jadval |
| Custom emoji matnda (`<tg-emoji>`) | native, lekin quyidagi cheklov bilan |
| `icon_custom_emoji_id` | `InlineKeyboardButton` **va** `KeyboardButton` (reply) da mavjud; cheklov quyida |
| `CopyTextButton` | native, **1–256 belgi**. Uzun kod uchun "Button kodini nusxalash" (faqat tugma qismi) va "Kodni fayl sifatida olish" |
| `callback_data` | 64 bayt, ixcham format bilan hal qilingan |
| Xabar matni | 4096 belgi (entity'lardan keyin), barcha ekranlar eng yomon holatda tekshirilgan |

**Custom emoji va `icon_custom_emoji_id` cheklovi (Telegram).** Bot custom emoji'ni matnda va tugma ikonkasida
faqat ikki holatda ishlata oladi:
- botga Fragment'da qo'shimcha username sotib olingan bo'lsa;
- bot egasida Telegram Premium bo'lsa. Bu holatda ruxsat faqat botning private, group va supergroup chatlarga
  to'g'ridan-to'g'ri yuborgan xabarlariga tegishli.

Aks holda Telegram premium elementni rad etadi yoki jimgina olib tashlaydi. Bot ikkala holatni ham aniqlaydi
(qaytgan xabardagi entity/markup bo'yicha) va shunday ishlaydi:
- ikonkalar o'chiriladi va xabar toza matn bilan qayta chiziladi. Telegram olib tashlagan emoji o'rnida
  qoladigan Unicode alternativ belgi ko'rinmaydi;
- 1 soatdan keyin imkoniyat qayta sinaladi.

Button Preview esa fallback'siz ishlaydi va natijani (ikonka ko'rindi yoki yo'q) aniq aytadi.

**Rich message.** Bu Telegram'ning yangi imkoniyati. Eski Telegram ilovalari jadvalni ko'rsatmasligi mumkin.
Server rad etsa, bot HTML jadvalga o'tadi.

## Deployment (Ubuntu, systemd)

```bash
sudo useradd --system --home /opt/telegram-emoji-bot --shell /usr/sbin/nologin emojibot
sudo mkdir -p /opt/telegram-emoji-bot && sudo chown emojibot: /opt/telegram-emoji-bot
sudo -u emojibot git clone <repo-url> /opt/telegram-emoji-bot
cd /opt/telegram-emoji-bot
sudo -u emojibot python3 -m venv .venv
sudo -u emojibot .venv/bin/pip install -r requirements.txt
sudo -u emojibot cp .env.example .env && sudo chmod 600 .env   # tokenni yozing
```

`/etc/systemd/system/telegram-emoji-bot.service`:

```ini
[Unit]
Description=Custom Emoji Explorer Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
User=emojibot
Group=emojibot
WorkingDirectory=/opt/telegram-emoji-bot
EnvironmentFile=/opt/telegram-emoji-bot/.env
ExecStart=/opt/telegram-emoji-bot/.venv/bin/python main.py
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=10
TimeoutStopSec=20
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadOnlyPaths=/opt/telegram-emoji-bot

[Install]
WantedBy=multi-user.target
```

Token faqat `.env` da turadi (`chmod 600`), unit faylga yozilmaydi. Bot polling rejimida ishlaydi va port ochmaydi.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-emoji-bot
journalctl -u telegram-emoji-bot -f
```

Log formati: `INFO | user=123 | set=animals | emojis=120`, `user=123 | page=3`, `user=123 | selected=47`,
`user=123 | language=py`. Token logga tushmaydi (maxsus filtr bilan himoyalangan).
