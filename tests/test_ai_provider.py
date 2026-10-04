import app.services.ai as ai
from app.core.config import settings
from app.services.gemini import GeminiUnavailable


def test_gemini_provider_is_used(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "ai_fallback_enabled", False)

    def fake_gemini(prompt: str, response_schema: dict | None = None) -> dict:
        assert "Instagram" in prompt or "instagram" in prompt
        assert response_schema == ai.CAPTION_SCHEMA
        return {
            "caption": "Build smarter creator workflows with AI.",
            "cta": "Save this for later.",
            "hashtags": [f"#creator{i}" for i in range(10)],
        }

    monkeypatch.setattr(ai, "gemini_generate_json", fake_gemini)
    result = ai.generate_caption(
        "AI creator workflows",
        "A short productivity post",
        "professional",
        "instagram",
    )

    assert result["source"] == "gemini"
    assert result["caption"]
    assert len(result["hashtags"]) == 10


def test_gemini_failure_uses_demo_fallback(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "ai_fallback_enabled", True)

    def unavailable(prompt: str, response_schema: dict | None = None) -> dict:
        raise GeminiUnavailable("temporary outage")

    monkeypatch.setattr(ai, "gemini_generate_json", unavailable)
    result = ai.generate_caption(
        "Creator productivity",
        "Three practical habits",
        "professional",
        "facebook",
    )

    assert result["source"] == "fallback"
    assert result["caption"]
    assert result["hashtags"]
