import os
import json
from dotenv import load_dotenv
load_dotenv()

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

CATEGORIES = {
    "Instagram": ["投稿", "リール", "ストーリー", "企画", "分析", "DM返信"],
    "TikTok": ["動画投稿", "企画", "分析", "コメント返信"],
    "X": ["ツイート", "企画", "分析", "リプ返信"],
    "Gumroad": ["商品作成", "販売ページ", "メール確認", "分析"],
}

MEMBER_1 = os.environ.get("MEMBER_1_NAME", "Shu")
MEMBER_2 = os.environ.get("MEMBER_2_NAME", "Partner")

def set_dropdown(ws, col_letter, values, start_row=2, end_row=1000):
    """プルダウンを設定する"""
    range_notation = f"{col_letter}{start_row}:{col_letter}{end_row}"
    body = {
        "requests": [{
            "setDataValidation": {
                "range": {
                    "sheetId": ws.id,
                    "startRowIndex": start_row - 1,
                    "endRowIndex": end_row,
                    "startColumnIndex": ord(col_letter) - ord('A'),
                    "endColumnIndex": ord(col_letter) - ord('A') + 1,
                },
                "rule": {
                    "condition": {
                        "type": "ONE_OF_LIST",
                        "values": [{"userEnteredValue": v} for v in values],
                    },
                    "showCustomUi": True,
                    "strict": False,
                }
            }
        }]
    }
    ws.spreadsheet.batch_update(body)
    print(f"  {col_letter}列: {values}")


def setup():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(
            os.environ["GOOGLE_CREDENTIALS_FILE"], scopes=SCOPES
        )

    client = gspread.authorize(creds)
    ss = client.open_by_key(os.environ["SPREADSHEET_ID"])

    for platform, categories in CATEGORIES.items():
        print(f"\n【{platform}】プルダウン設定中...")
        ws = ss.worksheet(platform)

        # C列: 担当者
        set_dropdown(ws, "C", [MEMBER_1, MEMBER_2, "二人とも"])

        # D列: カテゴリ
        set_dropdown(ws, "D", categories)

        # E列: ステータス
        set_dropdown(ws, "E", ["未着手", "進行中", "完了", "保留"])

        # F列: 優先度
        set_dropdown(ws, "F", ["高", "中", "低"])

    print("\n✅ 全シートのプルダウン設定が完了しました！")


if __name__ == "__main__":
    setup()
