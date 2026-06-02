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


def start_scheduler():
    time1 = os.environ.get("REMINDER_TIME_1", "09:00").split(":")
    time2 = os.environ.get("REMINDER_TIME_2", "13:00").split(":")

    scheduler = BackgroundScheduler(timezone=JST)
    scheduler.add_job(
        send_all_reminders,
        CronTrigger(hour=int(time1[0]), minute=int(time1[1]), timezone=JST),
        id="reminder_1"
    )
    scheduler.add_job(
        send_all_reminders,
        CronTrigger(hour=int(time2[0]), minute=int(time2[1]), timezone=JST),
        id="reminder_2"
    )
    scheduler.start()
    print(f"スケジューラー起動: {time1[0]}:{time1[1]} / {time2[0]}:{time2[1]} JST")


@app.on_event("startup")
def on_startup():
    start_scheduler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
