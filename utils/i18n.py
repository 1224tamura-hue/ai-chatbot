import os
from typing import Any, Iterable, Optional

DEFAULT_LANGUAGE = "ja"
SUPPORTED_LANGUAGES = ("ja", "en")
LANGUAGE_LABELS = {
    "ja": "日本語",
    "en": "English",
}

DEFAULT_CONVERSATION_TITLES = {
    "ja": "新しい会話",
    "en": "New conversation",
}

DEFAULT_SYSTEM_PROMPTS = {
    "ja": "あなたは親切で有能なAIアシスタントです。ユーザーの質問に丁寧に答えてください。",
    "en": "You are a helpful and capable AI assistant. Answer the user's questions clearly and politely.",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ja": {
        "language.label": "表示言語",
        "language.caption": "アプリの表示言語を切り替えます。",
        "page.title": "🤖 AI Chatbot",
        "sidebar.conversations": "💬 会話",
        "sidebar.new_conversation": "➕ 新規会話",
        "sidebar.archive": "📦 アーカイブ ({count})",
        "sidebar.archive_caption": "履歴会話をまとめて管理できます。",
        "sidebar.archive_empty": "アーカイブはありません。",
        "sidebar.advanced": "⚙️ 詳細設定",
        "sidebar.advanced_caption": "通常は未変更で利用できます。",
        "sidebar.system_prompt": "システムプロンプト",
        "sidebar.temperature": "Temperature",
        "sidebar.max_tokens": "Max Tokens",
        "sidebar.model": "モデル",
        "draft_label": "下書き（未送信）",
        "default_conversation_title": "新しい会話",
        "api_key_missing": "❌ .envファイルにOPENAI_API_KEYが設定されていません。",
        "api_key_help": "📝 .env または Streamlit Secrets に OPENAI_API_KEY を設定してください。",
        "model_caption": (
            "モデル: {model} / 履歴送信: 直近{history}件 / "
            "RAG候補: 上位{rag}件 / 応答上限: {tokens} tokens"
        ),
        "input.heading": "💬 文字入力",
        "input.label": "メッセージを入力",
        "input.placeholder": "社内規程について質問してください",
        "input.send": "📤 送信",
        "input.empty_warning": "メッセージを入力してください。",
        "audio.heading": "🎤 音声入力",
        "audio.input_label": "マイクで録音して文字起こしできます",
        "audio.record_text": "録音/停止",
        "audio.recognizing": "音声認識中...",
        "audio.recognize_error": "❌ 音声認識エラー: {error}",
        "audio.edit_caption": "文字起こし結果（必要なら修正して送信してください）",
        "audio.edit_label": "音声入力の文字起こし",
        "audio.send_edited": "✅ 修正して送信",
        "audio.clear": "🗑️ 文字起こしをクリア",
        "audio.send_empty": "送信する文字を入力してください。",
        "extras.heading": "🧩 補助機能",
        "extras.file_uploader": "テキストファイル (.txt, .md) またはPDF (.pdf) をアップロード",
        "extras.file_loaded": "✅ ファイル '{name}' を読み込みました ({chars} 文字)",
        "extras.file_preview": "📄 ファイル内容を確認",
        "extras.file_error": "❌ ファイル読み込みエラー: {error}",
        "extras.file_pending": "次回送信時にファイル内容を参照します（送信後に自動クリア）。",
        "extras.play_latest": "🔊 最新回答を音声再生",
        "extras.summarizing": "要約生成中...",
        "extras.generating_audio": "音声生成中...",
        "extras.played": "✅ 音声を再生しました",
        "extras.audio_error": "❌ 音声出力エラー: {error}",
        "extras.no_ai_message": "音声再生できるAI回答がまだありません。",
        "chat.truncated": "表示負荷軽減のため、最新{limit}件のみ表示しています。",
        "policy.expander": "📚 参照規程 ({count}件)",
        "policy.empty": "関連する規程候補は見つかりませんでした。",
        "policy.item": "- `{policy_code}` {title} / 第{section_no}項 {item_title}",
        "error.response_failed": (
            "❌ 応答生成に失敗しました。"
            "\n原因: {error}"
            "\n対処: APIキー・モデル設定・ネットワーク状態を確認して再試行してください。"
        ),
        "spinner.generating": "AI応答生成中...",
        "summary.system_prompt": "あなたは要約の専門家です。次の文章を日本語で簡潔に要約してください。",
        "policy.context_header": "[社内規程検索結果]",
        "policy.context_intro": "以下は社内規程データベースから抽出した関連候補です。",
        "policy.context_item": (
            "{idx}. {policy_code} / {title} / 第{section_no}項 {item_title}: {item_text}"
        ),
        "policy.context_guidance": (
            "回答方針: 関連する規程がある場合はその内容を優先し、規程コードと項番を明示して回答する。"
            "表示言語が日本語なので、ユーザーには日本語で回答してください。"
        ),
        "prompt.file_prefix": "[添付ファイルの内容]",
        "prompt.file_suffix": "[以下、ユーザーからのメッセージ]",
        "whisper.language": "ja",
    },
    "en": {
        "language.label": "Display language",
        "language.caption": "Switch the language used in this app.",
        "page.title": "🤖 AI Chatbot",
        "sidebar.conversations": "💬 Conversations",
        "sidebar.new_conversation": "➕ New conversation",
        "sidebar.archive": "📦 Archive ({count})",
        "sidebar.archive_caption": "Review and manage archived conversations.",
        "sidebar.archive_empty": "There are no archived conversations.",
        "sidebar.advanced": "⚙️ Advanced settings",
        "sidebar.advanced_caption": "You can usually leave these unchanged.",
        "sidebar.system_prompt": "System prompt",
        "sidebar.temperature": "Temperature",
        "sidebar.max_tokens": "Max Tokens",
        "sidebar.model": "Model",
        "draft_label": "Draft (unsent)",
        "default_conversation_title": "New conversation",
        "api_key_missing": "❌ OPENAI_API_KEY is not set in the .env file.",
        "api_key_help": "📝 Set OPENAI_API_KEY in .env or Streamlit Secrets.",
        "model_caption": (
            "Model: {model} / History sent: last {history} / "
            "RAG candidates: top {rag} / Response cap: {tokens} tokens"
        ),
        "input.heading": "💬 Text input",
        "input.label": "Enter a message",
        "input.placeholder": "Ask about company policies",
        "input.send": "📤 Send",
        "input.empty_warning": "Please enter a message.",
        "audio.heading": "🎤 Voice input",
        "audio.input_label": "Record with your microphone to transcribe",
        "audio.record_text": "Record / Stop",
        "audio.recognizing": "Transcribing audio...",
        "audio.recognize_error": "❌ Speech recognition error: {error}",
        "audio.edit_caption": "Transcript (edit before sending if needed)",
        "audio.edit_label": "Voice transcript",
        "audio.send_edited": "✅ Send edited text",
        "audio.clear": "🗑️ Clear transcript",
        "audio.send_empty": "Please enter text to send.",
        "extras.heading": "🧩 Extra tools",
        "extras.file_uploader": "Upload a text file (.txt, .md) or PDF (.pdf)",
        "extras.file_loaded": "✅ Loaded file '{name}' ({chars} characters)",
        "extras.file_preview": "📄 Preview file contents",
        "extras.file_error": "❌ File read error: {error}",
        "extras.file_pending": "The file will be used on the next send, then cleared automatically.",
        "extras.play_latest": "🔊 Play latest answer",
        "extras.summarizing": "Generating summary...",
        "extras.generating_audio": "Generating audio...",
        "extras.played": "✅ Playing audio",
        "extras.audio_error": "❌ Audio output error: {error}",
        "extras.no_ai_message": "There is no AI answer to play yet.",
        "chat.truncated": "Showing the latest {limit} messages to keep the page responsive.",
        "policy.expander": "📚 Referenced policies ({count})",
        "policy.empty": "No related policy candidates were found.",
        "policy.item": "- `{policy_code}` {title} / Section {section_no} {item_title}",
        "error.response_failed": (
            "❌ Failed to generate a response."
            "\nCause: {error}"
            "\nFix: Check the API key, model settings, and network, then try again."
        ),
        "spinner.generating": "Generating AI response...",
        "summary.system_prompt": "You are a summarization expert. Summarize the following text concisely in English.",
        "policy.context_header": "[Company policy search results]",
        "policy.context_intro": "The following candidates were retrieved from the company policy database.",
        "policy.context_item": (
            "{idx}. {policy_code} / {title} / Section {section_no} {item_title}: {item_text}"
        ),
        "policy.context_guidance": (
            "Response policy: Prefer matching policy text when available, and cite the policy code and section number. "
            "The display language is English, so answer the user in English."
        ),
        "prompt.file_prefix": "[Attached file contents]",
        "prompt.file_suffix": "[User message follows]",
        "whisper.language": "en",
    },
}


def normalize_language(value: Optional[str]) -> str:
    if not value:
        return ""

    raw = str(value).strip().replace("_", "-").lower()
    if not raw:
        return ""

    primary = raw.split("-", 1)[0]
    if raw in SUPPORTED_LANGUAGES:
        return raw
    if primary in SUPPORTED_LANGUAGES:
        return primary
    return ""


def default_language_from_env() -> str:
    for key in ("APP_DISPLAY_LANGUAGE", "DISPLAY_LANGUAGE"):
        normalized = normalize_language(os.getenv(key, ""))
        if normalized:
            return normalized
    return ""


def all_default_conversation_titles() -> tuple[str, ...]:
    return tuple(DEFAULT_CONVERSATION_TITLES.values())


def default_conversation_title(lang: str) -> str:
    return DEFAULT_CONVERSATION_TITLES.get(normalize_language(lang) or DEFAULT_LANGUAGE, DEFAULT_CONVERSATION_TITLES[DEFAULT_LANGUAGE])


def default_system_prompt(lang: str) -> str:
    return DEFAULT_SYSTEM_PROMPTS.get(normalize_language(lang) or DEFAULT_LANGUAGE, DEFAULT_SYSTEM_PROMPTS[DEFAULT_LANGUAGE])


def all_default_system_prompts() -> set[str]:
    return set(DEFAULT_SYSTEM_PROMPTS.values())


def is_default_conversation_title(title: Optional[str]) -> bool:
    return (title or "").strip() in all_default_conversation_titles()


def translate(key: str, lang: str, **kwargs: Any) -> str:
    language = normalize_language(lang) or DEFAULT_LANGUAGE
    table = TRANSLATIONS.get(language) or TRANSLATIONS[DEFAULT_LANGUAGE]
    text = table.get(key) or TRANSLATIONS[DEFAULT_LANGUAGE].get(key) or key
    if kwargs:
        return text.format(**kwargs)
    return text


def missing_translation_keys(languages: Iterable[str] = SUPPORTED_LANGUAGES) -> dict[str, list[str]]:
    languages = tuple(languages)
    all_keys = set()
    for language in languages:
        all_keys.update(TRANSLATIONS.get(language, {}).keys())

    missing: dict[str, list[str]] = {}
    for language in languages:
        table_keys = set(TRANSLATIONS.get(language, {}).keys())
        absent = sorted(all_keys - table_keys)
        if absent:
            missing[language] = absent
    return missing
