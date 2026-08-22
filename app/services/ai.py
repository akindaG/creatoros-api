import json
import re

from app.core.config import settings
from app.services.ollama import OllamaUnavailable, generate_json


def _hashtags(text: str, limit: int = 12) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9]+", text.lower())
    stop = {"about", "with", "from", "this", "that", "your", "have", "into", "content", "post"}
    unique = []
    for word in words:
        if len(word) < 3 or word in stop or word in unique:
            continue
        unique.append(word)
    base = unique[:8] + ["creator", "socialmedia", "growth", "creatortips"]
    return [f"#{word}" for word in base[:limit]]


def generate_caption(topic: str, description: str | None, tone: str, platform: str) -> dict:
    prompt = f"""Return ONLY valid JSON with keys caption, cta, hashtags. hashtags must be an array of 10-20 strings.\nPlatform: {platform}\nTopic: {topic}\nDescription: {description or ''}\nTone: {tone}\nKeep the caption concise and practical."""
    try:
        data = generate_json(prompt)
        hashtags = data.get("hashtags") or _hashtags(topic + " " + (description or ""))
        return {"caption": str(data.get("caption", "")).strip(), "cta": str(data.get("cta", "")).strip(), "hashtags": hashtags[:20], "source": "ollama"}
    except OllamaUnavailable:
        if not settings.ai_fallback_enabled:
            raise
        caption = f"{topic.strip()}. {description.strip() if description else 'A practical idea worth sharing with your audience.'}"
        return {"caption": caption[:1200], "cta": "What do you think? Share your take below.", "hashtags": _hashtags(topic + " " + (description or "")), "source": "fallback"}


def generate_hashtags(topic: str, caption: str | None, platform: str) -> dict:
    prompt = f"Return ONLY JSON: {{\"hashtags\":[\"#tag\"]}} with 10-20 relevant hashtags. Platform: {platform}. Topic: {topic}. Caption: {caption or ''}"
    try:
        data = generate_json(prompt)
        tags = [str(tag) for tag in data.get("hashtags", []) if str(tag).startswith("#")]
        return {"hashtags": tags[:20] or _hashtags(topic + " " + (caption or "")), "source": "ollama"}
    except OllamaUnavailable:
        if not settings.ai_fallback_enabled:
            raise
        return {"hashtags": _hashtags(topic + " " + (caption or ""), 16), "source": "fallback"}


def analyze_content(caption: str, platform: str) -> dict:
    prompt = f"Return ONLY JSON with integer score 0-100, strengths array, suggestions array. Platform: {platform}. Caption: {caption}"
    try:
        data = generate_json(prompt)
        return {
            "score": max(0, min(100, int(data.get("score", 70)))),
            "strengths": [str(x) for x in data.get("strengths", [])][:3],
            "suggestions": [str(x) for x in data.get("suggestions", [])][:3],
            "source": "ollama",
        }
    except (OllamaUnavailable, TypeError, ValueError):
        if not settings.ai_fallback_enabled:
            raise
        score = 55
        strengths = []
        suggestions = []
        length = len(caption.strip())
        if 80 <= length <= 500:
            score += 15
            strengths.append("Caption length is easy to consume")
        else:
            suggestions.append("Keep the caption between roughly 80 and 500 characters")
        if any(ch in caption for ch in "?!"):
            score += 10
            strengths.append("The copy has an engagement-oriented hook or question")
        else:
            suggestions.append("Add a question or stronger opening hook")
        if any(token in caption.lower() for token in ["comment", "share", "save", "follow", "tell me", "what do you think"]):
            score += 15
            strengths.append("A clear call to action is present")
        else:
            suggestions.append("Add a specific CTA such as comment, save, share, or follow")
        return {"score": min(score, 100), "strengths": strengths[:3], "suggestions": suggestions[:3], "source": "fallback"}


def serialize_log(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
