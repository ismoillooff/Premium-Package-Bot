import ast
import json
import re

import pytest

from app.services.code_generator_service import (
    LANGUAGES,
    CodeGeneratorService,
    CodeLanguage,
    UnsupportedLanguageError,
    parse_language,
)

EMOJI_ID = "5368324170671202286"
REAL_TOKEN_RE = re.compile(r"\d{6,}:[A-Za-z0-9_-]{30,}")

gen = CodeGeneratorService()


@pytest.mark.parametrize("language", list(CodeLanguage))
def test_every_language_uses_real_field_and_no_token(language: CodeLanguage) -> None:
    code = gen.generate(language, EMOJI_ID)
    assert EMOJI_ID in code.code and EMOJI_ID in code.snippet
    field = "iconCustomEmojiId" if language is CodeLanguage.JAVA else (
        ".icon(" if language in (CodeLanguage.JAVASCRIPT, CodeLanguage.TYPESCRIPT) else "icon_custom_emoji_id"
    )
    assert field in code.code
    assert not REAL_TOKEN_RE.search(code.code)
    assert "BOT_TOKEN" in code.code
    assert code.snippet_copy_supported


def test_python_is_valid_aiogram_code() -> None:
    code = gen.generate(CodeLanguage.PYTHON, EMOJI_ID).code
    ast.parse(code)
    assert "from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup" in code
    assert 'os.environ["BOT_TOKEN"]' in code


def test_python_snippet_matches_aiogram_constructor() -> None:
    from aiogram.types import InlineKeyboardButton  # noqa: F401 — snippet shu nomlar bilan bajariladi

    snippet = gen.generate(CodeLanguage.PYTHON, EMOJI_ID).snippet
    button = eval(snippet, {"InlineKeyboardButton": InlineKeyboardButton})  # noqa: S307 — o'zimiz generatsiya qilgan kod
    assert button.icon_custom_emoji_id == EMOJI_ID and button.callback_data == "open"


def test_javascript_grammy() -> None:
    code = gen.generate(CodeLanguage.JAVASCRIPT, EMOJI_ID).code
    assert 'require("grammy")' in code
    assert f'.icon("{EMOJI_ID}")' in code
    assert "process.env.BOT_TOKEN" in code


def test_typescript_grammy_typed() -> None:
    code = gen.generate(CodeLanguage.TYPESCRIPT, EMOJI_ID).code
    assert 'import { Bot, InlineKeyboard } from "grammy";' in code
    assert f'const EMOJI_ID: string = "{EMOJI_ID}";' in code
    assert "const keyboard: InlineKeyboard" in code


def test_php_payload() -> None:
    code = gen.generate(CodeLanguage.PHP, EMOJI_ID).code
    assert code.startswith("<?php")
    assert f"'icon_custom_emoji_id' => '{EMOJI_ID}'" in code
    assert "json_encode($payload" in code and "getenv('BOT_TOKEN')" in code
    assert code.count("[") == code.count("]") and code.count("(") == code.count(")")
    assert 'bot{$token}/sendMessage' in code


def test_java_telegrambots() -> None:
    code = gen.generate(CodeLanguage.JAVA, EMOJI_ID).code
    assert f'.iconCustomEmojiId("{EMOJI_ID}")' in code
    assert "new InlineKeyboardRow(button)" in code
    assert 'System.getenv("BOT_TOKEN")' in code
    assert code.count("{") == code.count("}")


def test_go_standard_library() -> None:
    code = gen.generate(CodeLanguage.GO, EMOJI_ID).code
    assert code.startswith("// Go") and "package main" in code
    assert 'IconCustomEmojiID string `json:"icon_custom_emoji_id"`' in code
    assert f'IconCustomEmojiID: "{EMOJI_ID}"' in code
    assert 'os.Getenv("BOT_TOKEN")' in code
    assert code.count("{") == code.count("}") and code.count("(") == code.count(")")
    body = code.split("package main", 1)[1]
    assert all(not line.startswith(" ") for line in body.splitlines())  # gofmt: indent faqat tab


def test_curl_valid_json_and_placeholder() -> None:
    code = gen.generate(CodeLanguage.CURL, EMOJI_ID).code
    assert '"https://api.telegram.org/bot<BOT_TOKEN>/sendMessage"' in code
    body = code.split("-d '", 1)[1].rsplit("'", 1)[0]
    payload = json.loads(body)
    button = payload["reply_markup"]["inline_keyboard"][0][0]
    assert button == {"text": "Open", "callback_data": "open", "icon_custom_emoji_id": EMOJI_ID}


def test_escaping_of_button_text() -> None:
    evil = "a\"b'c\\d$e"
    py = gen.generate(CodeLanguage.PYTHON, EMOJI_ID, button_text=evil).code
    ast.parse(py)
    curl = gen.generate(CodeLanguage.CURL, EMOJI_ID, button_text=evil).code
    assert "'\\''" in curl  # shell uchun ' escape
    php = gen.generate(CodeLanguage.PHP, EMOJI_ID, button_text=evil).code
    assert "'a\"b\\'c\\\\d$e'" in php


def test_invalid_id_and_language() -> None:
    with pytest.raises(ValueError):
        gen.generate(CodeLanguage.PYTHON, "12; rm -rf /")
    with pytest.raises(UnsupportedLanguageError):
        parse_language("rust")


def test_copy_fallback_flags() -> None:
    for language in CodeLanguage:
        code = gen.generate(language, EMOJI_ID)
        # To'liq kodlar 256 dan uzun: copy tugmasi o'rniga fayl + tugma qismi.
        assert code.copy_supported is (len(code.code) <= 256)
    assert set(LANGUAGES) == set(CodeLanguage)
