# 🤖 AI Chatbot

OpenAI APIを使用したシンプルで高機能なAIチャットボットアプリケーション

## ✨ 主な機能

- 💬 **対話型チャット**: GPT-3.5/GPT-4とのリアルタイム会話
- 💾 **会話の永続化**: SQLiteによる会話履歴の保存・管理
- 🔀 **複数会話管理**: 複数の会話を作成・切り替え可能
- 📎 **ファイルアップロード**: テキスト・PDFファイルの読み込み対応
- 🎤 **音声入力**: OpenAI Whisper APIによる音声認識
- 🔊 **音声出力**: OpenAI TTS APIによる音声読み上げ
- 🎯 **プロンプト設定**: システムプロンプト・Temperature・Max Tokensのカスタマイズ
- 💾 **プリセット機能**: よく使う設定の保存・読み込み

## 📋 必要環境

- Python 3.8以上
- OpenAI APIキー（[こちら](https://platform.openai.com/api-keys)から取得）

## 🚀 セットアップ手順

### 1. リポジトリのクローン（またはダウンロード）

```bash
cd /path/to/ai-chatbot-app
```

### 2. 仮想環境の作成と有効化

```bash
# 仮想環境作成
python3 -m venv venv

# 仮想環境有効化（Mac/Linux）
source venv/bin/activate

# 仮想環境有効化（Windows）
venv\Scripts\activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定

`.env.example`をコピーして`.env`ファイルを作成：

```bash
cp .env.example .env
```

`.env`ファイルを編集してOpenAI APIキーを設定：

```bash
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxx
```

PostgreSQLを利用する場合は `DATABASE_URL` も設定：

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require
```

### 5. アプリケーションの起動

```bash
streamlit run app.py
```

ブラウザが自動的に開き、アプリケーションが起動します。
（通常は `http://localhost:8501` でアクセス可能）

## 📖 使い方

### 基本的なチャット

1. メッセージ入力欄にテキストを入力
2. 「📤 送信」ボタンをクリック
3. AIからの応答がリアルタイムで表示されます

### 会話管理

- **新規会話作成**: サイドバーの「➕ 新規会話」ボタンをクリック
- **会話切り替え**: サイドバーの会話リストから選択
- **会話名編集**: 会話の「✏️」ボタンをクリック
- **会話削除**: 会話の「🗑️」ボタンをクリック

### ファイルアップロード

1. 「📎 ファイルアップロード」セクションでファイルを選択
2. サポート形式: `.txt`, `.md`, `.pdf`
3. ファイル内容が自動的にLLMに渡されます

### 音声機能

- **音声入力**: 「🎤 録音」ボタンをクリックして音声入力
- **音声出力**: 「🔊 音声出力」ボタンで最新のAI応答を音声再生

### プロンプト設定

サイドバーの「🎯 プロンプト設定」で以下を調整可能：

- **システムプロンプト**: AIの振る舞いを定義
- **Temperature**: 応答のランダム性（0.0〜2.0）
- **Max Tokens**: 最大応答長
- **モデル**: 使用するGPTモデル

### プリセット機能

よく使う設定を保存・再利用：

1. プロンプト設定を調整
2. プリセット名を入力して「保存」
3. 「読込」から保存したプリセットを選択して「適用」

## 📁 プロジェクト構成

```
ai-chatbot-app/
├── app.py                  # メインアプリケーション
├── requirements.txt        # 依存パッケージ
├── .env.example           # 環境変数テンプレート
├── .env                   # 環境変数（要作成）
├── .gitignore             # Git除外設定
├── README.md              # このファイル
├── database/
│   ├── __init__.py
│   └── db_manager.py      # データベース操作
├── utils/
│   ├── __init__.py
│   ├── llm_client.py      # LLM API呼び出し
│   ├── file_handler.py    # ファイル処理
│   ├── audio_handler.py   # 音声処理
│   └── prompt_manager.py  # プロンプト管理
└── data/
    ├── chatbot.db         # SQLiteデータベース（自動生成）
    └── presets/           # プリセット保存先
```

## 🛠️ 技術スタック

| カテゴリ | 技術 |
|---------|------|
| フレームワーク | Streamlit |
| LLM API | OpenAI API (GPT-3.5/GPT-4) |
| データベース | SQLite3 |
| ファイル処理 | PyPDF2 |
| 音声処理 | OpenAI Whisper API, TTS API |
| 環境管理 | python-dotenv |

## ⚠️ 注意事項

- OpenAI APIの使用には料金が発生します
- APIキーは絶対に公開しないでください
- `.env`ファイルは`.gitignore`に含まれています

## 🐛 トラブルシューティング

### アプリが起動しない

- 仮想環境が有効化されているか確認
- `pip install -r requirements.txt`が正常に完了しているか確認

### APIエラーが発生する

- `.env`ファイルのAPIキーが正しいか確認
- OpenAI APIの利用制限・残高を確認

### 社内規程RAGが本番でヒットしない

- Streamlit Cloud の `Secrets` に `DATABASE_URL` を設定（Supabase等の外部PostgreSQL）
- アプリ再起動後、`company_policies` が自動投入されることを確認

### 音声機能が動作しない

- マイクのアクセス許可を確認
- ブラウザがマイク使用を許可しているか確認

## ✅ RAG動作確認

- 実画面での確認手順は [docs/rag_manual_checklist.md](docs/rag_manual_checklist.md) を参照

## 📝 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 🤝 貢献

バグ報告や機能提案は大歓迎です！

---

**Powered by OpenAI API | Built with Streamlit**
