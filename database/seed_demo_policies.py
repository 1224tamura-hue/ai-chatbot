import sqlite3
from typing import Any


DB_PATH = "data/chatbot.db"


POLICIES: list[dict[str, Any]] = [
    {
        "policy_code": "HR-001",
        "title": "勤務・出退勤規程",
        "category": "人事",
        "scope": "全社員",
        "description": "勤務時間、遅刻・早退、残業申請に関する基本ルール。",
        "effective_date": "2026-01-01",
        "items": [
            ("1.1", "所定労働時間", "標準勤務時間は9:30〜18:30（休憩1時間）とする。"),
            ("1.2", "遅刻・早退連絡", "遅刻または早退が見込まれる場合は、始業30分前までに上長へ連絡する。"),
            ("1.3", "残業申請", "月20時間を超える見込みの残業は、事前に上長承認を得る。"),
        ],
    },
    {
        "policy_code": "HR-002",
        "title": "休暇・欠勤規程",
        "category": "人事",
        "scope": "全社員",
        "description": "有給休暇、特別休暇、欠勤時の報告手続き。",
        "effective_date": "2026-01-01",
        "items": [
            ("2.1", "有給申請期限", "有給休暇は原則として取得希望日の3営業日前までに申請する。"),
            ("2.2", "当日体調不良", "当日の体調不良による欠勤は、始業時刻までにチャットと電話で報告する。"),
            ("2.3", "慶弔休暇", "慶弔休暇は証明書提出を条件に就業規則の定める日数を付与する。"),
        ],
    },
    {
        "policy_code": "WK-001",
        "title": "リモートワーク運用規程",
        "category": "働き方",
        "scope": "在宅勤務対象社員",
        "description": "在宅勤務時の勤務報告、出社日、作業環境要件。",
        "effective_date": "2026-01-01",
        "items": [
            ("3.1", "出社頻度", "原則として週2日は出社し、チーム指定日に合わせる。"),
            ("3.2", "勤務開始報告", "在宅勤務日は9:30までに社内チャットで勤務開始報告を行う。"),
            ("3.3", "作業場所", "公共の場所で機密情報を表示する作業は禁止し、覗き見対策を行う。"),
        ],
    },
    {
        "policy_code": "SEC-001",
        "title": "情報セキュリティ基本規程",
        "category": "セキュリティ",
        "scope": "全社員・委託先",
        "description": "アカウント管理、端末管理、データ持ち出し制御。",
        "effective_date": "2026-01-01",
        "items": [
            ("4.1", "パスワード", "パスワードは12文字以上で、使い回しを禁止する。"),
            ("4.2", "多要素認証", "社内主要システムはMFAを必須とし、未設定アカウントは利用停止する。"),
            ("4.3", "USB利用", "会社承認の暗号化USB以外への機密データ保存を禁止する。"),
        ],
    },
    {
        "policy_code": "SEC-002",
        "title": "インシデント報告規程",
        "category": "セキュリティ",
        "scope": "全社員・委託先",
        "description": "情報漏えい・不正アクセス等の初動対応ルール。",
        "effective_date": "2026-01-01",
        "items": [
            ("5.1", "報告期限", "情報セキュリティ事故の疑いを認知した場合、30分以内にCSIRTへ報告する。"),
            ("5.2", "初動対応", "端末の電源断や証拠改変を避け、ネットワーク切断のみ実施する。"),
            ("5.3", "社外公表", "社外への説明は広報責任者または法務責任者の承認後に実施する。"),
        ],
    },
    {
        "policy_code": "FN-001",
        "title": "経費精算規程",
        "category": "経理",
        "scope": "全社員",
        "description": "交通費・交際費・備品購入の申請と承認フロー。",
        "effective_date": "2026-01-01",
        "items": [
            ("6.1", "申請期限", "経費精算は利用月の翌月5営業日以内に申請する。"),
            ("6.2", "領収書要件", "3,000円以上の支出は領収書原本または電子帳簿法対応データを添付する。"),
            ("6.3", "事前承認", "1万円を超える備品購入は、購入前に部門長承認を必須とする。"),
        ],
    },
    {
        "policy_code": "CMP-001",
        "title": "ハラスメント防止規程",
        "category": "コンプライアンス",
        "scope": "全社員・派遣社員",
        "description": "ハラスメント禁止、相談窓口、調査対応の原則。",
        "effective_date": "2026-01-01",
        "items": [
            ("7.1", "禁止行為", "人格を否定する言動、威圧的叱責、性的言動を含む行為を禁止する。"),
            ("7.2", "相談窓口", "相談は人事窓口・外部ホットラインのいずれでも受け付ける。"),
            ("7.3", "不利益取扱い禁止", "相談・申告を理由とした不利益な取扱いを禁止する。"),
        ],
    },
    {
        "policy_code": "IT-001",
        "title": "生成AI利用ガイドライン",
        "category": "IT運用",
        "scope": "全社員",
        "description": "生成AIへの入力制限、出力検証、利用ログ管理。",
        "effective_date": "2026-01-01",
        "items": [
            ("8.1", "入力禁止情報", "個人情報、顧客機密、未公開財務情報を外部生成AIへ入力してはならない。"),
            ("8.2", "出力検証", "生成AIの回答は一次情報で裏取りし、業務判断は担当者が最終責任を持つ。"),
            ("8.3", "利用目的", "利用目的と参照元をチケットに記録し、監査時に提示できる状態を維持する。"),
        ],
    },
]


def initialize_schema(conn: sqlite3.Connection) -> None:
    module_name = conn.__class__.__module__
    is_postgres = module_name.startswith("psycopg2")
    cur = conn.cursor()
    if is_postgres:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS company_policies (
                id BIGSERIAL PRIMARY KEY,
                policy_code TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                scope TEXT NOT NULL,
                description TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS company_policy_items (
                id BIGSERIAL PRIMARY KEY,
                policy_id BIGINT NOT NULL,
                section_no TEXT NOT NULL,
                item_title TEXT NOT NULL,
                item_text TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES company_policies(id) ON DELETE CASCADE,
                UNIQUE(policy_id, section_no)
            )
            """
        )
    else:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS company_policies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_code TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                scope TEXT NOT NULL,
                description TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS company_policy_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                policy_id INTEGER NOT NULL,
                section_no TEXT NOT NULL,
                item_title TEXT NOT NULL,
                item_text TEXT NOT NULL,
                FOREIGN KEY (policy_id) REFERENCES company_policies(id) ON DELETE CASCADE,
                UNIQUE(policy_id, section_no)
            )
            """
        )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_policies_category
        ON company_policies(category)
        """
    )
    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_company_policy_items_policy_id
        ON company_policy_items(policy_id)
        """
    )
    conn.commit()


def upsert_policies(conn: sqlite3.Connection) -> tuple[int, int]:
    module_name = conn.__class__.__module__
    is_postgres = module_name.startswith("psycopg2")
    mark = "%s" if is_postgres else "?"
    cur = conn.cursor()
    policy_count = 0
    item_count = 0

    for policy in POLICIES:
        cur.execute(
            """
            INSERT INTO company_policies
                (policy_code, title, category, scope, description, effective_date, updated_at)
            VALUES ({m}, {m}, {m}, {m}, {m}, {m}, CURRENT_TIMESTAMP)
            ON CONFLICT(policy_code) DO UPDATE SET
                title = excluded.title,
                category = excluded.category,
                scope = excluded.scope,
                description = excluded.description,
                effective_date = excluded.effective_date,
                updated_at = CURRENT_TIMESTAMP
            """.format(m=mark),
            (
                policy["policy_code"],
                policy["title"],
                policy["category"],
                policy["scope"],
                policy["description"],
                policy["effective_date"],
            ),
        )

        cur.execute(
            f"SELECT id FROM company_policies WHERE policy_code = {mark}",
            (policy["policy_code"],),
        )
        fetched = cur.fetchone()
        policy_id = fetched["id"] if isinstance(fetched, dict) else fetched[0]
        policy_count += 1

        cur.execute(f"DELETE FROM company_policy_items WHERE policy_id = {mark}", (policy_id,))
        for section_no, item_title, item_text in policy["items"]:
            cur.execute(
                """
                INSERT INTO company_policy_items
                    (policy_id, section_no, item_title, item_text)
                VALUES ({m}, {m}, {m}, {m})
                """.format(m=mark),
                (policy_id, section_no, item_title, item_text),
            )
            item_count += 1

    conn.commit()
    return policy_count, item_count


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    initialize_schema(conn)
    policy_count, item_count = upsert_policies(conn)
    conn.close()

    print(f"DB: {DB_PATH}")
    print(f"policies_upserted: {policy_count}")
    print(f"policy_items_refreshed: {item_count}")


if __name__ == "__main__":
    main()
