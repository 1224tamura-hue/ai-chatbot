from openai import OpenAI
from typing import List, Dict, Union, Iterator
import tiktoken


class LLMClient:
    """OpenAI API呼び出しクラス"""

    def __init__(self, api_key: str):
        """
        OpenAIクライアント初期化

        Args:
            api_key: OpenAI APIキー
        """
        self.client = OpenAI(api_key=api_key)

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-3.5-turbo",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        stream: bool = True
    ) -> Union[str, Iterator]:
        """
        チャット補完API呼び出し

        Args:
            messages: メッセージ履歴 [{"role": "user", "content": "..."}]
            model: 使用モデル
            temperature: ランダム性（0.0-2.0）
            max_tokens: 最大トークン数
            stream: ストリーミング応答

        Returns:
            応答テキストまたはストリームイテレータ
        """
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )

            if stream:
                return response
            else:
                return response.choices[0].message.content

        except Exception as e:
            raise RuntimeError(f"API呼び出しエラー: {str(e)}") from e

    def count_tokens(self, text: str, model: str = "gpt-3.5-turbo") -> int:
        """
        トークン数カウント（概算）

        Args:
            text: テキスト
            model: 使用モデル

        Returns:
            トークン数
        """
        try:
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception:
            # フォールバック: 4文字 ≒ 1トークンで概算
            return len(text) // 4
