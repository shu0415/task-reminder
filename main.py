import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from src.slack_bot import handler, send_all_reminders

app = FastAPI()
JST = pytz.timezone("Asia/Tokyo")


@app.post("/slack/events")
async def slack_events(req: Request):
    # Slack URL検証チャレンジに対応
    try:
        body = await req.json()
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge")}
    except Exception:
        pass
    return await handler.handle(req)


@app.post("/slack/interactions")
async def slack_interactions(req: Request):
    return await handler.handle(req)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/remind/now")
def remind_now():
    """手動でリマインドを送信（テスト用）"""
    send_all_reminders()
    return {"status": "sent"}


@app.post("/setup/formatting")
def setup_formatting():
    """完了行をグレー化する条件付き書式を全シートに適用（赤より優先）"""
    from src.sheets import apply_completed_formatting
    added = apply_completed_formatting()
    return {"status": "ok", "rules_added": added}


def start_scheduler():
    times = []
    for i in range(1, 4):
        val = os.environ.get(f"REMINDER_TIME_{i}")
        if val:
            times.append((i, val.split(":")))

    scheduler = BackgroundScheduler(timezone=JST)
    for idx, parts in times:
        scheduler.add_job(
            send_all_reminders,
            CronTrigger(hour=int(parts[0]), minute=int(parts[1]), timezone=JST),
            id=f"reminder_{idx}"
        )
    scheduler.start()
    time_str = " / ".join(f"{p[0]}:{p[1]}" for _, p in times)
    print(f"スケジューラー起動: {time_str} JST")


@app.on_event("startup")
def on_startup():
    start_scheduler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
