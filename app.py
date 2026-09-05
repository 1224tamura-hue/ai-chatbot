import base64
import hashlib
import inspect
import os

import streamlit as st
from audio_recorder_streamlit import audio_recorder
from dotenv import load_dotenv

from database.db_manager import DatabaseManager
from utils.audio_handler import AudioHandler
from utils.file_handler import FileHandler
from utils.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGE_LABELS,
    SUPPORTED_LANGUAGES,
    all_default_conversation_titles,
    all_default_system_prompts,
    default_conversation_title,
    default_language_from_env,
    default_system_prompt,
    is_default_conversation_title,
    normalize_language,
    translate,
)
from utils.llm_client import LLMClient
from utils.prompt_manager import PromptManager

# 環境変数読み込み
load_dotenv()

# 定数
HISTORY_MESSAGE_LIMIT = 12
RAG_RESULT_LIMIT = 3
MAX_RESPONSE_TOKENS_CAP = 500
CHAT_RENDER_LIMIT = 60
AUTO_ARCHIVE_DAYS = 30


def tr(key: str, **kwargs) -> str:
    return translate(key, st.session_state.get("display_language", DEFAULT_LANGUAGE), **kwargs)


def get_runtime_setting(key: str) -> str:
    value = os.getenv(key, "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get(key, "")).strip()
    except Exception:
        return ""


def read_query_language() -> str:
    try:
        raw = st.query_params.get("lang", "")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        return normalize_language(raw)
    except Exception:
        return ""


def read_browser_language() -> str:
    try:
        locale = getattr(st.context, "locale", "") or ""
        return normalize_language(locale)
    except Exception:
        return ""


def resolve_display_language() -> str:
    return (
        read_query_language()
        or normalize_language(st.session_state.get("display_language", ""))
        or default_language_from_env()
        or read_browser_language()
        or DEFAULT_LANGUAGE
    )


def configure_page(lang: str) -> None:
    page_kwargs = {
        "page_title": "AI Chatbot",
        "page_icon": "🤖",
        "layout": "wide",
    }
    try:
        parameters = inspect.signature(st.set_page_config).parameters
        if "page_lang" in parameters:
            page_kwargs["page_lang"] = lang
        elif "lang" in parameters:
            page_kwargs["lang"] = lang
    except (TypeError, ValueError):
        pass
    st.set_page_config(**page_kwargs)


def persist_display_language(lang: str) -> None:
    st.session_state.display_language = lang
    try:
        st.query_params["lang"] = lang
    except Exception:
        pass


def apply_display_language(lang: str) -> None:
    lang = normalize_language(lang) or DEFAULT_LANGUAGE
    previous = normalize_language(st.session_state.get("display_language", ""))
    persist_display_language(lang)

    if st.session_state.get("system_prompt") in all_default_system_prompts():
        localized_prompt = default_system_prompt(lang)
        st.session_state.system_prompt = localized_prompt
        if "system_prompt_input" in st.session_state:
            st.session_state.system_prompt_input = localized_prompt

    if previous and previous != lang:
        sync_draft_conversation_title(lang)


def sync_draft_conversation_title(lang: str) -> None:
    db = st.session_state.get("db")
    conversation_id = st.session_state.get("current_conversation_id")
    if db is None or conversation_id is None:
        return

    conversation = db.get_conversation(conversation_id)
    if not conversation or not is_default_conversation_title(conversation.get("title")):
        return
    if db.get_messages(conversation_id):
        return

    next_title = default_conversation_title(lang)
    if conversation.get("title") != next_title:
        db.update_conversation_title(conversation_id, next_title)


def render_language_selector() -> None:
    current_lang = st.session_state.display_language
    if "display_language_select" not in st.session_state:
        st.session_state.display_language_select = current_lang
    elif st.session_state.display_language_select not in SUPPORTED_LANGUAGES:
        st.session_state.display_language_select = current_lang

    selected = st.selectbox(
        tr("language.label"),
        options=list(SUPPORTED_LANGUAGES),
        format_func=lambda code: LANGUAGE_LABELS[code],
        key="display_language_select",
        help=tr("language.caption"),
    )
    if selected != current_lang:
        apply_display_language(selected)
        st.rerun()


def build_policy_context(policy_hits: list[dict]) -> str:
    if not policy_hits:
        return ""

    lines = [
        tr("policy.context_header"),
        tr("policy.context_intro"),
    ]
    for idx, hit in enumerate(policy_hits, 1):
        lines.append(
            tr(
                "policy.context_item",
                idx=idx,
                policy_code=hit["policy_code"],
                title=hit["title"],
                section_no=hit["section_no"],
                item_title=hit["item_title"],
                item_text=hit["item_text"],
            )
        )

    lines.append(tr("policy.context_guidance"))
    return "\n".join(lines)


def reset_input_state() -> None:
    st.session_state.uploaded_file_content = None
    st.session_state.audio_transcript = ""
    st.session_state.audio_transcript_edit = ""
    st.session_state.last_audio_hash = None


def get_initial_conversation_id() -> int:
    existing_id = st.session_state.db.get_latest_active_conversation_id()
    if existing_id is not None:
        return existing_id
    return st.session_state.db.create_conversation(default_conversation_title(st.session_state.display_language))


def conversation_label(conv: dict) -> str:
    title = (conv.get("title") or "").strip()
    message_count = int(conv.get("message_count", 0))
    if is_default_conversation_title(title) and message_count == 0:
        return tr("draft_label")
    return title


def find_previous_user_text(messages: list[dict], current_index: int) -> str:
    for i in range(current_index - 1, -1, -1):
        if messages[i]["role"] == "user":
            return messages[i]["content"]
    return ""


def render_policy_hits(policy_hits: list[dict], show_empty: bool = False) -> None:
    if not policy_hits and not show_empty:
        return

    with st.expander(tr("policy.expander", count=len(policy_hits)), expanded=False):
        if not policy_hits:
            st.caption(tr("policy.empty"))
            return

        for hit in policy_hits:
            st.markdown(
                tr(
                    "policy.item",
                    policy_code=hit["policy_code"],
                    title=hit["title"],
                    section_no=hit["section_no"],
                    item_title=hit["item_title"],
                )
            )


def handle_user_message(user_input: str, llm_client: LLMClient) -> None:
    user_input = (user_input or "").strip()
    if not user_input:
        return

    with st.chat_message("user"):
        st.write(user_input)

    st.session_state.db.add_message(
        st.session_state.current_conversation_id,
        "user",
        user_input,
    )

    all_messages = st.session_state.db.get_messages(st.session_state.current_conversation_id)
    recent_messages = all_messages[-HISTORY_MESSAGE_LIMIT:]

    policy_hits = st.session_state.db.search_company_policies(user_input, limit=RAG_RESULT_LIMIT)
    policy_context = build_policy_context(policy_hits)

    api_messages = PromptManager.format_messages_for_api(
        recent_messages,
        system_prompt=st.session_state.system_prompt,
        file_content=st.session_state.uploaded_file_content,
        policy_context=policy_context,
        lang=st.session_state.display_language,
    )

    response_text = ""
    try:
        with st.spinner(tr("spinner.generating")):
            response_stream = llm_client.chat_completion(
                messages=api_messages,
                model=st.session_state.model,
                temperature=st.session_state.temperature,
                max_tokens=min(int(st.session_state.max_tokens), MAX_RESPONSE_TOKENS_CAP),
                stream=True,
            )

            with st.chat_message("assistant"):
                response_placeholder = st.empty()
                for chunk in response_stream:
                    if chunk.choices[0].delta.content:
                        response_text += chunk.choices[0].delta.content
                        response_placeholder.markdown(response_text)

                render_policy_hits(policy_hits, show_empty=True)

        st.session_state.db.add_message(
            st.session_state.current_conversation_id,
            "assistant",
            response_text,
        )
        st.session_state.uploaded_file_content = None

    except Exception as e:
        st.error(tr("error.response_failed", error=str(e)))


initial_language = resolve_display_language()
configure_page(initial_language)

if "display_language" not in st.session_state:
    persist_display_language(initial_language)
elif read_query_language() and read_query_language() != st.session_state.display_language:
    apply_display_language(read_query_language())
elif not read_query_language():
    persist_display_language(st.session_state.display_language)

# セッション状態初期化
if "db" not in st.session_state:
    database_url = get_runtime_setting("DATABASE_URL")
    st.session_state.db = DatabaseManager(database_url=database_url)
    st.session_state.db.auto_archive_stale_conversations(days=AUTO_ARCHIVE_DAYS)
    st.session_state.db.cleanup_empty_conversations(title=all_default_conversation_titles(), keep=1)

if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = get_initial_conversation_id()
else:
    current_conv = st.session_state.db.get_conversation(st.session_state.current_conversation_id)
    if not current_conv or int(current_conv.get("is_archived", 0)) == 1:
        st.session_state.current_conversation_id = get_initial_conversation_id()

sync_draft_conversation_title(st.session_state.display_language)

if "uploaded_file_content" not in st.session_state:
    st.session_state.uploaded_file_content = None

if "audio_transcript" not in st.session_state:
    st.session_state.audio_transcript = ""

if "audio_transcript_edit" not in st.session_state:
    st.session_state.audio_transcript_edit = ""

if "audio_transcript_edit_input" not in st.session_state:
    st.session_state.audio_transcript_edit_input = ""

if "clear_audio_transcript_input" not in st.session_state:
    st.session_state.clear_audio_transcript_input = False

if "clear_manual_input" not in st.session_state:
    st.session_state.clear_manual_input = False

if "archive_expanded" not in st.session_state:
    st.session_state.archive_expanded = False

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = default_system_prompt(st.session_state.display_language)

if "temperature" not in st.session_state:
    st.session_state.temperature = 0.7

if "max_tokens" not in st.session_state:
    st.session_state.max_tokens = 500

if "model" not in st.session_state:
    st.session_state.model = "gpt-3.5-turbo"

if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None

if st.session_state.clear_audio_transcript_input:
    st.session_state.audio_transcript_edit_input = ""
    st.session_state.clear_audio_transcript_input = False

if st.session_state.clear_manual_input:
    st.session_state.manual_text_input = ""
    st.session_state.clear_manual_input = False

# タイトル
st.title(tr("page.title"))

# サイドバー
with st.sidebar:
    render_language_selector()
    st.caption(tr("language.caption"))
    st.markdown("---")
    st.header(tr("sidebar.conversations"))

    if st.button(tr("sidebar.new_conversation"), use_container_width=True):
        current_messages = st.session_state.db.get_messages(st.session_state.current_conversation_id)
        if current_messages:
            st.session_state.db.archive_conversation(st.session_state.current_conversation_id)
        else:
            current_conv = st.session_state.db.get_conversation(st.session_state.current_conversation_id)
            if current_conv and is_default_conversation_title(current_conv["title"]):
                st.session_state.db.delete_conversation(st.session_state.current_conversation_id)

        new_conv_id = st.session_state.db.create_conversation(
            default_conversation_title(st.session_state.display_language)
        )
        st.session_state.current_conversation_id = new_conv_id
        reset_input_state()
        st.rerun()

    archived_conversations = st.session_state.db.get_archived_conversations(limit=20)
    with st.expander(
        tr("sidebar.archive", count=len(archived_conversations)),
        expanded=st.session_state.archive_expanded
    ):
        st.caption(tr("sidebar.archive_caption"))

        if not archived_conversations:
            st.caption(tr("sidebar.archive_empty"))
        else:
            for conv in archived_conversations:
                col1, col2 = st.columns([5, 1])
                with col1:
                    if st.button(conversation_label(conv), key=f"archived_open_{conv['id']}", use_container_width=True):
                        st.session_state.archive_expanded = True
                        current_messages = st.session_state.db.get_messages(st.session_state.current_conversation_id)
                        if current_messages:
                            st.session_state.db.archive_conversation(st.session_state.current_conversation_id)
                        st.session_state.db.restore_conversation(conv["id"])
                        st.session_state.current_conversation_id = conv["id"]
                        reset_input_state()
                        st.rerun()
                with col2:
                    if st.button("🗑️", key=f"archived_delete_{conv['id']}"):
                        st.session_state.archive_expanded = True
                        st.session_state.db.delete_conversation(conv["id"])
                        st.rerun()

    st.markdown("---")
    with st.expander(tr("sidebar.advanced"), expanded=False):
        st.caption(tr("sidebar.advanced_caption"))

        st.session_state.system_prompt = st.text_area(
            tr("sidebar.system_prompt"),
            value=st.session_state.system_prompt,
            height=120,
            key="system_prompt_input",
        )

        st.session_state.temperature = st.slider(
            tr("sidebar.temperature"),
            min_value=0.0,
            max_value=2.0,
            value=float(st.session_state.temperature),
            step=0.1,
            key="temperature_slider",
        )

        st.session_state.max_tokens = int(
            st.number_input(
                tr("sidebar.max_tokens"),
                min_value=100,
                max_value=MAX_RESPONSE_TOKENS_CAP,
                value=int(min(st.session_state.max_tokens, MAX_RESPONSE_TOKENS_CAP)),
                step=50,
                key="max_tokens_input",
            )
        )

        model_options = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]
        current_model_index = model_options.index(st.session_state.model) if st.session_state.model in model_options else 0
        st.session_state.model = st.selectbox(
            tr("sidebar.model"),
            options=model_options,
            index=current_model_index,
            key="model_select",
        )

# APIキー確認
api_key = get_runtime_setting("OPENAI_API_KEY")
if not api_key:
    st.error(tr("api_key_missing"))
    st.info(tr("api_key_help"))
    st.stop()

# LLMクライアント初期化
llm_client = LLMClient(api_key)
audio_handler = AudioHandler(api_key)

# メインエリア
current_conv = st.session_state.db.get_conversation(st.session_state.current_conversation_id)
if current_conv:
    st.subheader(f"💬 {current_conv['title']}")

st.caption(
    tr(
        "model_caption",
        model=st.session_state.model,
        history=HISTORY_MESSAGE_LIMIT,
        rag=RAG_RESULT_LIMIT,
        tokens=MAX_RESPONSE_TOKENS_CAP,
    )
)

messages = st.session_state.db.get_messages(st.session_state.current_conversation_id)
# 1) 文字入力（最上部）
st.markdown(f"### {tr('input.heading')}")
manual_input = st.text_area(
    tr("input.label"),
    key="manual_text_input",
    height=90,
    placeholder=tr("input.placeholder"),
)
if st.button(tr("input.send"), use_container_width=True, type="primary"):
    if manual_input.strip():
        handle_user_message(manual_input, llm_client)
        st.session_state.clear_manual_input = True
        st.rerun()
    else:
        st.warning(tr("input.empty_warning"))

# 2) 音声入力
st.markdown(f"### {tr('audio.heading')}")
audio_bytes = None
if hasattr(st, "audio_input"):
    recorded_audio = st.audio_input(tr("audio.input_label"), key="audio_input_native")
    if recorded_audio is not None:
        audio_bytes = recorded_audio.read()
else:
    audio_bytes = audio_recorder(
        text=tr("audio.record_text"),
        icon_size="2x",
        pause_threshold=60.0,
        key=f"audio_recorder_{st.session_state.current_conversation_id}",
    )

if audio_bytes:
    try:
        audio_hash = hashlib.sha256(
            str(st.session_state.current_conversation_id).encode("utf-8") + audio_bytes
        ).hexdigest()
        if audio_hash != st.session_state.last_audio_hash:
            with st.spinner(tr("audio.recognizing")):
                transcript = audio_handler.speech_to_text(
                    audio_bytes,
                    language=tr("whisper.language") or None,
                )
                st.session_state.audio_transcript = transcript
                st.session_state.audio_transcript_edit = transcript
                st.session_state.audio_transcript_edit_input = transcript
                st.session_state.last_audio_hash = audio_hash
    except Exception as e:
        st.error(tr("audio.recognize_error", error=str(e)))

if st.session_state.audio_transcript:
    st.caption(tr("audio.edit_caption"))
    edited_transcript = st.text_area(
        tr("audio.edit_label"),
        key="audio_transcript_edit_input",
        height=90,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button(tr("audio.send_edited"), use_container_width=True):
            if edited_transcript.strip():
                handle_user_message(edited_transcript, llm_client)
                st.session_state.audio_transcript = ""
                st.session_state.clear_audio_transcript_input = True
                st.rerun()
            else:
                st.warning(tr("audio.send_empty"))
    with col_b:
        if st.button(tr("audio.clear"), use_container_width=True):
            st.session_state.audio_transcript = ""
            st.session_state.clear_audio_transcript_input = True
            st.rerun()

# 3) 補助機能（折りたたみ）
with st.expander(tr("extras.heading"), expanded=False):
    uploaded_file = st.file_uploader(
        tr("extras.file_uploader"),
        type=["txt", "md", "pdf"],
        key="file_uploader",
    )

    if uploaded_file:
        try:
            file_content = FileHandler.process_uploaded_file(uploaded_file)
            st.session_state.uploaded_file_content = file_content
            st.success(tr("extras.file_loaded", name=uploaded_file.name, chars=len(file_content)))
            with st.expander(tr("extras.file_preview")):
                st.text(file_content[:500] + ("..." if len(file_content) > 500 else ""))
        except Exception as e:
            st.error(tr("extras.file_error", error=str(e)))

    if st.session_state.uploaded_file_content:
        st.caption(tr("extras.file_pending"))
    st.markdown("---")
    if st.button(tr("extras.play_latest"), use_container_width=True):
        ai_messages = [msg for msg in messages if msg["role"] == "assistant"]
        if ai_messages:
            last_ai_message = ai_messages[-1]["content"]
            try:
                with st.spinner(tr("extras.summarizing")):
                    summary_messages = [
                        {"role": "system", "content": tr("summary.system_prompt")},
                        {"role": "user", "content": last_ai_message},
                    ]
                    summary_text = llm_client.chat_completion(
                        messages=summary_messages,
                        model=st.session_state.model,
                        temperature=0.3,
                        max_tokens=200,
                        stream=False,
                    )

                with st.spinner(tr("extras.generating_audio")):
                    audio_data = audio_handler.text_to_speech(summary_text, voice="alloy")
                    audio_base64 = base64.b64encode(audio_data).decode()
                    audio_html = f"""
                    <audio autoplay>
                        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                    </audio>
                    """
                    st.markdown(audio_html, unsafe_allow_html=True)
                    st.success(tr("extras.played"))
            except Exception as e:
                st.error(tr("extras.audio_error", error=str(e)))
        else:
            st.warning(tr("extras.no_ai_message"))

# チャット履歴
if len(messages) > CHAT_RENDER_LIMIT:
    st.info(tr("chat.truncated", limit=CHAT_RENDER_LIMIT))

visible_messages = messages[-CHAT_RENDER_LIMIT:]
for idx, msg in enumerate(visible_messages):
    if msg["role"] == "user":
        with st.chat_message("user"):
            st.write(msg["content"])
    elif msg["role"] == "assistant":
        with st.chat_message("assistant"):
            st.write(msg["content"])
            prev_user_text = find_previous_user_text(visible_messages, idx)
            if prev_user_text:
                history_hits = st.session_state.db.search_company_policies(prev_user_text, limit=RAG_RESULT_LIMIT)
                render_policy_hits(history_hits)

# フッター
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray;'>
        Powered by OpenAI API | Built with Streamlit
    </div>
    """,
    unsafe_allow_html=True,
)
