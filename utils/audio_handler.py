from openai import OpenAI
from typing import Optional
import io


class AudioHandler:
    """音声処理クラス"""

    def __init__(self, api_key: str):
        """
        OpenAI クライアント初期化

        Args:
            api_key: OpenAI APIキー
        """
        self.client = OpenAI(api_key=api_key)

    def speech_to_text(self, audio_file) -> str:
        """
        音声をテキストに変換（Whisper API）

        Args:
            audio_file: 音声ファイル（バイトデータまたはファイルオブジェクト）

        Returns:
            テキスト
        """
        try:
            # audio_fileがバイトデータの場合、BytesIOオブジェクトに変換
            if isinstance(audio_file, bytes):
                audio_bytes_io = io.BytesIO(audio_file)
                audio_bytes_io.name = "audio.wav"

                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_bytes_io,
                    language="ja"
                )
            else:
                # すでにファイルオブジェクトの場合
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ja"
                )

            return transcript.text

        except Exception as e:
            raise Exception(f"音声認識エラー: {str(e)}")

    def text_to_speech(self, text: str, voice: str = "alloy") -> bytes:
        """
        テキストを音声に変換（TTS API）

        Args:
            text: 読み上げテキスト
            voice: 音声タイプ（alloy, echo, fable, onyx, nova, shimmer）

        Returns:
            音声データ（バイト）
        """
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice=voice,
                input=text
            )

            # ストリームから音声データを取得
            audio_data = b""
            for chunk in response.iter_bytes():
                audio_data += chunk

            return audio_data

        except Exception as e:
            raise Exception(f"音声合成エラー: {str(e)}")
