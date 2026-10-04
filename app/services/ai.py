import json
import re

from app.core.config import settings
from app.services.gemini import GeminiUnavailable, generate_json as gemini_generate_json
from app.services.ollama import OllamaUnavailable, generate_json as ollama_generate_json


class AIUnavailable(RuntimeError):
    pass


CAPTION_SCHEMA = {
    "type": "object",
    "properties": {
        "caption": {"type": "string"},
        "cta": {"type": "string"},
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 10,
            "maxItems": 20,
        },
    },
    "required": ["caption", "cta", "hashtags"],
}

HASHTAG_SCHEMA = {
    "type": "object",
    "properties": {
        "hashtags": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 10,
            "maxItems": 20,
        }
    },
    "required": ["hashtags"],
}

ANALYZE_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer", "minimum": 0, "maximum": 100},
        "strengths": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    },
    "required": ["score", "strengths", "suggestions"],
}


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


def _generate_json(prompt: str, schema: dict, ollama_prompt: str | None = None) -> tuple[dict, str]:
    provider = settings.ai_provider.strip().lower()
    try:
        if provider == "gemini":
            return gemini_generate_json(prompt, response_schema=schema), "gemini"
        if provider == "ollama":
            return ollama_generate_json(ollama_prompt or prompt), "ollama"
        raise AIUnavailable(f"Unsupported AI provider: {settings.ai_provider}")
    except (GeminiUnavailable, OllamaUnavailable) as exc:
        raise AIUnavailable(str(exc)) from exc


def _normalize_hashtags(values: object, fallback_text: str, limit: int = 20) -> list[str]:
    if not isinstance(values, list):
        return _hashtags(fallback_text, min(limit, 16))
    tags = []
    for value in values:
        tag = str(value).strip().replace(" ", "")
        if not tag:
            continue
        tag = tag if tag.startswith("#") else f"#{tag.lstrip('#')}"
        if tag not in tags:
            tags.append(tag)
    return tags[:limit] or _hashtags(fallback_text, min(limit, 16))


def generate_caption(topic: str, description: str | None, tone: str, platform: str) -> dict:
    context = description or ""
    prompt = (
        f"Create social-media copy for {platform}. Topic: {topic}. "
        f"Description/context: {context}. Tone: {tone}. "
        "Write a concise practical caption, a clear call to action, and 10-20 relevant hashtags."
    )
    ollama_prompt = (
        "Return ONLY valid JSON with keys caption, cta, hashtags. hashtags must be an array of 10-20 strings.\n"
        f"Platform: {platform}\nTopic: {topic}\nDescription: {context}\nTone: {tone}\n"
        "Keep the caption concise and practical."
    )
    try:
        data, source = _generate_json(prompt, CAPTION_SCHEMA, ollama_prompt)
        hashtags = _normalize_hashtags(data.get("hashtags"), topic + " " + context)
        return {
            "caption": str(data.get("caption", "")).strip(),
            "cta": str(data.get("cta", "")).strip(),
            "hashtags": hashtags,
            "source": source,
        }
    except AIUnavailable:
        if not settings.ai_fallback_enabled:
            raise
        caption = f"{topic.strip()}. {description.strip() if description else 'A practical idea worth sharing with your audience.'}"
        return {
            "caption": caption[:1200],
            "cta": "What do you think? Share your take below.",
            "hashtags": _hashtags(topic + " " + context),
            "source": "fallback",
        }


def generate_hashtags(topic: str, caption: str | None, platform: str) -> dict:
    context = caption or ""
    prompt = (
        f"Generate 10-20 relevant social-media hashtags for {platform}. "
        f"Topic: {topic}. Existing caption/context: {context}."
    )
    ollama_prompt = (
        'Return ONLY JSON: {"hashtags":["#tag"]} with 10-20 relevant hashtags. '
        f"Platform: {platform}. Topic: {topic}. Caption: {context}"
    )
    try:
        data, source = _generate_json(prompt, HASHTAG_SCHEMA, ollama_prompt)
        return {
            "hashtags": _normalize_hashtags(data.get("hashtags"), topic + " " + context),
            "source": source,
        }
    except AIUnavailable:
        if not settings.ai_fallback_enabled:
            raise
        return {
            "hashtags": _hashtags(topic + " " + context, 16),
            "source": "fallback",
        }


def analyze_content(caption: str, platform: str) -> dict:
    prompt = (
        f"Analyze this {platform} caption for clarity, hook quality, structure, and call-to-action strength. "
        f"Give a quality score from 0 to 100, up to three strengths, and up to three practical improvements. "
        f"Caption: {caption}"
    )
    ollama_prompt = (
        "Return ONLY JSON with integer score 0-100, strengths array, suggestions array. "
        f"Platform: {platform}. Caption: {caption}"
    )
    try:
        data, source = _generate_json(prompt, ANALYZE_SCHEMA, ollama_prompt)
        return {
            "score": max(0, min(100, int(data.get("score", 70)))),
            "strengths": [str(x) for x in data.get("strengths", [])][:3],
            "suggestions": [str(x) for x in data.get("suggestions", [])][:3],
            "source": source,
        }
    except (AIUnavailable, TypeError, ValueError):
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
        return {
            "score": min(score, 100),
            "strengths": strengths[:3],
            "suggestions": suggestions[:3],
            "source": "fallback",
        }


def serialize_log(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)
