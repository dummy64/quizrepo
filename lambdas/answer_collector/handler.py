import json
import os
from datetime import datetime

import boto3

RESPONSES_TABLE = os.environ["RESPONSES_TABLE"]
QUIZZES_TABLE = os.environ["QUIZZES_TABLE"]

dynamodb = boto3.resource("dynamodb")


def is_quiz_open(quiz_id: str) -> bool:
    item = dynamodb.Table(QUIZZES_TABLE).get_item(Key={"quiz_id": quiz_id}).get("Item")
    if not item or item["status"] != "active":
        return False
    return datetime.utcnow().isoformat() < item["closes_at"]


def save_response(quiz_id: str, user_id: str, platform: str, display_name: str, answers: dict) -> dict:
    table = dynamodb.Table(RESPONSES_TABLE)
    # Prevent duplicate submissions
    existing = table.get_item(Key={"quiz_id": quiz_id, "user_id": user_id}).get("Item")
    if existing:
        return {"status": "duplicate", "message": "You already submitted answers for this quiz."}

    if not is_quiz_open(quiz_id):
        return {"status": "closed", "message": "This quiz is no longer accepting answers."}

    table.put_item(Item={
        "quiz_id": quiz_id,
        "user_id": user_id,
        "platform": platform,
        "display_name": display_name,
        "answers": answers,
        "submitted_at": datetime.utcnow().isoformat(),
    })
    return {"status": "ok", "message": "Answers submitted!"}


def handler(event, context):
    body = json.loads(event.get("body", "{}"))
    result = save_response(
        quiz_id=body["quiz_id"],
        user_id=body["user_id"],
        platform=body["platform"],
        display_name=body["display_name"],
        answers=body["answers"],
    )
    return {"statusCode": 200, "body": json.dumps(result)}
