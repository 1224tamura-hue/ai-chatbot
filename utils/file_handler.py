from PyPDF2 import PdfReader
import io
import os


class FileHandler:
    """ファイル処理クラス"""

    @staticmethod
    def read_text_file(uploaded_file) -> str:
        """
        テキストファイル読み込み (.txt, .md)

        Args:
            uploaded_file: Streamlitのアップロードファイルオブジェクト

        Returns:
            ファイル内容のテキスト
        """
        try:
            # バイトデータをデコード
            content = uploaded_file.read().decode('utf-8')
            return content
        except UnicodeDecodeError:
            # UTF-8でデコードできない場合は他のエンコーディングを試す
            uploaded_file.seek(0)
            try:
                content = uploaded_file.read().decode('shift-jis')
                return content
            except UnicodeDecodeError as e:
                raise ValueError("ファイルの読み込みに失敗しました。エンコーディングを確認してください。") from e

    @staticmethod
    def read_pdf_file(uploaded_file) -> str:
        """
        PDFファイル読み込み

        Args:
            uploaded_file: Streamlitのアップロードファイルオブジェクト

        Returns:
            ファイル内容のテキスト
        """
        try:
            # PDFリーダーで読み込み
            pdf_reader = PdfReader(io.BytesIO(uploaded_file.read()))

            # 全ページのテキストを抽出
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"

            return text.strip()
        except Exception as e:
            raise RuntimeError(f"PDFの読み込みに失敗しました: {str(e)}") from e

    @staticmethod
    def process_uploaded_file(uploaded_file) -> str:
        """
        アップロードファイルを処理

        Args:
            uploaded_file: Streamlitのアップロードファイルオブジェクト

        Returns:
            ファイル内容のテキスト

        Raises:
            ValueError: サポートされていないファイル形式
        """
        file_name = uploaded_file.name
        _, ext = os.path.splitext(file_name)
        file_extension = ext.lower().lstrip(".")

        if file_extension in ['txt', 'md']:
            return FileHandler.read_text_file(uploaded_file)
        elif file_extension == 'pdf':
            return FileHandler.read_pdf_file(uploaded_file)
        else:
            raise ValueError(f"サポートされていないファイル形式です: .{file_extension}")
