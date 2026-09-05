import os
import unittest
from unittest.mock import patch

from utils.i18n import (
    SUPPORTED_LANGUAGES,
    all_default_conversation_titles,
    default_conversation_title,
    default_language_from_env,
    default_system_prompt,
    is_default_conversation_title,
    missing_translation_keys,
    normalize_language,
    translate,
)
from utils.prompt_manager import PromptManager


class I18nTests(unittest.TestCase):
    def test_supported_languages_have_matching_keys(self):
        self.assertEqual(missing_translation_keys(), {})

    def test_normalize_language(self):
        self.assertEqual(normalize_language("en-US"), "en")
        self.assertEqual(normalize_language("JA"), "ja")
        self.assertEqual(normalize_language("fr"), "")
        self.assertEqual(normalize_language(""), "")

    def test_translate_falls_back_and_formats(self):
        self.assertEqual(translate("input.send", "ja"), "📤 送信")
        self.assertEqual(translate("input.send", "en"), "📤 Send")
        self.assertIn("12", translate("chat.truncated", "en", limit=12))
        self.assertEqual(translate("missing.key", "en"), "missing.key")

    def test_default_titles_and_prompts_are_localized(self):
        self.assertEqual(default_conversation_title("ja"), "新しい会話")
        self.assertEqual(default_conversation_title("en"), "New conversation")
        self.assertTrue(is_default_conversation_title("New conversation"))
        self.assertIn("New conversation", all_default_conversation_titles())
        self.assertIn("AI assistant", default_system_prompt("en"))
        self.assertEqual(default_system_prompt("ja"), PromptManager.DEFAULT_SYSTEM_PROMPT)

    def test_env_default_language(self):
        with patch.dict(os.environ, {"APP_DISPLAY_LANGUAGE": "en-GB"}, clear=False):
            self.assertEqual(default_language_from_env(), "en")

    def test_prompt_manager_uses_display_language_labels(self):
        messages = PromptManager.format_messages_for_api(
            [{"role": "user", "content": "hello"}],
            file_content="attached",
            lang="en",
        )
        file_message = messages[1]["content"]
        self.assertIn("Attached file contents", file_message)
        self.assertNotIn("添付ファイルの内容", file_message)
        self.assertEqual(messages[0]["content"], default_system_prompt("en"))
        self.assertEqual(set(SUPPORTED_LANGUAGES), {"ja", "en"})


if __name__ == "__main__":
    unittest.main()
