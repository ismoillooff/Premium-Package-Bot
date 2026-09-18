"""Har bir til uchun kod shablonlari.

Barcha shablonlar Telegram Bot API'ning InlineKeyboardButton.icon_custom_emoji_id
maydonidan foydalanadi. Kutubxona versiyalari 2026-09-18 da tekshirilgan:
  * aiogram 3.31.0            — InlineKeyboardButton(icon_custom_emoji_id=...)
  * grammY 1.46.0             — InlineKeyboard().text(...).icon(...)  (@grammyjs/types 5.0.0)
  * TelegramBots 10.3.0 (Java)— InlineKeyboardButton.builder().iconCustomEmojiId(...)
  * PHP / Go / cURL           — to'g'ridan-to'g'ri Bot API JSON so'rovi (Go: faqat standart kutubxona)
Real token hech qachon kodga qo'yilmaydi: muhit o'zgaruvchisi yoki <BOT_TOKEN>.

Har bir shablon: (emoji_id, text, callback_data) -> (to'liq kod, faqat tugma qismi).
Qiymatlar tilning string-literal qoidalariga ko'ra escape qilinadi.
"""

from __future__ import annotations

import json
from collections.abc import Callable


def _dq(value: str) -> str:
    """Python/JS/TS/Java uchun qo'shtirnoqli literal (JSON escape bu tillarda ham to'g'ri)."""
    return json.dumps(value, ensure_ascii=False)


def _php(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def python_aiogram(emoji_id: str, text: str, data: str) -> tuple[str, str]:
    button = (
        "InlineKeyboardButton(\n"
        f"    text={_dq(text)},\n"
        f"    callback_data={_dq(data)},\n"
        f"    icon_custom_emoji_id={_dq(emoji_id)},\n"
        ")"
    )
    code = f'''# pip install "aiogram>=3.31"
import asyncio
import os

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text={_dq(text)},
                callback_data={_dq(data)},
                icon_custom_emoji_id={_dq(emoji_id)},
            )
        ]
    ]
)


async def main() -> None:
    bot = Bot(token=os.environ["BOT_TOKEN"])
    try:
        await bot.send_message(
            chat_id=int(os.environ["CHAT_ID"]),
            text="Custom emoji button:",
            reply_markup=keyboard,
        )
    finally:
        await bot.session.close()


asyncio.run(main())
'''
    return code, button


def javascript_grammy(emoji_id: str, text: str, data: str) -> tuple[str, str]:
    button = f"new InlineKeyboard()\n  .text({_dq(text)}, {_dq(data)})\n  .icon({_dq(emoji_id)});"
    code = f"""// npm i grammy@^1.46
const {{ Bot, InlineKeyboard }} = require("grammy");

const bot = new Bot(process.env.BOT_TOKEN);

const keyboard = new InlineKeyboard()
  .text({_dq(text)}, {_dq(data)})
  .icon({_dq(emoji_id)});

bot.command("start", (ctx) =>
  ctx.reply("Custom emoji button:", {{ reply_markup: keyboard }}),
);

bot.start();
"""
    return code, button


def typescript_grammy(emoji_id: str, text: str, data: str) -> tuple[str, str]:
    button = f"new InlineKeyboard()\n  .text({_dq(text)}, {_dq(data)})\n  .icon({_dq(emoji_id)});"
    code = f"""// npm i grammy@^1.46
import {{ Bot, InlineKeyboard }} from "grammy";

const token = process.env.BOT_TOKEN;
if (!token) throw new Error("BOT_TOKEN is not set");

const bot = new Bot(token);

const EMOJI_ID: string = {_dq(emoji_id)};

const keyboard: InlineKeyboard = new InlineKeyboard()
  .text({_dq(text)}, {_dq(data)})
  .icon(EMOJI_ID);

bot.command("start", async (ctx) => {{
  await ctx.reply("Custom emoji button:", {{ reply_markup: keyboard }});
}});

bot.start();
"""
    return code, button


def php_curl(emoji_id: str, text: str, data: str) -> tuple[str, str]:
    button = (
        "[\n"
        f"    'text' => {_php(text)},\n"
        f"    'callback_data' => {_php(data)},\n"
        f"    'icon_custom_emoji_id' => {_php(emoji_id)},\n"
        "]"
    )
    code = f"""<?php
$token = getenv('BOT_TOKEN');
$chatId = getenv('CHAT_ID');

$payload = [
    'chat_id' => $chatId,
    'text' => 'Custom emoji button:',
    'reply_markup' => [
        'inline_keyboard' => [
            [
                [
                    'text' => {_php(text)},
                    'callback_data' => {_php(data)},
                    'icon_custom_emoji_id' => {_php(emoji_id)},
                ],
            ],
        ],
    ],
];

$ch = curl_init("https://api.telegram.org/bot{{$token}}/sendMessage");
curl_setopt_array($ch, [
    CURLOPT_POST => true,
    CURLOPT_HTTPHEADER => ['Content-Type: application/json'],
    CURLOPT_POSTFIELDS => json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
    CURLOPT_RETURNTRANSFER => true,
]);
$response = curl_exec($ch);
if ($response === false) {{
    throw new RuntimeException(curl_error($ch));
}}
echo $response, PHP_EOL;
"""
    return code, button


def java_telegrambots(emoji_id: str, text: str, data: str) -> tuple[str, str]:
    button = (
        "InlineKeyboardButton.builder()\n"
        f"        .text({_dq(text)})\n"
        f"        .callbackData({_dq(data)})\n"
        f"        .iconCustomEmojiId({_dq(emoji_id)})\n"
        "        .build();"
    )
    code = f"""// Maven: org.telegram:telegrambots-client:10.3.0
import org.telegram.telegrambots.client.okhttp.OkHttpTelegramClient;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.InlineKeyboardMarkup;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardButton;
import org.telegram.telegrambots.meta.api.objects.replykeyboard.buttons.InlineKeyboardRow;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;
import org.telegram.telegrambots.meta.generics.TelegramClient;

public class CustomEmojiButton {{
    public static void main(String[] args) throws TelegramApiException {{
        TelegramClient client = new OkHttpTelegramClient(System.getenv("BOT_TOKEN"));

        InlineKeyboardButton button = InlineKeyboardButton.builder()
                .text({_dq(text)})
                .callbackData({_dq(data)})
                .iconCustomEmojiId({_dq(emoji_id)})
                .build();

        SendMessage message = SendMessage.builder()
                .chatId(System.getenv("CHAT_ID"))
                .text("Custom emoji button:")
                .replyMarkup(InlineKeyboardMarkup.builder()
                        .keyboardRow(new InlineKeyboardRow(button))
                        .build())
                .build();

        client.execute(message);
    }}
}}
"""
    return code, button


def go_net_http(emoji_id: str, text: str, data: str) -> tuple[str, str]:
    button = (
        "InlineKeyboardButton{\n"
        f"\tText:              {_dq(text)},\n"
        f"\tCallbackData:      {_dq(data)},\n"
        f"\tIconCustomEmojiID: {_dq(emoji_id)},\n"
        "}"
    )
    code = f"""// Go 1.21+, faqat standart kutubxona: go run custom_emoji_button.go
package main

import (
\t"bytes"
\t"encoding/json"
\t"fmt"
\t"io"
\t"net/http"
\t"os"
)

type InlineKeyboardButton struct {{
\tText              string `json:"text"`
\tCallbackData      string `json:"callback_data"`
\tIconCustomEmojiID string `json:"icon_custom_emoji_id"`
}}

func main() {{
\tpayload := map[string]any{{
\t\t"chat_id": os.Getenv("CHAT_ID"),
\t\t"text":    "Custom emoji button:",
\t\t"reply_markup": map[string]any{{
\t\t\t"inline_keyboard": [][]InlineKeyboardButton{{{{
\t\t\t\t{{Text: {_dq(text)}, CallbackData: {_dq(data)}, IconCustomEmojiID: {_dq(emoji_id)}}},
\t\t\t}}}},
\t\t}},
\t}}

\tbody, err := json.Marshal(payload)
\tif err != nil {{
\t\tpanic(err)
\t}}
\turl := "https://api.telegram.org/bot" + os.Getenv("BOT_TOKEN") + "/sendMessage"
\tresp, err := http.Post(url, "application/json", bytes.NewReader(body))
\tif err != nil {{
\t\tpanic(err)
\t}}
\tdefer resp.Body.Close()

\tout, err := io.ReadAll(resp.Body)
\tif err != nil {{
\t\tpanic(err)
\t}}
\tfmt.Println(string(out))
}}
"""
    return code, button


def curl_raw(emoji_id: str, text: str, data: str) -> tuple[str, str]:
    button_obj = {"text": text, "callback_data": data, "icon_custom_emoji_id": emoji_id}
    payload = {
        "chat_id": "<CHAT_ID>",
        "text": "Custom emoji button:",
        "reply_markup": {"inline_keyboard": [[button_obj]]},
    }
    body = json.dumps(payload, ensure_ascii=False, indent=2).replace("'", "'\\''")
    code = (
        'curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \\\n'
        '  -H "Content-Type: application/json" \\\n'
        f"  -d '{body}'\n"
    )
    return code, json.dumps(button_obj, ensure_ascii=False, indent=2)


Template = Callable[[str, str, str], tuple[str, str]]
