import json

from google import genai
from google.genai import errors, types

from app.core.config import settings


class GeminiUnavailable(RuntimeError):
    pass


def generate_json(prompt: str, response_schema: dict | None = None) -> dict:
    api_key = (settings.gemini_api_key or "").strip()
    if not api_key:
        raise GeminiUnavailable("GEMINI_API_KEY is not configured")

    try:
        client = genai.Client(api_key=api_key)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=response_schema,
        )
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=config,
        )
        text = (response.text or "").strip()
        if not text:
            raise GeminiUnavailable("Gemini returned an empty response")
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise GeminiUnavailable("Gemini did not return a JSON object")
        return payload
    except GeminiUnavailable:
        raise
    except errors.APIError as exc:
        code = getattr(exc, "code", "unknown")
        message = getattr(exc, "message", str(exc))
        raise GeminiUnavailable(f"Gemini API error ({code}): {message}") from exc
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise GeminiUnavailable(f"Invalid Gemini response: {exc}") from exc
