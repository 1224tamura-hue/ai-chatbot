import base64
import hashlib
import os

import streamlit as st
from audio_recorder_streamlit import audio_recorder
from dotenv import load_dotenv

from database.db_manager import DatabaseManager
from utils.audio_handler import AudioHandler
from utils.file_handler import FileHandler
from utils.llm_client import LLMClient
from utils.prompt_manager import PromptManager

# 環境変数読み込み
load_dotenv()

# 定数
DEFAULT_CONVERSATION_TITLE = "新しい会話"
SUMMARY_SYSTEM_PROMPT = "あなたは要約の専門家です。次の文章を日本語で簡潔に要約してください。"

# コスト抑制用（固定上限）
HISTORY_MESSAGE_LIMIT = 12
RAG_RESULT_LIMIT = 3
MAX_RESPONSE_TOKENS_CAP = 500
CHAT_RENDER_LIMIT = 60
AUTO_ARCHIVE_DAYS = 30


def build_policy_context(policy_hits: list[dict]) -> str:
    if not policy_hits:
        return ""

    lines = [
        "[社内規程検索結果]",
        "以下は社内規程データベースから抽出した関連候補です。",
    ]
    for idx, hit in enumerate(policy_hits, 1):
        lines.append(
            f"{idx}. {hit['policy_code']} / {hit['title']} / 第{hit['section_no']}項 {hit['item_title']}: {hit['item_text']}"
        )

    lines.append(
        "回答方針: 関連する規程がある場合はその内容を優先し、規程コードと項番を明示して回答する。"
    )
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
    return st.session_state.db.create_conversation(DEFAULT_CONVERSATION_TITLE)


def conversation_label(conv: dict) -> str:
    title = (conv.get("title") or "").strip()
    message_count = int(conv.get("message_count", 0))
    if title == DEFAULT_CONVERSATION_TITLE and message_count == 0:
        return "下書き（未送信）"
    return title


def find_previous_user_text(messages: list[dict], current_index: int) -> str:
    for i in range(current_index - 1, -1, -1):
        if messages[i]["role"] == "user":
            return messages[i]["content"]
    return ""


def render_policy_hits(policy_hits: list[dict], show_empty: bool = False) -> None:
    if not policy_hits and not show_empty:
        return

    with st.expander(f"📚 参照規程 ({len(policy_hits)}件)", expanded=False):
        if not policy_hits:
            st.caption("関連する規程候補は見つかりませんでした。")
            return

        for hit in policy_hits:
            st.markdown(
                f"- `{hit['policy_code']}` {hit['title']} / 第{hit['section_no']}項 {hit['item_title']}"
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
    )

    response_text = ""
    try:
        with st.spinner("AI応答生成中..."):
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
        st.error(
            "❌ 応答生成に失敗しました。"
            f"\n原因: {str(e)}"
            "\n対処: APIキー・モデル設定・ネットワーク状態を確認して再試行してください。"
        )


# ページ設定
st.set_page_config(page_title="AI Chatbot", page_icon="🤖", layout="wide")

# セッション状態初期化
if "db" not in st.session_state:
    st.session_state.db = DatabaseManager()
    st.session_state.db.auto_archive_stale_conversations(days=AUTO_ARCHIVE_DAYS)
    st.session_state.db.cleanup_empty_conversations(title=DEFAULT_CONVERSATION_TITLE, keep=1)

if "current_conversation_id" not in st.session_state:
    st.session_state.current_conversation_id = get_initial_conversation_id()
else:
    current_conv = st.session_state.db.get_conversation(st.session_state.current_conversation_id)
    if not current_conv or int(current_conv.get("is_archived", 0)) == 1:
        st.session_state.current_conversation_id = get_initial_conversation_id()

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
    st.session_state.system_prompt = PromptManager.DEFAULT_SYSTEM_PROMPT

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

# APIキー確認
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets.get("OPENAI_API_KEY", "")
    except Exception:
        api_key = ""
if not api_key:
    st.error("❌ .envファイルにOPENAI_API_KEYが設定されていません。")
    st.info("📝 .env または Streamlit Secrets に OPENAI_API_KEY を設定してください。")
    st.stop()

# LLMクライアント初期化
llm_client = LLMClient(api_key)
audio_handler = AudioHandler(api_key)

# タイトル
st.title("🤖 AI Chatbot")

# サイドバー
with st.sidebar:
    st.header("💬 会話")

    if st.button("➕ 新規会話", use_container_width=True):
        current_messages = st.session_state.db.get_messages(st.session_state.current_conversation_id)
        if current_messages:
            st.session_state.db.archive_conversation(st.session_state.current_conversation_id)
        else:
            current_conv = st.session_state.db.get_conversation(st.session_state.current_conversation_id)
            if current_conv and current_conv["title"] == DEFAULT_CONVERSATION_TITLE:
                st.session_state.db.delete_conversation(st.session_state.current_conversation_id)

        new_conv_id = st.session_state.db.create_conversation(DEFAULT_CONVERSATION_TITLE)
        st.session_state.current_conversation_id = new_conv_id
        reset_input_state()
        st.rerun()

    archived_conversations = st.session_state.db.get_archived_conversations(limit=20)
    with st.expander(
        f"📦 アーカイブ ({len(archived_conversations)})",
        expanded=st.session_state.archive_expanded
    ):
        st.caption("履歴会話をまとめて管理できます。")

        if not archived_conversations:
            st.caption("アーカイブはありません。")
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
    with st.expander("⚙️ 詳細設定", expanded=False):
        st.caption("通常は未変更で利用できます。")

        st.session_state.system_prompt = st.text_area(
            "システムプロンプト",
            value=st.session_state.system_prompt,
            height=120,
            key="system_prompt_input",
        )

        st.session_state.temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=float(st.session_state.temperature),
            step=0.1,
            key="temperature_slider",
        )

        st.session_state.max_tokens = int(
            st.number_input(
                "Max Tokens",
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
            "モデル",
            options=model_options,
            index=current_model_index,
            key="model_select",
        )

# メインエリア
current_conv = st.session_state.db.get_conversation(st.session_state.current_conversation_id)
if current_conv:
    st.subheader(f"💬 {current_conv['title']}")

st.caption(
    f"モデル: {st.session_state.model} / 履歴送信: 直近{HISTORY_MESSAGE_LIMIT}件 / "
    f"RAG候補: 上位{RAG_RESULT_LIMIT}件 / 応答上限: {MAX_RESPONSE_TOKENS_CAP} tokens"
)

messages = st.session_state.db.get_messages(st.session_state.current_conversation_id)
# 1) 文字入力（最上部）
st.markdown("### 💬 文字入力")
manual_input = st.text_area(
    "メッセージを入力",
    key="manual_text_input",
    height=90,
    placeholder="社内規程について質問してください",
)
if st.button("📤 送信", use_container_width=True, type="primary"):
    if manual_input.strip():
        handle_user_message(manual_input, llm_client)
        st.session_state.clear_manual_input = True
        st.rerun()
    else:
        st.warning("メッセージを入力してください。")

# 2) 音声入力
st.markdown("### 🎤 音声入力")
audio_bytes = None
if hasattr(st, "audio_input"):
    recorded_audio = st.audio_input("マイクで録音して文字起こしできます", key="audio_input_native")
    if recorded_audio is not None:
        audio_bytes = recorded_audio.read()
else:
    audio_bytes = audio_recorder(
        text="録音/停止",
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
            with st.spinner("音声認識中..."):
                transcript = audio_handler.speech_to_text(audio_bytes)
                st.session_state.audio_transcript = transcript
                st.session_state.audio_transcript_edit = transcript
                st.session_state.audio_transcript_edit_input = transcript
                st.session_state.last_audio_hash = audio_hash
    except Exception as e:
        st.error(f"❌ 音声認識エラー: {str(e)}")

if st.session_state.audio_transcript:
    st.caption("文字起こし結果（必要なら修正して送信してください）")
    edited_transcript = st.text_area(
        "音声入力の文字起こし",
        key="audio_transcript_edit_input",
        height=90,
    )
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("✅ 修正して送信", use_container_width=True):
            if edited_transcript.strip():
                handle_user_message(edited_transcript, llm_client)
                st.session_state.audio_transcript = ""
                st.session_state.clear_audio_transcript_input = True
                st.rerun()
            else:
                st.warning("送信する文字を入力してください。")
    with col_b:
        if st.button("🗑️ 文字起こしをクリア", use_container_width=True):
            st.session_state.audio_transcript = ""
            st.session_state.clear_audio_transcript_input = True
            st.rerun()

# 3) 補助機能（折りたたみ）
with st.expander("🧩 補助機能", expanded=False):
    uploaded_file = st.file_uploader(
        "テキストファイル (.txt, .md) またはPDF (.pdf) をアップロード",
        type=["txt", "md", "pdf"],
        key="file_uploader",
    )

    if uploaded_file:
        try:
            file_content = FileHandler.process_uploaded_file(uploaded_file)
            st.session_state.uploaded_file_content = file_content
            st.success(f"✅ ファイル '{uploaded_file.name}' を読み込みました ({len(file_content)} 文字)")
            with st.expander("📄 ファイル内容を確認"):
                st.text(file_content[:500] + ("..." if len(file_content) > 500 else ""))
        except Exception as e:
            st.error(f"❌ ファイル読み込みエラー: {str(e)}")

    if st.session_state.uploaded_file_content:
        st.caption("次回送信時にファイル内容を参照します（送信後に自動クリア）。")
    st.markdown("---")
    if st.button("🔊 最新回答を音声再生", use_container_width=True):
        ai_messages = [msg for msg in messages if msg["role"] == "assistant"]
        if ai_messages:
            last_ai_message = ai_messages[-1]["content"]
            try:
                with st.spinner("要約生成中..."):
                    summary_messages = [
                        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                        {"role": "user", "content": last_ai_message},
                    ]
                    summary_text = llm_client.chat_completion(
                        messages=summary_messages,
                        model=st.session_state.model,
                        temperature=0.3,
                        max_tokens=200,
                        stream=False,
                    )

                with st.spinner("音声生成中..."):
                    audio_data = audio_handler.text_to_speech(summary_text, voice="alloy")
                    audio_base64 = base64.b64encode(audio_data).decode()
                    audio_html = f"""
                    <audio autoplay>
                        <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                    </audio>
                    """
                    st.markdown(audio_html, unsafe_allow_html=True)
                    st.success("✅ 音声を再生しました")
            except Exception as e:
                st.error(f"❌ 音声出力エラー: {str(e)}")
        else:
            st.warning("音声再生できるAI回答がまだありません。")

# チャット履歴
if len(messages) > CHAT_RENDER_LIMIT:
    st.info(f"表示負荷軽減のため、最新{CHAT_RENDER_LIMIT}件のみ表示しています。")

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
