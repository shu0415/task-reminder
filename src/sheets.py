import gspread
from google.oauth2.service_account import Credentials
from datetime import date
from typing import Optional
import os
import json

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

PLATFORMS = ["Instagram", "TikTok", "X", "Gumroad", "その他"]

CATEGORIES = {
    "Instagram": ["投稿", "リール", "ストーリー", "企画", "分析", "DM返信"],
    "TikTok": ["動画投稿", "企画", "分析", "コメント返信"],
    "X": ["ツイート", "企画", "分析", "リプ返信"],
    "Gumroad": ["商品作成", "販売ページ", "メール確認", "分析", "企画"],
    "その他": ["企画", "リサーチ", "ミーティング", "事務", "その他"],
}

HEADERS = [
    "タスクID", "タスク名", "担当者", "カテゴリ", "ステータス",
    "優先度", "期限", "作成日", "完了日", "メモ", "AIスコア"
]

STATUSES = ["未着手", "進行中", "完了", "保留"]
PRIORITIES = ["高", "中", "低"]


def get_client() -> gspread.Client:
    # 環境変数からJSON文字列で読み込む（Railway用）
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        # ローカル開発用（ファイルから読み込む）
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


def apply_completed_formatting():
    """「ステータス=完了」の行をグレー＋取り消し線にする条件付き書式を、
    優先度=高の赤ルールより上位（index 0）に追加する。完了が赤より優先される。
    既に同じルールがあれば追加しない（冪等）。全シートに適用。"""
    ss = get_spreadsheet()
    meta = ss.fetch_sheet_metadata({
        "fields": "sheets(properties(sheetId,title),conditionalFormats)"
    })
    DONE_FORMULA = '=$E2="完了"'
    requests = []

    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        title = props.get("title")
        sid = props.get("sheetId")
        if title not in PLATFORMS:
            continue

        # 既に完了ルールがあるか確認（冪等性）
        already = False
        for cf in sheet.get("conditionalFormats", []):
            cond = cf.get("booleanRule", {}).get("condition", {})
            for v in cond.get("values", []):
                if v.get("userEnteredValue") == DONE_FORMULA:
                    already = True
        if already:
            continue

        requests.append({
            "addConditionalFormatRule": {
                "index": 0,  # 最上位＝赤ルールより優先
                "rule": {
                    "ranges": [{
                        "sheetId": sid,
                        "startRowIndex": 1,
                        "startColumnIndex": 0,
                        "endColumnIndex": len(HEADERS),
                    }],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": DONE_FORMULA}],
                        },
                        "format": {
                            "backgroundColor": {"red": 0.85, "green": 0.85, "blue": 0.85},
                            "textFormat": {
                                "strikethrough": True,
                                "foregroundColor": {"red": 0.5, "green": 0.5, "blue": 0.5},
                            },
                        },
                    },
                },
            }
        })

    if requests:
        ss.batch_update({"requests": requests})
    return len(requests)


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
