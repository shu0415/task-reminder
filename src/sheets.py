import gspread
from google.oauth2.service_account import Credentials
from datetime import date
from typing import Optional
import os

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PLATFORMS = ["Instagram", "TikTok", "X", "Gumroad"]

CATEGORIES = {
    "Instagram": ["投稿", "リール", "ストーリー", "企画", "分析", "DM返信"],
    "TikTok": ["動画投稿", "企画", "分析", "コメント返信"],
    "X": ["ツイート", "企画", "分析", "リプ返信"],
    "Gumroad": ["商品作成", "販売ページ", "メール確認", "分析"],
}

HEADERS = [
    "タスクID", "タスク名", "担当者", "カテゴリ", "ステータス",
    "優先度", "期限", "作成日", "完了日", "メモ", "AIスコア"
]

STATUSES = ["未着手", "進行中", "完了", "保留"]
PRIORITIES = ["高", "中", "低"]


def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(
        os.environ["GOOGLE_CREDENTIALS_FILE"], scopes=SCOPES
    )
    return gspread.authorize(creds)


def get_spreadsheet() -> gspread.Spreadsheet:
    client = get_client()
    return client.open_by_key(os.environ["SPREADSHEET_ID"])


def init_sheets():
    """スプレッドシートの初期化（初回のみ実行）"""
    ss = get_spreadsheet()
    existing = [ws.title for ws in ss.worksheets()]

    for platform in PLATFORMS:
        if platform not in existing:
            ws = ss.add_worksheet(title=platform, rows=1000, cols=20)
        else:
            ws = ss.worksheet(platform)

        # ヘッダーが未設定なら書き込む
        if ws.row_values(1) != HEADERS:
            ws.update("A1", [HEADERS])
            ws.format("A1:K1", {
                "textFormat": {"bold": True},
                "backgroundColor": {"red": 0.2, "green": 0.6, "blue": 0.9}
            })

    print("シートの初期化が完了しました")


def get_pending_tasks(platform: str) -> list[dict]:
    """未完了タスクを取得"""
    ss = get_spreadsheet()
    ws = ss.worksheet(platform)
    rows = ws.get_all_records()
    return [r for r in rows if r.get("ステータス") not in ("完了",) and r.get("タスクID")]


def get_all_tasks(platform: str) -> list[dict]:
    ss = get_spreadsheet()
    ws = ss.worksheet(platform)
    return ws.get_all_records()


def update_task_status(platform: str, task_id: str, status: str, user_name: Optional[str] = None):
    """タスクのステータスを更新"""
    ss = get_spreadsheet()
    ws = ss.worksheet(platform)
    rows = ws.get_all_records()

    for i, row in enumerate(rows, start=2):  # ヘッダーが1行目なので2行目から
        if str(row.get("タスクID")) == str(task_id):
            status_col = HEADERS.index("ステータス") + 1
            ws.update_cell(i, status_col, status)

            if status == "完了":
                done_col = HEADERS.index("完了日") + 1
                ws.update_cell(i, done_col, date.today().isoformat())
            return True
    return False


def update_ai_score(platform: str, task_id: str, score: int):
    """AIスコアを更新"""
    ss = get_spreadsheet()
    ws = ss.worksheet(platform)
    rows = ws.get_all_records()

    for i, row in enumerate(rows, start=2):
        if str(row.get("タスクID")) == str(task_id):
            score_col = HEADERS.index("AIスコア") + 1
            ws.update_cell(i, score_col, score)
            return True
    return False


def add_task(platform: str, task_name: str, assignee: str, category: str,
             priority: str, deadline: str, memo: str = "") -> str:
    """新規タスクを追加"""
    ss = get_spreadsheet()
    ws = ss.worksheet(platform)
    rows = ws.get_all_records()

    # タスクIDの採番
    prefix = platform[:4].upper()
    existing_ids = [r.get("タスクID", "") for r in rows if r.get("タスクID")]
    max_num = 0
    for tid in existing_ids:
        try:
            num = int(str(tid).split("-")[-1])
            max_num = max(max_num, num)
        except ValueError:
            pass
    task_id = f"{prefix}-{str(max_num + 1).zfill(3)}"

    new_row = [
        task_id, task_name, assignee, category, "未着手",
        priority, deadline, date.today().isoformat(), "", memo, ""
    ]
    ws.append_row(new_row)
    return task_id
