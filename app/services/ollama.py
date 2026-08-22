import json
import re

import httpx

from app.core.config import settings


class OllamaUnavailable(RuntimeError):
    pass


def generate_json(prompt: str) -> dict:
    try:
        response = httpx.post(
            f"{settings.ollama_base_url.rstrip('/')}/api/generate",
            json={"model": settings.ollama_model, "prompt": prompt, "stream": False},
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("Ollama did not return JSON")
        return json.loads(match.group(0))
    except (httpx.HTTPError, ValueError, json.JSONDecodeError, KeyError) as exc:
        raise OllamaUnavailable(str(exc)) from exc
