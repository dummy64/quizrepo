import json, os
from openai import OpenAI

client = None

def get_client():
    global client
    if not client:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return client


def generate_questions(topic: str, count: int = 50, content_text: str = None) -> list:
    """Generate quiz questions via ChatGPT. If content_text is provided, generate from that content."""
    if content_text:
        prompt = (
            f"Based on the following content, generate exactly {count} multiple-choice questions.\n\n"
            f"CONTENT:\n{content_text[:8000]}\n\n"
            "Return ONLY a JSON array of objects with keys: \"text\", \"options\" (object with A,B,C,D), \"correct\" (A/B/C/D), \"explanation\".\n"
            "No markdown, no extra text."
        )
    else:
        prompt = (
            f"Generate exactly {count} multiple-choice questions about: {topic}.\n"
            "Return ONLY a JSON array of objects with keys: \"text\", \"options\" (object with A,B,C,D), \"correct\" (A/B/C/D), \"explanation\".\n"
            "No markdown, no extra text."
        )

    resp = get_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.8,
        max_tokens=16000,
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def fetch_url_text(url: str) -> str:
    """Fetch text content from a URL."""
    import httpx
    resp = httpx.get(url, follow_redirects=True, timeout=15)
    resp.raise_for_status()
    # Simple HTML stripping
    import re
    text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:10000]
