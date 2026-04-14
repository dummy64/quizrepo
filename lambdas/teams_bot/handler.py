import json
import os

import boto3
from botbuilder.core import TurnContext
from botbuilder.schema import Activity

QUIZZES_TABLE = os.environ["QUIZZES_TABLE"]
RESPONSES_TABLE = os.environ["RESPONSES_TABLE"]
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "")

dynamodb = boto3.resource("dynamodb")


def build_adaptive_card(quiz: dict) -> dict:
    body = [
        {"type": "TextBlock", "text": f"🧠 Daily Quiz: {quiz['topic']}", "size": "Large", "weight": "Bolder"},
        {"type": "TextBlock", "text": f"⏰ Closes at: {quiz['closes_at']} UTC", "size": "Small"},
    ]
    for q in quiz["questions"]:
        body.append({"type": "TextBlock", "text": q["text"], "weight": "Bolder", "wrap": True})
        body.append({
            "type": "Input.ChoiceSet",
            "id": q["question_id"],
            "style": "expanded",
            "choices": [{"title": f"{k}: {v}", "value": k} for k, v in q["options"].items()],
        })

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": [{
            "type": "Action.Submit",
            "title": "✅ Submit Answers",
            "data": {"action": "submit_quiz", "quiz_id": quiz["quiz_id"]},
        }],
    }


def handle_submission(body: dict) -> dict:
    """Process Adaptive Card submission from Teams."""
    data = body.get("value", {})
    quiz_id = data.pop("quiz_id", "")
    data.pop("action", None)
    user = body.get("from", {})
    user_id = user.get("aadObjectId", user.get("id", "unknown"))
    display_name = user.get("name", user_id)

    from lambdas.answer_collector.handler import save_response
    return save_response(
        quiz_id=quiz_id,
        user_id=user_id,
        platform="teams",
        display_name=display_name,
        answers=data,
    )


def post_quiz_to_teams(quiz: dict):
    """Post quiz card via incoming webhook."""
    import urllib.request
    card = build_adaptive_card(quiz)
    payload = json.dumps({
        "type": "message",
        "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": card}],
    }).encode()
    req = urllib.request.Request(TEAMS_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)


def handler(event, context):
    """Routes: quiz posting (from generator) vs card submission (from API Gateway)."""
    if "body" in event:
        body = json.loads(event.get("body", "{}"))
        if body.get("value", {}).get("action") == "submit_quiz":
            result = handle_submission(body)
            # Return adaptive card response to update the card
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "statusCode": 200,
                    "type": "message",
                    "text": result["message"],
                }),
            }
        return {"statusCode": 200, "body": ""}

    # Triggered by quiz generator — post quiz to Teams
    quiz_id = event.get("quiz_id")
    if quiz_id:
        quiz = dynamodb.Table(QUIZZES_TABLE).get_item(Key={"quiz_id": quiz_id}).get("Item")
        if quiz:
            post_quiz_to_teams(quiz)
    return {"statusCode": 200}
