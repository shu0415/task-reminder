import os
import re
import threading
from slack_bolt import App
from slack_bolt.adapter.fastapi import SlackRequestHandler
from datetime import date
from src.sheets import get_pending_tasks, get_all_tasks, update_task_status, PLATFORMS
from src.ai import score_tasks, analyze_patterns

app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"]
)
handler = SlackRequestHandler(app)

PLATFORM_CHANNELS = {
    "Instagram": os.environ.get("SLACK_CHANNEL_INSTAGRAM", ""),
    "TikTok": os.environ.get("SLACK_CHANNEL_TIKTOK", ""),
    "X": os.environ.get("SLACK_CHANNEL_X", ""),
    "Gumroad": os.environ.get("SLACK_CHANNEL_GUMROAD", ""),
    "その他": os.environ.get("SLACK_CHANNEL_OTHER", ""),
}

PLATFORM_EMOJI = {
    "Instagram": "📸",
    "TikTok": "🎵",
    "X": "🐦",
    "Gumroad": "🛒",
    "その他": "📋",
}

STATUS_EMOJI = {
    "未着手": "⚪",
    "進行中": "🟡",
    "完了": "✅",
    "保留": "🔵",
}

SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{os.environ.get('SPREADSHEET_ID', '')}"


def parse_date_safe(value):
    """期限を安全にパース。ハイフン/スラッシュ/ドット区切り、ゼロ埋めなし、
    '2026年6月3日'、時刻付きなど、どんな表記でも年月日の数字を拾う。失敗時はNone。"""
    if not value:
        return None
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", str(value))
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return date(y, mo, d)
        except ValueError:
            return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def build_task_blocks(tasks: list[dict], platform: str) -> list[dict]:
    blocks = []

    for task in tasks:
        task_id = str(task.get("タスクID", ""))
        name = task.get("タスク名", "")
        assignee = task.get("担当者", "")
        deadline = task.get("期限", "")
        status = task.get("ステータス", "未着手")
        ai_score = task.get("AIスコア", "")
        priority = task.get("優先度", "")

        # 期限チェック
        deadline_label = ""
        if deadline:
            d = parse_date_safe(deadline)
            if d:
                delta = (d - date.today()).days
                if delta < 0:
                    deadline_label = f"*🔴 期限超過 ({deadline})*"
                elif delta == 0:
                    deadline_label = f"*🟠 今日締切 ({deadline})*"
                elif delta <= 2:
                    deadline_label = f"🟡 {deadline}締切"
                else:
                    deadline_label = f"📅 {deadline}締切"
            else:
                deadline_label = f"📅 {deadline}"

        score_label = f"AIスコア: {ai_score}" if ai_score else ""
        priority_label = f"優先度: {priority}" if priority else ""

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"{STATUS_EMOJI.get(status, '⚪')} *{name}*\n"
                    f"担当: {assignee}　{deadline_label}\n"
                    f"{priority_label}　{score_label}"
                ).strip()
            },
            "accessory": {
                "type": "overflow",
                "action_id": f"status_update_{platform}_{task_id}",
                "options": [
                    {"text": {"type": "plain_text", "text": "✅ 完了"}, "value": f"{platform}|{task_id}|完了"},
                    {"text": {"type": "plain_text", "text": "🟡 進行中"}, "value": f"{platform}|{task_id}|進行中"},
                    {"text": {"type": "plain_text", "text": "🔵 保留"}, "value": f"{platform}|{task_id}|保留"},
                    {"text": {"type": "plain_text", "text": "⚪ 未着手に戻す"}, "value": f"{platform}|{task_id}|未着手"},
                ]
            }
        })
        blocks.append({"type": "divider"})

    return blocks


def get_sheet_url(platform: str) -> str:
    """プラットフォームごとのシートURLを取得"""
    try:
        from src.sheets import get_spreadsheet
        ss = get_spreadsheet()
        ws = ss.worksheet(platform)
        return f"{SPREADSHEET_URL}/edit#gid={ws.id}"
    except Exception:
        return f"{SPREADSHEET_URL}/edit"


def send_reminder(platform: str):
    channel = PLATFORM_CHANNELS.get(platform)
    if not channel:
        print(f"チャンネルIDが設定されていません: {platform}")
        return

    tasks = get_pending_tasks(platform)
    all_tasks = get_all_tasks(platform)

    # AIスコアリング（失敗してもスキップ）
    if tasks:
        try:
            tasks = score_tasks(tasks, platform)
        except Exception as e:
            print(f"[{platform}] AIスコアリングをスキップ: {e}")

    # AI分析コメント（失敗してもスキップ）
    ai_comment = ""
    if all_tasks:
        try:
            ai_comment = analyze_patterns(all_tasks, platform)
        except Exception as e:
            print(f"[{platform}] AI分析をスキップ: {e}")

    emoji = PLATFORM_EMOJI.get(platform, "📋")
    now_str = date.today().strftime("%Y/%m/%d")
    overdue = []
    for t in tasks:
        d = parse_date_safe(t.get("期限"))
        if d and (d - date.today()).days < 0:
            overdue.append(t)

    header_text = (
        f"{emoji} *{platform} タスクリマインド*　{now_str}\n"
        f"未完了: *{len(tasks)}件*"
        + (f"　｜　期限超過: *{len(overdue)}件*" if overdue else "")
    )

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": header_text}},
        {"type": "divider"},
    ]

    if tasks:
        blocks += build_task_blocks(tasks, platform)
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "🎉 未完了タスクはありません！"}
        })

    if ai_comment:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"🤖 *AI分析*\n{ai_comment}"}
        })

    sheet_url = get_sheet_url(platform)
    blocks.append({
        "type": "actions",
        "elements": [{
            "type": "button",
            "text": {"type": "plain_text", "text": "📊 スプレッドシートを開く"},
            "url": sheet_url,
            "action_id": "open_sheet"
        }]
    })

    try:
        app.client.chat_postMessage(channel=channel, blocks=blocks, text=f"{platform}のタスクリマインド")
    except Exception as e:
        # ブロックが原因で失敗しても、最低限テキストだけは必ず届ける
        print(f"[{platform}] ブロック投稿失敗、テキストで再送: {e}")
        app.client.chat_postMessage(
            channel=channel,
            text=f"{emoji} {platform} タスクリマインド {now_str}\n未完了: {len(tasks)}件"
        )


def send_all_reminders():
    """全プラットフォームにリマインド送信"""
    for platform in PLATFORMS:
        try:
            send_reminder(platform)
        except Exception as e:
            print(f"[{platform}] リマインド送信エラー: {e}")


# ステータス変更のインタラクション受信
def _process_status_update(value: str, channel: str, user: str):
    """重い処理（シート更新＋通知）。バックグラウンドで実行され、例外はここで握りつぶす。"""
    try:
        platform, task_id, new_status = value.split("|")
    except ValueError:
        print(f"ステータス更新: 不正なvalue: {value!r}")
        return

    try:
        success = update_task_status(platform, task_id, new_status)
    except Exception as e:
        print(f"ステータス更新エラー [{task_id}]: {e}")
        if channel:
            try:
                app.client.chat_postMessage(
                    channel=channel,
                    text=f"⚠️ *{task_id}* の更新に失敗しました。少し待って再度お試しください。"
                )
            except Exception:
                pass
        return

    if success and channel:
        try:
            app.client.chat_postMessage(
                channel=channel,
                text=f"✅ *{task_id}* のステータスを *{new_status}* に更新しました（{user}）"
            )
        except Exception as e:
            print(f"ステータス更新の通知失敗 [{task_id}]: {e}")


@app.action(re.compile(r"^status_update_"))
def handle_status_update(ack, body, action):
    # まず即座にackを返す（Slackの3秒タイムアウト・500回避）
    ack()
    try:
        value = action.get("value", "")
        channel = body.get("container", {}).get("channel_id", "")
        user = body.get("user", {}).get("name", "")
        # 重い処理はバックグラウンドへ逃がす
        threading.Thread(
            target=_process_status_update,
            args=(value, channel, user),
            daemon=True,
        ).start()
    except Exception as e:
        # 何があってもSlackには500を返さない
        print(f"handle_status_update エラー: {e}")


@app.action("open_sheet")
def handle_open_sheet(ack):
    ack()
