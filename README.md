# Telegram Custom Emoji ID Bot

Botga Telegram Premium / Custom Emoji yuborasiz. Bot:

1. xabardagi har bir custom emoji'ning `custom_emoji_id` sini aniqlaydi;
2. `getCustomEmojiStickers` orqali emoji ma'lumotini (emoji, `set_name`, turi) oladi;
3. `getStickerSet` orqali shu packdagi **barcha** custom emoji'larni oladi;
4. natijani nusxalashga qulay ko'rinishda chiqaradi (`<code>` ID'lar, `📋 ID larni olish` tugmasi, `copy_text` tugmasi).

Bir xabarda bir nechta emoji yuborish mumkin: takrorlanganlari olib tashlanadi, turli packlardagi emoji'lar `SET 1`, `SET 2`, … ko'rinishida guruhlanadi.

## Texnologiyalar

- Python 3.12+ (serverda 3.14 bilan tekshirilgan)
- aiogram 3.31.0 (Telegram Bot API 10.3)
- python-dotenv 1.2.3

Ma'lumotlar bazasi ishlatilmaydi: setlar 10 daqiqalik in-memory TTL keshda saqlanadi.

## Tuzilma

```text
app/
├── bot.py                  # Bot/Dispatcher, logging, error handler, polling
├── config.py               # .env dan sozlamalar
├── handlers/
│   ├── start.py            # /start, /help
│   └── emoji.py            # emoji xabarlari va callback tugmalar
├── services/
│   └── emoji_service.py    # entity parsing, getCustomEmojiStickers, getStickerSet, kesh
├── keyboards/
│   └── inline.py
└── utils/
    ├── cache.py            # TTL kesh
    └── formatting.py       # HTML escape, xabarlarni xavfsiz bo'laklash
tests/                      # unittest (stdlib)
main.py
```

## Bot yaratish (BotFather)

1. Telegram'da [@BotFather](https://t.me/BotFather) ni oching.
2. `/newbot` yuboring, bot nomi va `..._bot` bilan tugaydigan username kiriting.
3. BotFather bergan tokenni `.env` fayliga yozing. Tokenni hech kimga bermang.
   Token oshkor bo'lsa, `/revoke` bilan yangisini oling.

## O'rnatish

```bash
git clone <repo-url>
cd PremiumEmojBot

python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Keyin:

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env`:

```env
BOT_TOKEN=123456789:AA...
LOG_LEVEL=INFO        # ixtiyoriy
SET_CACHE_TTL=600     # ixtiyoriy, soniya
```

## Ishga tushirish

```bash
python main.py
```

`Ctrl+C` yoki `SIGTERM` bilan to'g'ri to'xtaydi.

### Serverda (systemd)

`/etc/systemd/system/premiumemoji-bot.service`:

```ini
[Unit]
Description=Premium Emoji ID Telegram bot (aiogram polling)
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/root/TelegramBot/PremiumEmojBot
ExecStart=/root/TelegramBot/PremiumEmojBot/.venv/bin/python main.py
Environment=PYTHONUNBUFFERED=1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl enable --now premiumemoji-bot
journalctl -u premiumemoji-bot -f      # loglar
systemctl restart premiumemoji-bot     # kod o'zgargandan keyin
```

Bot polling rejimida ishlaydi, port ochmaydi.

## Testlar

```bash
python -m unittest discover -s tests -t . -v
```

Testlar oddiy matn, oddiy Unicode emoji, bitta/bir nechta/takroriy custom emoji, bitta packdan bir nechta emoji, turli packlar, `set_name` bo'lmagan javob, Telegram API xatosi, 200 ta va undan katta packlar, HTML escape va xabarlarni bo'laklash holatlarini qamrab oladi.

## Telegram Bot API cheklovlari

- `getCustomEmojiStickers` bir so'rovda ko'pi bilan **200** ta ID qabul qiladi. Shuning uchun bitta xabardan ko'pi bilan 200 ta emoji tekshiriladi.
- `set_name` Telegram javobida bo'lmasa (yoki set o'chirilgan bo'lsa), pack ma'lumoti **uydirilmaydi**: faqat emoji'ning o'z ID'si ko'rsatiladi va ogohlantirish chiqadi.
- `copy_text` tugmasi (Bot API 7.11+) faqat **1–256** belgini nusxalaydi. Shuning uchun u faqat foydalanuvchi yuborgan ID'lar uchun chiqadi, butun pack uchun esa `📋 ID larni olish` tugmasi `<pre>` bloklarni yuboradi.
- Bot o'z xabarlarida premium emoji'ni (`<tg-emoji>`) va tugma ikonkasini (`icon_custom_emoji_id`) faqat Fragment'dan qo'shimcha username sotib olgan bo'lsa yoki bot egasida Telegram Premium bo'lsa ko'rsata oladi. Shuning uchun natijada har bir emoji'ning oddiy Unicode ekvivalenti (`emoji` maydoni) ko'rsatiladi.
- Telegram xabar limiti 4096 belgi: natija 50 tadan bo'laklarga ajratiladi. Katta packlar uchun (masalan 997 ta emoji) bir nechta xabar yuboriladi va flood limitga urilmaslik uchun ular orasiga kichik pauza qo'yiladi.
- Bitta xabardan ko'pi bilan 10 ta turli set yuklanadi. Qolgan setlardagi emoji'lar faqat ID bilan ko'rsatiladi.
- `📋 ID larni olish` natijalari xotirada 1 soat saqlanadi. Bot qayta ishga tushsa, emoji'ni qayta yuborish kerak.
