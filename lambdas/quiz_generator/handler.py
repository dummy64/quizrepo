import json
import os
import uuid
from datetime import datetime, timedelta

import boto3

QUIZZES_TABLE = os.environ["QUIZZES_TABLE"]
CONFIG_TABLE = os.environ["CONFIG_TABLE"]
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")

dynamodb = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime")

DEFAULTS = {"topic": "mix of general knowledge and tech trivia", "num_questions": "5", "window_minutes": "120"}


def get_config(key: str) -> str:
    table = dynamodb.Table(CONFIG_TABLE)
    resp = table.get_item(Key={"config_key": key})
    if "Item" in resp:
        return resp["Item"]["value"]
    return DEFAULTS.get(key, "")


def generate_quiz_via_bedrock(topic: str, num_questions: int) -> list:
    prompt = (
        f"Generate a quiz with exactly {num_questions} multiple-choice questions about: {topic}.\n"
        "Return ONLY valid JSON — an array of objects with keys: "
        '"text", "options" (object with keys A,B,C,D), "correct_option" (one of A,B,C,D), "explanation".\n'
        "No markdown, no extra text."
    )
    resp = bedrock.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 4096, "temperature": 0.8},
    )
    body = resp["output"]["message"]["content"][0]["text"]
    return json.loads(body)


def handler(event, context):
    topic = get_config("topic")
    num_questions = int(get_config("num_questions"))
    window_minutes = int(get_config("window_minutes"))

    raw_questions = generate_quiz_via_bedrock(topic, num_questions)

    now = datetime.utcnow()
    quiz_id = f"quiz-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6]}"
    questions = []
    for i, q in enumerate(raw_questions):
        questions.append({
            "question_id": f"{quiz_id}-q{i}",
            "text": q["text"],
            "options": q["options"],
            "correct_option": q["correct_option"],
            "explanation": q["explanation"],
        })

    quiz_item = {
        "quiz_id": quiz_id,
        "created_at": now.isoformat(),
        "topic": topic,
        "questions": questions,
        "status": "active",
        "window_minutes": window_minutes,
        "closes_at": (now + timedelta(minutes=window_minutes)).isoformat(),
    }

    dynamodb.Table(QUIZZES_TABLE).put_item(Item=quiz_item)
    return {"quiz_id": quiz_id, "num_questions": len(questions), "closes_at": quiz_item["closes_at"]}
