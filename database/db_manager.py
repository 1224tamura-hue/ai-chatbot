import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
import os
import re

from database.seed_demo_policies import initialize_schema as initialize_policy_schema
from database.seed_demo_policies import upsert_policies as upsert_demo_policies

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover - optional dependency for PostgreSQL deploys
    psycopg2 = None
    RealDictCursor = None


class DatabaseManager:
    """データベース操作を管理するクラス"""

    def __init__(self, db_path: str = "data/chatbot.db", database_url: Optional[str] = None):
        """
        DB接続初期化

        Args:
            db_path: データベースファイルのパス
        """
        self.database_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
        self.is_postgres = self.database_url.startswith(("postgres://", "postgresql://"))
        self.db_path = db_path
        if not self.is_postgres:
            # データディレクトリが存在しない場合は作成
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.initialize_database()

    def _to_placeholder_sql(self, query: str) -> str:
        if self.is_postgres:
            return query.replace("?", "%s")
        return query

    def _get_connection(self):
        """DB接続取得"""
        if self.is_postgres:
            if psycopg2 is None:
                raise RuntimeError(
                    "PostgreSQL利用には psycopg2-binary が必要です。requirements.txt を更新後に再デプロイしてください。"
                )
            conn = psycopg2.connect(self.database_url, cursor_factory=RealDictCursor)
            conn.autocommit = False
            return conn

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 辞書形式で結果を取得
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _execute(self, cursor, query: str, params=None):
        query = self._to_placeholder_sql(query)
        if params is None:
            return cursor.execute(query)
        return cursor.execute(query, params)

    def _executemany(self, cursor, query: str, params_seq):
        query = self._to_placeholder_sql(query)
        return cursor.executemany(query, params_seq)

    def initialize_database(self) -> None:
        """テーブル作成"""
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.is_postgres:
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS conversations (
                    id BIGSERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS messages (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_id BIGINT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS presets (
                    id BIGSERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    system_prompt TEXT,
                    temperature REAL DEFAULT 0.7,
                    max_tokens INTEGER DEFAULT 1000,
                    model TEXT DEFAULT 'gpt-3.5-turbo',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        else:
            # conversationsテーブル
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # messagesテーブル
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)

            # presetsテーブル
            self._execute(cursor, """
                CREATE TABLE IF NOT EXISTS presets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    system_prompt TEXT,
                    temperature REAL DEFAULT 0.7,
                    max_tokens INTEGER DEFAULT 1000,
                    model TEXT DEFAULT 'gpt-3.5-turbo',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        # インデックス作成
        self._execute(cursor, """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
            ON messages(conversation_id)
        """)
        self._execute(cursor, """
            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
            ON conversations(updated_at DESC)
        """)

        # 既存DB向けのカラム拡張
        self._ensure_conversation_columns(cursor)
        self._ensure_company_policies(conn)

        conn.commit()
        conn.close()

    def _ensure_company_policies(self, conn) -> None:
        """
        社内規程テーブルを保証し、空の場合はデモデータを投入する
        """
        initialize_policy_schema(conn)
        cursor = conn.cursor()
        self._execute(cursor, "SELECT COUNT(*) AS cnt FROM company_policies")
        row = cursor.fetchone()
        policy_count = int(row["cnt"]) if row else 0

        if policy_count == 0:
            upsert_demo_policies(conn)

    def _ensure_conversation_columns(self, cursor) -> None:
        """
        conversationsテーブルに必要カラムを追加（マイグレーション）
        """
        if self.is_postgres:
            self._execute(cursor, """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'conversations'
            """)
            existing_columns = {row["column_name"] for row in cursor.fetchall()}
        else:
            self._execute(cursor, "PRAGMA table_info(conversations)")
            existing_columns = {row[1] for row in cursor.fetchall()}

        if "is_pinned" not in existing_columns:
            self._execute(cursor, "ALTER TABLE conversations ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0")
        if "is_archived" not in existing_columns:
            self._execute(cursor, "ALTER TABLE conversations ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0")
        if "archived_at" not in existing_columns:
            self._execute(cursor, "ALTER TABLE conversations ADD COLUMN archived_at TIMESTAMP")

    # ===== 会話管理 =====

    def create_conversation(self, title: str = "新しい会話") -> int:
        """
        新規会話作成

        Args:
            title: 会話タイトル

        Returns:
            作成された会話ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.is_postgres:
            self._execute(
                cursor,
                "INSERT INTO conversations (title) VALUES (?) RETURNING id",
                (title,),
            )
            conversation_id = int(cursor.fetchone()["id"])
        else:
            self._execute(
                cursor,
                "INSERT INTO conversations (title) VALUES (?)",
                (title,),
            )
            conversation_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return conversation_id

    def get_all_conversations(self) -> List[Dict]:
        """
        全会話リスト取得

        Returns:
            会話リスト（新しい順）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT id, title, created_at, updated_at, is_pinned, is_archived, archived_at
            FROM conversations
            ORDER BY is_pinned DESC, updated_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_conversation(self, conversation_id: int) -> Optional[Dict]:
        """
        特定会話の情報取得

        Args:
            conversation_id: 会話ID

        Returns:
            会話情報（存在しない場合はNone）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT id, title, created_at, updated_at, is_pinned, is_archived, archived_at
            FROM conversations
            WHERE id = ?
        """, (conversation_id,))

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def update_conversation_title(self, conversation_id: int, title: str) -> None:
        """
        会話タイトル更新

        Args:
            conversation_id: 会話ID
            title: 新しいタイトル
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(
            cursor,
            "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, conversation_id)
        )

        conn.commit()
        conn.close()

    def delete_conversation(self, conversation_id: int) -> None:
        """
        会話削除（関連メッセージも削除）

        Args:
            conversation_id: 会話ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, "DELETE FROM conversations WHERE id = ?", (conversation_id,))

        conn.commit()
        conn.close()

    def cleanup_empty_conversations(self, title: str = "新しい会話", keep: int = 1) -> None:
        """
        指定タイトルの空会話を整理（最新を残して削除）

        Args:
            title: 会話タイトル
            keep: 残す件数
        """
        if keep < 0:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT c.id, c.updated_at
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.title = ?
            GROUP BY c.id
            HAVING COUNT(m.id) = 0
            ORDER BY c.updated_at DESC, c.id DESC
        """, (title,))

        rows = cursor.fetchall()
        ids = [row["id"] for row in rows]
        to_delete = ids[keep:]

        if to_delete:
            self._executemany(cursor, "DELETE FROM conversations WHERE id = ?", [(cid,) for cid in to_delete])

        conn.commit()
        conn.close()

    def update_conversation_timestamp(self, conversation_id: int) -> None:
        """
        会話の更新日時を現在時刻に更新

        Args:
            conversation_id: 会話ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            UPDATE conversations
            SET updated_at = CURRENT_TIMESTAMP,
                is_archived = 0,
                archived_at = NULL
            WHERE id = ?
        """, (conversation_id,))

        conn.commit()
        conn.close()

    def auto_archive_stale_conversations(self, days: int = 30, exclude_conversation_id: Optional[int] = None) -> int:
        """
        長期間更新のない会話を自動アーカイブ（ピン留めは除外）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.is_postgres:
            params = [days]
            sql = """
                UPDATE conversations
                SET is_archived = 1,
                    archived_at = CURRENT_TIMESTAMP
                WHERE is_archived = 0
                  AND is_pinned = 0
                  AND updated_at < (CURRENT_TIMESTAMP - (? * INTERVAL '1 day'))
            """
            if exclude_conversation_id is not None:
                sql += " AND id != ?"
                params.append(exclude_conversation_id)
            self._execute(cursor, sql, tuple(params))
        else:
            params = [f"-{days} days"]
            sql = """
                UPDATE conversations
                SET is_archived = 1,
                    archived_at = CURRENT_TIMESTAMP
                WHERE is_archived = 0
                  AND is_pinned = 0
                  AND updated_at < datetime('now', ?)
            """
            if exclude_conversation_id is not None:
                sql += " AND id != ?"
                params.append(exclude_conversation_id)
            self._execute(cursor, sql, tuple(params))
        affected = cursor.rowcount

        conn.commit()
        conn.close()
        return affected

    def get_pinned_conversations(self) -> List[Dict]:
        """
        ピン留めされたアクティブ会話を取得
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT c.id, c.title, c.created_at, c.updated_at, c.is_pinned, c.is_archived,
                   COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.is_archived = 0
              AND c.is_pinned = 1
            GROUP BY c.id
            ORDER BY c.updated_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_recent_conversations(self, limit: int = 10) -> List[Dict]:
        """
        非ピン留めの最近会話を取得
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT c.id, c.title, c.created_at, c.updated_at, c.is_pinned, c.is_archived,
                   COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.is_archived = 0
              AND c.is_pinned = 0
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_archived_conversations(self, limit: int = 30) -> List[Dict]:
        """
        アーカイブ会話を取得
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT c.id, c.title, c.created_at, c.updated_at, c.archived_at,
                   COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.is_archived = 1
            GROUP BY c.id
            ORDER BY c.archived_at DESC, c.updated_at DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_latest_active_conversation_id(self) -> Optional[int]:
        """
        最新のアクティブ会話IDを取得
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT id
            FROM conversations
            WHERE is_archived = 0
            ORDER BY is_pinned DESC, updated_at DESC, id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        conn.close()
        return int(row["id"]) if row else None

    def set_conversation_pin(self, conversation_id: int, pinned: bool) -> None:
        """
        会話のピン留め状態を更新
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            UPDATE conversations
            SET is_pinned = ?,
                updated_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE updated_at END
            WHERE id = ?
        """, (1 if pinned else 0, 1 if pinned else 0, conversation_id))

        conn.commit()
        conn.close()

    def restore_conversation(self, conversation_id: int) -> None:
        """
        アーカイブ会話を復元
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            UPDATE conversations
            SET is_archived = 0,
                archived_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (conversation_id,))

        conn.commit()
        conn.close()

    def archive_conversation(self, conversation_id: int) -> None:
        """
        会話をアーカイブ
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            UPDATE conversations
            SET is_archived = 1,
                is_pinned = 0,
                archived_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (conversation_id,))

        conn.commit()
        conn.close()

    def auto_title_conversation_if_default(
        self,
        conversation_id: int,
        default_title: str = "新しい会話",
        max_len: int = 28
    ) -> None:
        """
        デフォルトタイトルの会話を、最初のユーザー発言で自動命名
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, "SELECT title FROM conversations WHERE id = ?", (conversation_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return

        title = (row["title"] or "").strip()
        if title != default_title:
            conn.close()
            return

        self._execute(cursor, """
            SELECT content
            FROM messages
            WHERE conversation_id = ?
              AND role = 'user'
            ORDER BY id ASC
            LIMIT 1
        """, (conversation_id,))
        user_row = cursor.fetchone()
        if not user_row:
            conn.close()
            return

        normalized = re.sub(r"\s+", " ", user_row["content"]).strip()
        normalized = re.sub(r"[。！？!?]+$", "", normalized)
        if not normalized:
            conn.close()
            return

        new_title = normalized[:max_len]
        self._execute(cursor, """
            UPDATE conversations
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_title, conversation_id))

        conn.commit()
        conn.close()

    # ===== メッセージ管理 =====

    def add_message(self, conversation_id: int, role: str, content: str) -> None:
        """
        メッセージ追加

        Args:
            conversation_id: 会話ID
            role: 役割（user, assistant, system）
            content: メッセージ内容
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(
            cursor,
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content)
        )

        conn.commit()
        conn.close()

        # 会話の更新日時を更新
        self.update_conversation_timestamp(conversation_id)
        if role == "user":
            self.auto_title_conversation_if_default(conversation_id)

    def get_messages(self, conversation_id: int) -> List[Dict]:
        """
        会話のメッセージ履歴取得

        Args:
            conversation_id: 会話ID

        Returns:
            メッセージリスト（古い順）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT id, conversation_id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
        """, (conversation_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def clear_messages(self, conversation_id: int) -> None:
        """
        会話のメッセージクリア

        Args:
            conversation_id: 会話ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, "DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))

        conn.commit()
        conn.close()

    # ===== 社内規程検索（簡易RAG用） =====

    def search_company_policies(self, query: str, limit: int = 5) -> List[Dict]:
        """
        社内規程テーブルをキーワード検索

        Args:
            query: ユーザー入力
            limit: 返却件数

        Returns:
            スコア順の規程条項リスト
        """
        if not query or not query.strip():
            return []

        normalized_query, token_weights, strong_tokens = self._build_query_tokens(query)
        if not token_weights:
            return []

        conn = self._get_connection()
        cursor = conn.cursor()

        if self.is_postgres:
            self._execute(cursor, """
                SELECT COUNT(*) AS cnt
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('company_policies', 'company_policy_items')
            """)
        else:
            self._execute(cursor, """
                SELECT COUNT(*) AS cnt
                FROM sqlite_master
                WHERE type = 'table'
                  AND name IN ('company_policies', 'company_policy_items')
            """)
        if cursor.fetchone()["cnt"] < 2:
            conn.close()
            return []

        self._execute(cursor, """
            SELECT
                p.policy_code,
                p.title,
                p.category,
                p.scope,
                p.description,
                p.effective_date,
                i.section_no,
                i.item_title,
                i.item_text
            FROM company_policies p
            JOIN company_policy_items i ON i.policy_id = p.id
        """)
        rows = cursor.fetchall()
        conn.close()

        scored_results = []
        for row in rows:
            searchable_text = self._normalize_search_text(
                " ".join(
                [
                    row["policy_code"],
                    row["title"],
                    row["category"],
                    row["scope"],
                    row["description"],
                    row["section_no"],
                    row["item_title"],
                    row["item_text"],
                ]
                )
            )

            score = 0.0
            strong_hit = False

            if len(normalized_query) >= 2 and normalized_query in searchable_text:
                score += 8.0
                strong_hit = True

            for token, weight in token_weights.items():
                if token in searchable_text:
                    score += weight
                    if token in strong_tokens:
                        strong_hit = True

            # 2文字バイグラムの偶発一致のみでは採用しない
            if score > 0 and strong_hit:
                row_dict = dict(row)
                row_dict["score"] = score
                scored_results.append(row_dict)

        scored_results.sort(
            key=lambda x: (
                -x["score"],
                x["policy_code"],
                x["section_no"],
            )
        )
        return scored_results[:limit]

    def _normalize_search_text(self, text: str) -> str:
        """
        検索用テキスト正規化（同義語吸収）
        """
        normalized = (text or "").lower()
        replacements = {
            "社内文書": "社内規程",
            "社内規定": "社内規程",
            "規定": "規程",
            "ルール": "規程",
        }
        for src, dst in replacements.items():
            normalized = normalized.replace(src, dst)

        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _build_query_tokens(self, query: str) -> tuple[str, Dict[str, float], set[str]]:
        """
        クエリを正規化し、重み付きトークンを生成
        """
        normalized_query = self._normalize_search_text(query)
        token_weights: Dict[str, float] = {}
        strong_tokens: set[str] = set()

        def add_token(token: str, weight: float, strong: bool = False) -> None:
            token = token.strip()
            if len(token) < 2:
                return
            current = token_weights.get(token)
            if current is None or weight > current:
                token_weights[token] = weight
            if strong:
                strong_tokens.add(token)

        add_token(normalized_query, 5.0, strong=True)

        for token in re.findall(r"[a-z0-9]{2,}", normalized_query):
            add_token(token, 2.5 if len(token) >= 4 else 2.0, strong=True)

        # 助詞を区切りにして日本語語句を抽出
        segmented = re.sub(r"[のはをにでとがへやも、。！？\s]+", " ", normalized_query)
        for token in re.findall(r"[一-龥ぁ-んァ-ンー]{2,}", segmented):
            add_token(token, 3.0 if len(token) >= 3 else 2.0, strong=True)

        # スクリプト境界で追加分割（例: パスワード要件 -> パスワード / 要件）
        for token in re.findall(r"[一-龥]{2,}|[ぁ-ん]{2,}|[ァ-ンー]{2,}", normalized_query):
            add_token(token, 2.5 if len(token) >= 3 else 2.0, strong=True)

        # 取りこぼし防止のため2文字バイグラムも追加（弱い重み）
        ja_text = "".join(re.findall(r"[一-龥ぁ-んァ-ンー]", normalized_query))
        if len(ja_text) >= 2:
            for i in range(len(ja_text) - 1):
                add_token(ja_text[i:i + 2], 0.35, strong=False)

        # 社内文書のような曖昧語を規程検索へ寄せる
        if any(word in normalized_query for word in ("社内規程", "社内文書", "社内規定", "規程", "規定")):
            add_token("規程", 4.0, strong=True)
            add_token("ガイドライン", 2.0, strong=True)

        ordered = dict(sorted(token_weights.items(), key=lambda x: x[1], reverse=True)[:80])
        strong_tokens = {token for token in strong_tokens if token in ordered}
        return normalized_query, ordered, strong_tokens

    # ===== プリセット管理 =====

    def save_preset(
        self,
        name: str,
        system_prompt: str,
        temperature: float,
        max_tokens: int,
        model: str
    ) -> None:
        """
        プリセット保存

        Args:
            name: プリセット名
            system_prompt: システムプロンプト
            temperature: Temperature設定
            max_tokens: 最大トークン数
            model: 使用モデル
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        if self.is_postgres:
            self._execute(cursor, """
                INSERT INTO presets (name, system_prompt, temperature, max_tokens, model)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    system_prompt = EXCLUDED.system_prompt,
                    temperature = EXCLUDED.temperature,
                    max_tokens = EXCLUDED.max_tokens,
                    model = EXCLUDED.model
            """, (name, system_prompt, temperature, max_tokens, model))
        else:
            self._execute(cursor, """
                INSERT OR REPLACE INTO presets (name, system_prompt, temperature, max_tokens, model)
                VALUES (?, ?, ?, ?, ?)
            """, (name, system_prompt, temperature, max_tokens, model))

        conn.commit()
        conn.close()

    def get_all_presets(self) -> List[Dict]:
        """
        全プリセット取得

        Returns:
            プリセットリスト
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, """
            SELECT id, name, system_prompt, temperature, max_tokens, model, created_at
            FROM presets
            ORDER BY created_at DESC
        """)

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_preset(self, name: str) -> Optional[Dict]:
        """
        特定プリセット取得

        Args:
            name: プリセット名

        Returns:
            プリセット情報（存在しない場合はNone）
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(
            cursor,
            "SELECT id, name, system_prompt, temperature, max_tokens, model, created_at FROM presets WHERE name = ?",
            (name,)
        )

        row = cursor.fetchone()
        conn.close()

        return dict(row) if row else None

    def delete_preset(self, name: str) -> None:
        """
        プリセット削除

        Args:
            name: プリセット名
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        self._execute(cursor, "DELETE FROM presets WHERE name = ?", (name,))

        conn.commit()
        conn.close()
