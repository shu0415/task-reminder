import os
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
}

PLATFORM_EMOJI = {
    "Instagram": "📸",
    "TikTok": "🎵",
    "X": "🐦",
    "Gumroad": "🛒",
}

STATUS_EMOJI = {
    "未着手": "⚪",
    "進行中": "🟡",
    "完了": "✅",
    "保留": "🔵",
}

SPREADSHEET_URL = f"https://docs.google.com/spreadsheets/d/{os.environ.get('SPREADSHEET_ID', '')}"


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
            try:
                delta = (date.fromisoformat(str(deadline)) - date.today()).days
                if delta < 0:
                    deadline_label = f"*🔴 期限超過 ({deadline})*"
                elif delta == 0:
                    deadline_label = f"*🟠 今日締切 ({deadline})*"
                elif delta <= 2:
                    deadline_label = f"🟡 {deadline}締切"
                else:
                    deadline_label = f"📅 {deadline}締切"
            except ValueError:
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

    # AIスコアリング
    if tasks:
        tasks = score_tasks(tasks, platform)

    # AI分析コメント
    ai_comment = analyze_patterns(all_tasks, platform) if all_tasks else ""

    emoji = PLATFORM_EMOJI.get(platform, "📋")
    now_str = date.today().strftime("%Y/%m/%d")
    overdue = [t for t in tasks if t.get("期限") and
               (date.fromisoformat(str(t["期限"])) - date.today()).days < 0]

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

    app.client.chat_postMessage(channel=channel, blocks=blocks, text=f"{platform}のタスクリマインド")


def send_all_reminders():
    """全プラットフォームにリマインド送信"""
    for platform in PLATFORMS:
        try:
            send_reminder(platform)
        except Exception as e:
            print(f"[{platform}] リマインド送信エラー: {e}")


# ステータス変更のインタラクション受信
@app.action({"action_id": lambda aid: aid.startswith("status_update_")})
def handle_status_update(ack, body, action):
    ack()
    value = action.get("value", "")
    try:
        platform, task_id, new_status = value.split("|")
    except ValueError:
        return

    success = update_task_status(platform, task_id, new_status)
    user = body["user"]["name"]

    if success:
        channel = body["container"]["channel_id"]
        app.client.chat_postMessage(
            channel=channel,
            text=f"✅ *{task_id}* のステータスを *{new_status}* に更新しました（{user}）"
        )


@app.action("open_sheet")
def handle_open_sheet(ack):
    ack()
