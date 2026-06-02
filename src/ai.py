import anthropic
import json
from datetime import date


client = anthropic.Anthropic()


def score_tasks(tasks: list[dict], platform: str) -> list[dict]:
    """タスクに優先度スコアをつける（0-100）"""
    if not tasks:
        return []

    today = date.today().isoformat()
    task_summary = json.dumps(tasks, ensure_ascii=False, indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=(
            "あなたはタスク管理のエキスパートです。"
            "与えられたタスクリストを分析し、各タスクの優先度スコア（0-100）を算出してください。"
            "スコアは期限の近さ・優先度設定・滞留日数を考慮してください。"
            "必ずJSON形式のみで返答してください。"
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"今日の日付: {today}\n"
                    f"プラットフォーム: {platform}\n\n"
                    f"以下のタスクにAIスコア（0-100）をつけてください。\n"
                    f"返答形式: {{\"scores\": {{\"タスクID\": スコア, ...}}}}\n\n"
                    f"{task_summary}"
                )
            }
        ]
    )

    try:
        result = json.loads(response.content[0].text)
        scores = result.get("scores", {})
        for task in tasks:
            task_id = str(task.get("タスクID", ""))
            task["AIスコア"] = scores.get(task_id, 50)
        return sorted(tasks, key=lambda x: x.get("AIスコア", 0), reverse=True)
    except (json.JSONDecodeError, KeyError):
        return tasks


def analyze_patterns(all_tasks: list[dict], platform: str) -> str:
    """行動パターンと改善提案を分析"""
    if not all_tasks:
        return ""

    today = date.today().isoformat()
    task_summary = json.dumps(all_tasks, ensure_ascii=False, indent=2)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=(
            "あなたはSNS運用チームのタスク管理アドバイザーです。"
            "タスクの完了パターン・滞留傾向・担当者バランスを分析し、"
            "2〜3文の簡潔な日本語でアドバイスを返してください。"
        ),
        messages=[
            {
                "role": "user",
                "content": (
                    f"今日の日付: {today}\n"
                    f"プラットフォーム: {platform}\n\n"
                    f"以下のタスク履歴を分析して、改善提案を2〜3文でください。\n\n"
                    f"{task_summary}"
                )
            }
        ]
    )

    return response.content[0].text.strip()
