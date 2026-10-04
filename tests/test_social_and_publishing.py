from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.post import Post
from app.models.scheduled_post import ScheduledPost
from app.models.social_account import SocialAccount
from app.services.token_crypto import decrypt_token


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self._payload

    def raise_for_status(self):
        if not self.is_success:
            import httpx

            request = httpx.Request("GET", "https://example.test")
            response = httpx.Response(self.status_code, request=request, text=self.text)
            raise httpx.HTTPStatusError("mock error", request=request, response=response)


def _create_post(client, auth_headers, platform="facebook", media_url=None):
    response = client.post(
        "/api/v1/posts",
        headers=auth_headers,
        json={
            "title": "CreatorOS QA post",
            "caption": "CreatorOS end-to-end publishing test.",
            "platform": platform,
            "media_url": media_url,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health_reports_exact_scheduler():
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        scheduler = response.json()["scheduler"]
        assert scheduler["running"] is True
        assert scheduler["mode"] == "exact-time"


def test_facebook_oauth_connect_and_callback(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "meta_app_id", "meta-app-id")
    monkeypatch.setattr(settings, "meta_app_secret", "meta-app-secret")
    monkeypatch.setattr(
        settings,
        "meta_redirect_uri",
        "https://api.example.com/api/v1/social-accounts/facebook/callback",
    )
    monkeypatch.setattr(settings, "frontend_url", "https://creatoros.example.com")
    monkeypatch.setattr(settings, "meta_graph_base_url", "https://graph.facebook.com/v26.0")

    connect = client.get("/api/v1/social-accounts/facebook/connect", headers=auth_headers)
    assert connect.status_code == 200, connect.text
    authorization_url = connect.json()["authorization_url"]
    parsed = urlparse(authorization_url)
    query = parse_qs(parsed.query)
    state = query["state"][0]
    assert query["client_id"][0] == "meta-app-id"
    assert "pages_manage_posts" in query["scope"][0]

    calls = []

    def fake_get(url, params=None, timeout=30):
        calls.append((url, params))
        if url.endswith("/oauth/access_token") and params.get("grant_type") == "fb_exchange_token":
            return FakeResponse({"access_token": "long-user-token"})
        if url.endswith("/oauth/access_token"):
            return FakeResponse({"access_token": "short-user-token"})
        if url.endswith("/me/accounts"):
            assert params["access_token"] == "long-user-token"
            return FakeResponse(
                {
                    "data": [
                        {
                            "id": "1445595295293093",
                            "name": "CreatorOS AI",
                            "access_token": "page-access-token",
                            "tasks": ["CREATE_CONTENT", "ANALYZE", "MANAGE"],
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected Meta URL: {url}")

    import app.api.routes.social_accounts as social_routes

    monkeypatch.setattr(social_routes.httpx, "get", fake_get)

    callback = client.get(
        "/api/v1/social-accounts/facebook/callback",
        params={"code": "oauth-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code in {302, 307}
    assert callback.headers["location"] == "https://creatoros.example.com/social-accounts?facebook=connected"

    db = SessionLocal()
    try:
        account = db.query(SocialAccount).filter(SocialAccount.platform == "facebook").order_by(SocialAccount.created_at.desc()).first()
        assert account is not None
        assert account.platform_account_id == "1445595295293093"
        assert account.account_name == "CreatorOS AI"
        assert decrypt_token(account.access_token) == "page-access-token"
    finally:
        db.close()

    assert any(url.endswith("/me/accounts") for url, _ in calls)


def test_live_facebook_text_publish_uses_page_id(client, auth_headers, monkeypatch):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "987654321",
            "account_name": "CreatorOS Test Page",
            "access_token": "live-page-token",
        },
    )
    assert social.status_code == 201, social.text
    post = _create_post(client, auth_headers)

    monkeypatch.setattr(settings, "social_publish_mode", "live")

    captured = {}

    def fake_post(url, data=None, timeout=30):
        captured["url"] = url
        captured["data"] = data
        return FakeResponse({"id": "987654321_post123"})

    import app.services.social_publish as social_publish

    monkeypatch.setattr(social_publish.httpx, "post", fake_post)

    published = client.post(f"/api/v1/publishing/posts/{post['id']}", headers=auth_headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["mode"] == "live"
    assert captured["url"].endswith("/987654321/feed")
    assert captured["data"]["access_token"] == "live-page-token"


def test_due_scheduled_post_is_processed(client, auth_headers):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "due-page-id",
            "account_name": "Due Test Page",
            "access_token": "due-token",
        },
    )
    assert social.status_code == 201, social.text
    post = _create_post(client, auth_headers)

    schedule_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    scheduled = client.post(
        f"/api/v1/posts/{post['id']}/schedule",
        headers=auth_headers,
        json={"schedule_time": schedule_at.isoformat(), "platform": "facebook"},
    )
    assert scheduled.status_code == 200, scheduled.text

    db = SessionLocal()
    try:
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post["id"]).first()
        assert schedule is not None
        schedule.schedule_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    processed = client.post("/api/v1/publishing/process-due", headers=auth_headers)
    assert processed.status_code == 200, processed.text
    assert processed.json()["processed"] == 1
    assert processed.json()["published"] == 1

    db = SessionLocal()
    try:
        row = db.query(Post).filter(Post.id == post["id"]).first()
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post["id"]).first()
        assert row.status == "published"
        assert schedule.publish_state == "published"
    finally:
        db.close()


def test_failed_post_now_keeps_draft_retryable(client, auth_headers, monkeypatch):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "fail-page-id",
            "account_name": "Failure Test Page",
            "access_token": "fail-token",
        },
    )
    assert social.status_code == 201, social.text
    post = _create_post(client, auth_headers)

    monkeypatch.setattr(settings, "social_publish_mode", "live")

    def fake_post(url, data=None, timeout=30):
        return FakeResponse({"error": {"message": "Meta rejected the request"}}, status_code=400)

    import app.services.social_publish as social_publish

    monkeypatch.setattr(social_publish.httpx, "post", fake_post)

    response = client.post(f"/api/v1/publishing/posts/{post['id']}", headers=auth_headers)
    assert response.status_code == 502

    db = SessionLocal()
    try:
        row = db.query(Post).filter(Post.id == post["id"]).first()
        assert row.status == "draft"
    finally:
        db.close()


def test_live_facebook_video_publish_uses_videos_endpoint(client, auth_headers, monkeypatch):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "video-page-id",
            "account_name": "Video Test Page",
            "access_token": "video-page-token",
        },
    )
    assert social.status_code == 201, social.text

    post = _create_post(
        client,
        auth_headers,
        media_url="https://cdn.example.com/creator-video.mp4?download=1",
    )
    monkeypatch.setattr(settings, "social_publish_mode", "live")

    captured = {}

    def fake_post(url, data=None, timeout=30):
        captured["url"] = url
        captured["data"] = data
        captured["timeout"] = timeout
        return FakeResponse({"id": "video-123"})

    import app.services.social_publish as social_publish

    monkeypatch.setattr(social_publish.httpx, "post", fake_post)

    published = client.post(f"/api/v1/publishing/posts/{post['id']}", headers=auth_headers)
    assert published.status_code == 200, published.text
    assert captured["url"].endswith("/video-page-id/videos")
    assert captured["data"]["file_url"].startswith("https://cdn.example.com/")
    assert captured["data"]["description"] == "CreatorOS end-to-end publishing test."
    assert captured["data"]["access_token"] == "video-page-token"
    assert captured["timeout"] == 60
