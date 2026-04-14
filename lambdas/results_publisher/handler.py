import json
import os
import urllib.request

import boto3
from boto3.dynamodb.conditions import Key
from slack_sdk import WebClient

LEADERBOARD_TABLE = os.environ["LEADERBOARD_TABLE"]
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "")
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")

dynamodb = boto3.resource("dynamodb")


def get_top_entries(period: str, limit: int = 10) -> list:
    table = dynamodb.Table(LEADERBOARD_TABLE)
    resp = table.query(
        KeyConditionExpression=Key("period").eq(period),
        IndexName="by_score",
        ScanIndexForward=False,
        Limit=limit,
    )
    return resp.get("Items", [])


def format_leaderboard_text(title: str, entries: list) -> str:
    lines = [f"*{title}*\n"]
    medals = ["🥇", "🥈", "🥉"]
    for i, e in enumerate(entries):
        prefix = medals[i] if i < 3 else f"{i+1}."
        lines.append(f"{prefix} {e['display_name']} — {int(e['score'])} pts ({int(e['correct'])}/{int(e['total'])})")
    return "\n".join(lines) if entries else f"*{title}*\nNo participants yet."


def publish_to_slack(daily_text: str, alltime_text: str):
    if not SLACK_BOT_TOKEN or not SLACK_CHANNEL:
        return
    slack = WebClient(token=SLACK_BOT_TOKEN)
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": "📊 Quiz Results"}},
        {"type": "section", "text": {"type": "mrkdwn", "text": daily_text}},
        {"type": "divider"},
        {"type": "section", "text": {"type": "mrkdwn", "text": alltime_text}},
    ]
    slack.chat_postMessage(channel=SLACK_CHANNEL, text="Quiz Results", blocks=blocks)


def publish_to_teams(daily_text: str, alltime_text: str):
    if not TEAMS_WEBHOOK_URL:
        return
    card = {
        "type": "AdaptiveCard", "$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "📊 Quiz Results", "size": "Large", "weight": "Bolder"},
            {"type": "TextBlock", "text": daily_text, "wrap": True},
            {"type": "TextBlock", "text": "───────────────", "separator": True},
            {"type": "TextBlock", "text": alltime_text, "wrap": True},
        ],
    }
    payload = json.dumps({
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    }).encode()
    req = urllib.request.Request(TEAMS_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)


def handler(event, context):
    """Publish results for scored quizzes. Invoked by scorer Lambda."""
    quiz_date = event.get("quiz_date", "")
    daily_period = f"daily:{quiz_date}"

    daily_entries = get_top_entries(daily_period)
    alltime_entries = get_top_entries("alltime")

    daily_text = format_leaderboard_text(f"🏆 Today's Results ({quiz_date})", daily_entries)
    alltime_text = format_leaderboard_text("🌟 All-Time Leaderboard", alltime_entries)

    publish_to_slack(daily_text, alltime_text)
    publish_to_teams(daily_text, alltime_text)

    return {"published": True, "daily_count": len(daily_entries), "alltime_count": len(alltime_entries)}
