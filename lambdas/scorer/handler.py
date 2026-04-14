import json
import os
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

QUIZZES_TABLE = os.environ["QUIZZES_TABLE"]
RESPONSES_TABLE = os.environ["RESPONSES_TABLE"]
LEADERBOARD_TABLE = os.environ["LEADERBOARD_TABLE"]
RESULTS_PUBLISHER_ARN = os.environ.get("RESULTS_PUBLISHER_ARN", "")

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
POINTS_PER_CORRECT = 10
SPEED_BONUS_MAX = 5  # bonus points for fastest responders


def get_active_quizzes_to_score() -> list:
    """Find quizzes that are active but past their closes_at time."""
    table = dynamodb.Table(QUIZZES_TABLE)
    now = datetime.utcnow().isoformat()
    resp = table.scan(FilterExpression="#s = :active AND closes_at <= :now",
                      ExpressionAttributeNames={"#s": "status"},
                      ExpressionAttributeValues={":active": "active", ":now": now})
    return resp.get("Items", [])


def score_quiz(quiz: dict) -> list:
    """Score all responses for a quiz. Returns list of {user_id, display_name, score, correct, total}."""
    correct_map = {q["question_id"]: q["correct_option"] for q in quiz["questions"]}
    total_questions = len(correct_map)

    responses = dynamodb.Table(RESPONSES_TABLE).query(
        KeyConditionExpression=Key("quiz_id").eq(quiz["quiz_id"])
    ).get("Items", [])

    # Sort by submitted_at for speed bonus
    responses.sort(key=lambda r: r.get("submitted_at", ""))

    results = []
    for rank, resp in enumerate(responses):
        correct = sum(1 for qid, ans in resp.get("answers", {}).items() if correct_map.get(qid) == ans)
        speed_bonus = max(0, SPEED_BONUS_MAX - rank) if correct == total_questions else 0
        score = correct * POINTS_PER_CORRECT + speed_bonus
        results.append({
            "user_id": resp["user_id"],
            "display_name": resp.get("display_name", resp["user_id"]),
            "score": score,
            "correct": correct,
            "total": total_questions,
        })
    return results


def update_leaderboard(results: list, quiz_date: str):
    """Update daily and all-time leaderboard entries."""
    table = dynamodb.Table(LEADERBOARD_TABLE)
    periods = [f"daily:{quiz_date}", "alltime"]

    for entry in results:
        for period in periods:
            key = {"period": period, "user_id": entry["user_id"]}
            table.update_item(
                Key=key,
                UpdateExpression="SET display_name = :dn, score = if_not_exists(score, :zero) + :s, "
                                 "correct = if_not_exists(correct, :zero) + :c, "
                                 "total = if_not_exists(total, :zero) + :t, "
                                 "quizzes_taken = if_not_exists(quizzes_taken, :zero) + :one",
                ExpressionAttributeValues={
                    ":dn": entry["display_name"],
                    ":s": Decimal(str(entry["score"])),
                    ":c": Decimal(str(entry["correct"])),
                    ":t": Decimal(str(entry["total"])),
                    ":zero": Decimal("0"),
                    ":one": Decimal("1"),
                },
            )


def handler(event, context):
    quizzes = get_active_quizzes_to_score()
    scored = []

    for quiz in quizzes:
        results = score_quiz(quiz)
        quiz_date = quiz["created_at"][:10]
        update_leaderboard(results, quiz_date)

        # Mark quiz as scored
        dynamodb.Table(QUIZZES_TABLE).update_item(
            Key={"quiz_id": quiz["quiz_id"]},
            UpdateExpression="SET #s = :scored",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":scored": "scored"},
        )
        scored.append({"quiz_id": quiz["quiz_id"], "participants": len(results), "results": results})

    # Invoke results publisher for each scored date
    if scored and RESULTS_PUBLISHER_ARN:
        dates = {d["quiz_id"][:len("quiz-YYYY-MM-DD")] for d in scored}
        for quiz_id_prefix in dates:
            quiz_date = quiz_id_prefix.replace("quiz-", "")[:10]
            lambda_client.invoke(
                FunctionName=RESULTS_PUBLISHER_ARN,
                InvocationType="Event",
                Payload=json.dumps({"quiz_date": quiz_date}),
            )

    return {"scored_quizzes": len(scored), "details": scored}
