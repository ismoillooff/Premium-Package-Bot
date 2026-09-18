"""Tanlangan custom emoji bilan Telegram tugmasi yaratish kodini generatsiya qilish.

Yangi til qo'shish: code_templates.py ga shablon yozing va LANGUAGES ga bitta yozuv qo'shing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from app.constants import SAMPLE_BUTTON_TEXT, SAMPLE_CALLBACK_DATA
from app.premium_emojis import PremiumEmoji
from app.services import code_templates
from app.utils.telegram_limits import COPY_TEXT_MAX_CHARS

_EMOJI_ID_RE = re.compile(r"^\d{1,32}$")


class CodeLanguage(StrEnum):
    PYTHON = "py"
    JAVASCRIPT = "js"
    TYPESCRIPT = "ts"
    PHP = "php"
    JAVA = "java"
    GO = "go"
    CURL = "curl"


@dataclass(frozen=True, slots=True)
class LanguageSpec:
    language: CodeLanguage
    label: str  # tugmadagi nom
    title: str  # kod sahifasi sarlavhasi
    library: str
    pre_language: str  # <code class="language-...">
    file_name: str
    icon: PremiumEmoji
    template: code_templates.Template


LANGUAGES: dict[CodeLanguage, LanguageSpec] = {
    spec.language: spec
    for spec in (
        LanguageSpec(
            CodeLanguage.PYTHON, "Python", "Python / aiogram 3.x", "aiogram 3.31",
            "python", "custom_emoji_button.py", PremiumEmoji.PYTHON, code_templates.python_aiogram,
        ),
        LanguageSpec(
            CodeLanguage.JAVASCRIPT, "JavaScript", "JavaScript / grammY", "grammY 1.46 (Node.js)",
            "javascript", "custom_emoji_button.js", PremiumEmoji.JAVASCRIPT, code_templates.javascript_grammy,
        ),
        LanguageSpec(
            CodeLanguage.TYPESCRIPT, "TypeScript", "TypeScript / grammY", "grammY 1.46 (type-safe)",
            "typescript", "custom_emoji_button.ts", PremiumEmoji.TYPESCRIPT, code_templates.typescript_grammy,
        ),
        LanguageSpec(
            CodeLanguage.PHP, "PHP", "PHP / cURL (Bot API)", "ext-curl, Bot API JSON",
            "php", "custom_emoji_button.php", PremiumEmoji.PHP, code_templates.php_curl,
        ),
        LanguageSpec(
            CodeLanguage.JAVA, "Java", "Java / TelegramBots", "TelegramBots 10.3.0",
            "java", "CustomEmojiButton.java", PremiumEmoji.JAVA, code_templates.java_telegrambots,
        ),
        LanguageSpec(
            CodeLanguage.GO, "Go", "Go / net/http (Bot API)", "Go 1.21+ standart kutubxona",
            "go", "custom_emoji_button.go", PremiumEmoji.GO, code_templates.go_net_http,
        ),
        LanguageSpec(
            CodeLanguage.CURL, "cURL", "cURL / Bot API", "curl (sendMessage)",
            "bash", "custom_emoji_button.sh", PremiumEmoji.CURL, code_templates.curl_raw,
        ),
    )
}


class UnsupportedLanguageError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class GeneratedCode:
    language: CodeLanguage
    title: str
    library: str
    pre_language: str
    file_name: str
    code: str
    snippet: str  # faqat tugma qismi

    @property
    def copy_supported(self) -> bool:
        """To'liq kod CopyTextButton limitiga (1–256 belgi) sig'adimi."""
        return 0 < len(self.code) <= COPY_TEXT_MAX_CHARS

    @property
    def snippet_copy_supported(self) -> bool:
        return 0 < len(self.snippet) <= COPY_TEXT_MAX_CHARS


def parse_language(value: str) -> CodeLanguage:
    try:
        return CodeLanguage(value)
    except ValueError:
        raise UnsupportedLanguageError(value) from None


class CodeGeneratorService:
    def generate(
        self,
        language: CodeLanguage,
        emoji_id: str,
        button_text: str = SAMPLE_BUTTON_TEXT,
        callback_data: str = SAMPLE_CALLBACK_DATA,
    ) -> GeneratedCode:
        if not _EMOJI_ID_RE.fullmatch(emoji_id or ""):
            raise ValueError("invalid custom emoji id")
        spec = LANGUAGES.get(language)
        if spec is None:
            raise UnsupportedLanguageError(str(language))
        code, snippet = spec.template(emoji_id, button_text, callback_data)
        return GeneratedCode(
            language=language,
            title=spec.title,
            library=spec.library,
            pre_language=spec.pre_language,
            file_name=spec.file_name,
            code=code,
            snippet=snippet,
        )
