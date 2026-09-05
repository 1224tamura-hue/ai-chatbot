from typing import List, Dict, Optional

from utils.i18n import DEFAULT_LANGUAGE, default_system_prompt, translate


class PromptManager:
    """プロンプト管理クラス"""

    DEFAULT_SYSTEM_PROMPT = default_system_prompt(DEFAULT_LANGUAGE)

    @staticmethod
    def build_system_prompt(custom_prompt: Optional[str] = None, lang: str = DEFAULT_LANGUAGE) -> str:
        """
        システムプロンプト構築

        Args:
            custom_prompt: カスタムプロンプト（Noneの場合デフォルト）

        Returns:
            システムプロンプト文字列
        """
        if custom_prompt and custom_prompt.strip():
            return custom_prompt.strip()
        return default_system_prompt(lang)

    @staticmethod
    def format_messages_for_api(
        messages: List[Dict],
        system_prompt: Optional[str] = None,
        file_content: Optional[str] = None,
        policy_context: Optional[str] = None,
        lang: str = DEFAULT_LANGUAGE,
    ) -> List[Dict]:
        """
        APIリクエスト用にメッセージ整形

        Args:
            messages: DB保存メッセージ [{"role": "user", "content": "..."}]
            system_prompt: システムプロンプト
            file_content: ファイル内容（添付時）
            policy_context: 社内規程検索結果（簡易RAG）

        Returns:
            API用メッセージリスト
        """
        api_messages = []

        # システムプロンプトを先頭に追加
        system_text = PromptManager.build_system_prompt(system_prompt, lang=lang)
        api_messages.append({
            "role": "system",
            "content": system_text
        })

        # 社内規程の検索結果がある場合、参照コンテキストとして追加
        if policy_context:
            api_messages.append({
                "role": "system",
                "content": policy_context
            })

        # ファイル内容がある場合は、最初のユーザーメッセージの前に追加
        if file_content:
            file_message = (
                f"{translate('prompt.file_prefix', lang)}\n\n"
                f"{file_content}\n\n"
                f"{translate('prompt.file_suffix', lang)}"
            )
            api_messages.append({
                "role": "system",
                "content": file_message
            })

        # 会話履歴を追加（systemロールのメッセージは除外）
        for msg in messages:
            if msg["role"] in ["user", "assistant"]:
                api_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        return api_messages
