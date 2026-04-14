import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qs

import boto3
from slack_sdk import WebClient

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
QUIZZES_TABLE = os.environ["QUIZZES_TABLE"]
RESPONSES_TABLE = os.environ["RESPONSES_TABLE"]

slack = WebClient(token=SLACK_BOT_TOKEN)
dynamodb = boto3.resource("dynamodb")


def verify_slack_signature(event: dict) -> bool:
    headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
    timestamp = headers.get("x-slack-request-timestamp", "")
    if abs(time.time() - int(timestamp or 0)) > 300:
        return False
    sig_basestring = f"v0:{timestamp}:{event.get('body', '')}"
    my_sig = "v0=" + hmac.new(
        SLACK_SIGNING_SECRET.encode(), sig_basestring.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(my_sig, headers.get("x-slack-signature", ""))


def build_quiz_blocks(quiz: dict) -> list:
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": f"🧠 Daily Quiz: {quiz['topic']}"}}]
    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"⏰ Closes at: {quiz['closes_at']} UTC"}})

    for q in quiz["questions"]:
        options_text = "\n".join(f"*{k}*: {v}" for k, v in q["options"].items())
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*{q['text']}*\n{options_text}"}})
        blocks.append({
            "type": "actions",
            "block_id": f"answer_{q['question_id']}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": opt_key},
                    "action_id": f"ans_{q['question_id']}_{opt_key}",
                    "value": json.dumps({"quiz_id": quiz["quiz_id"], "question_id": q["question_id"], "option": opt_key}),
                }
                for opt_key in q["options"]
            ],
        })
    blocks.append({"type": "actions", "block_id": "submit_quiz", "elements": [{
        "type": "button",
        "text": {"type": "plain_text", "text": "✅ Submit Answers"},
        "style": "primary",
        "action_id": "submit_quiz",
        "value": quiz["quiz_id"],
    }]})
    return blocks


def post_quiz_to_slack(channel: str, quiz: dict):
    blocks = build_quiz_blocks(quiz)
    slack.chat_postMessage(channel=channel, text=f"Daily Quiz: {quiz['topic']}", blocks=blocks)


def handle_interaction(event, context):
    if not verify_slack_signature(event):
        return {"statusCode": 401, "body": "Invalid signature"}

    body = parse_qs(event.get("body", ""))
    payload = json.loads(body.get("payload", ["{}"])[0])

    if payload.get("type") == "block_actions":
        user = payload["user"]
        actions = payload.get("actions", [])

        for action in actions:
            if action["action_id"] == "submit_quiz":
                quiz_id = action["value"]
                # Collect answers from message state
                state_values = payload.get("state", {}).get("values", {})
                answers = {}
                for block_id, block_data in state_values.items():
                    if block_id.startswith("answer_"):
                        for action_id, action_data in block_data.items():
                            if "selected_option" in action_data:
                                qid = block_id.replace("answer_", "")
                                answers[qid] = action_data["selected_option"]

                # Also collect from button clicks stored in the interaction
                from lambdas.answer_collector.handler import save_response
                result = save_response(
                    quiz_id=quiz_id,
                    user_id=user["id"],
                    platform="slack",
                    display_name=user.get("name", user["id"]),
                    answers=answers,
                )
                slack.chat_postEphemeral(
                    channel=payload["channel"]["id"],
                    user=user["id"],
                    text=result["message"],
                )

    return {"statusCode": 200, "body": ""}


def handler(event, context):
    """Main entry: routes quiz posting (EventBridge) vs interaction (API Gateway)."""
    if "body" in event:
        return handle_interaction(event, context)

    # Triggered by quiz generator — post quiz to channel
    quiz_id = event.get("quiz_id")
    channel = event.get("channel", os.environ.get("SLACK_CHANNEL", ""))
    if quiz_id and channel:
        quiz = dynamodb.Table(QUIZZES_TABLE).get_item(Key={"quiz_id": quiz_id}).get("Item")
        if quiz:
            post_quiz_to_slack(channel, quiz)
    return {"statusCode": 200}
