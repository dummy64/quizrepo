import json
import os
from urllib.parse import parse_qs

import boto3

CONFIG_TABLE = os.environ["CONFIG_TABLE"]
QUIZ_GENERATOR_ARN = os.environ.get("QUIZ_GENERATOR_ARN", "")

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")

VALID_KEYS = {"topic", "num_questions", "window_minutes", "frequency"}


def set_config(key: str, value: str) -> str:
    if key not in VALID_KEYS:
        return f"Unknown config key `{key}`. Valid: {', '.join(sorted(VALID_KEYS))}"
    dynamodb.Table(CONFIG_TABLE).put_item(Item={"config_key": key, "value": value})
    return f"✅ Set `{key}` = `{value}`"


def get_config(key: str) -> str:
    resp = dynamodb.Table(CONFIG_TABLE).get_item(Key={"config_key": key})
    if "Item" in resp:
        return f"`{key}` = `{resp['Item']['value']}`"
    return f"`{key}` is not set (using default)"


def trigger_quiz_now() -> str:
    if not QUIZ_GENERATOR_ARN:
        return "❌ Quiz generator not configured."
    lambda_client.invoke(FunctionName=QUIZ_GENERATOR_ARN, InvocationType="Event", Payload=b"{}")
    return "🚀 Quiz generation triggered! It will be posted shortly."


def parse_command(text: str) -> str:
    """Parse: /quiz now | /quiz config <key> <value> | /quiz config <key> | /quiz status"""
    parts = text.strip().split()
    if not parts:
        return "Usage: `/quiz now` | `/quiz config <key> [value]` | `/quiz status`"

    cmd = parts[0].lower()
    if cmd == "now":
        return trigger_quiz_now()
    elif cmd == "config" and len(parts) >= 2:
        key = parts[1]
        if len(parts) >= 3:
            return set_config(key, " ".join(parts[2:]))
        return get_config(key)
    elif cmd == "status":
        items = dynamodb.Table(CONFIG_TABLE).scan().get("Items", [])
        if not items:
            return "No config set — using all defaults."
        return "\n".join(f"`{i['config_key']}` = `{i['value']}`" for i in items)
    return "Unknown command. Use: `/quiz now` | `/quiz config <key> [value]` | `/quiz status`"


def handler(event, context):
    """Handles /quiz slash command from Slack or Teams."""
    body = parse_qs(event.get("body", ""))
    text = body.get("text", [""])[0]
    response_text = parse_command(text)
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"response_type": "ephemeral", "text": response_text}),
    }
