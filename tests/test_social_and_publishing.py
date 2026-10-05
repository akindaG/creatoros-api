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


def test_instagram_oauth_connect_and_callback(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "instagram_app_id", "instagram-app-id")
    monkeypatch.setattr(settings, "instagram_app_secret", "instagram-app-secret")
    monkeypatch.setattr(
        settings,
        "instagram_redirect_uri",
        "https://api.example.com/api/v1/social-accounts/instagram/callback",
    )
    monkeypatch.setattr(settings, "frontend_url", "https://creatoros.example.com")
    monkeypatch.setattr(settings, "instagram_graph_base_url", "https://graph.instagram.com/v26.0")
    monkeypatch.setattr(
        settings,
        "instagram_scopes",
        "instagram_business_basic,instagram_business_content_publish,instagram_business_manage_insights",
    )

    connect = client.get("/api/v1/social-accounts/instagram/connect", headers=auth_headers)
    assert connect.status_code == 200, connect.text
    authorization_url = connect.json()["authorization_url"]
    parsed = urlparse(authorization_url)
    query = parse_qs(parsed.query)
    state = query["state"][0]
    assert parsed.netloc == "www.instagram.com"
    assert query["client_id"][0] == "instagram-app-id"
    assert "instagram_business_basic" in query["scope"][0]
    assert "instagram_business_content_publish" in query["scope"][0]
    assert "instagram_business_manage_insights" in query["scope"][0]

    def fake_post(url, data=None, timeout=30):
        assert url == settings.instagram_oauth_token_url
        assert data["client_id"] == "instagram-app-id"
        assert data["client_secret"] == "instagram-app-secret"
        assert data["grant_type"] == "authorization_code"
        return FakeResponse(
            {
                "access_token": "short-instagram-token",
                "user_id": "17841400000000000",
            }
        )

    def fake_get(url, params=None, timeout=30):
        if url == "https://graph.instagram.com/access_token":
            assert params["grant_type"] == "ig_exchange_token"
            assert params["access_token"] == "short-instagram-token"
            return FakeResponse(
                {
                    "access_token": "long-instagram-token",
                    "expires_in": 5184000,
                }
            )
        if url == "https://graph.instagram.com/v26.0/me":
            assert params["access_token"] == "long-instagram-token"
            return FakeResponse(
                {
                    "user_id": "17841400000000000",
                    "username": "creatoros_test",
                    "name": "CreatorOS Test",
                    "account_type": "BUSINESS",
                    "followers_count": 321,
                    "media_count": 12,
                }
            )
        raise AssertionError(f"Unexpected Instagram URL: {url}")

    import app.api.routes.social_accounts as social_routes

    monkeypatch.setattr(social_routes.httpx, "post", fake_post)
    monkeypatch.setattr(social_routes.httpx, "get", fake_get)

    callback = client.get(
        "/api/v1/social-accounts/instagram/callback",
        params={"code": "instagram-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code in {302, 307}
    assert callback.headers["location"] == "https://creatoros.example.com/social-accounts?instagram=connected"

    db = SessionLocal()
    try:
        account = (
            db.query(SocialAccount)
            .filter(SocialAccount.platform == "instagram")
            .order_by(SocialAccount.created_at.desc())
            .first()
        )
        assert account is not None
        assert account.platform_account_id == "17841400000000000"
        assert account.account_name == "CreatorOS Test"
        assert account.username == "creatoros_test"
        assert decrypt_token(account.access_token) == "long-instagram-token"
        assert account.token_expires_at is not None
    finally:
        db.close()


def test_live_instagram_image_publish_uses_instagram_graph(client, auth_headers, monkeypatch):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "instagram",
            "platform_account_id": "17841400000000000",
            "account_name": "CreatorOS Instagram",
            "username": "creatoros_test",
            "access_token": "live-instagram-token",
        },
    )
    assert social.status_code == 201, social.text
    post = _create_post(
        client,
        auth_headers,
        platform="instagram",
        media_url="https://cdn.example.com/creator-image.jpg",
    )

    monkeypatch.setattr(settings, "social_publish_mode", "live")
    monkeypatch.setattr(settings, "instagram_graph_base_url", "https://graph.instagram.com/v26.0")

    calls = []

    def fake_post(url, data=None, timeout=30):
        calls.append((url, data, timeout))
        if url.endswith("/media_publish"):
            return FakeResponse({"id": "17900000000000000"})
        if url.endswith("/media"):
            return FakeResponse({"id": "18000000000000000"})
        raise AssertionError(f"Unexpected Instagram publish URL: {url}")

    def fake_get(url, params=None, timeout=30):
        if url.endswith("/18000000000000000"):
            return FakeResponse({"status_code": "FINISHED", "status": "Finished"})
        raise AssertionError(f"Unexpected Instagram status URL: {url}")

    import app.services.social_publish as social_publish

    monkeypatch.setattr(social_publish.httpx, "post", fake_post)
    monkeypatch.setattr(social_publish.httpx, "get", fake_get)

    published = client.post(f"/api/v1/publishing/posts/{post['id']}", headers=auth_headers)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["mode"] == "live"
    assert calls[0][0] == "https://graph.instagram.com/v26.0/17841400000000000/media"
    assert calls[0][1]["image_url"] == "https://cdn.example.com/creator-image.jpg"
    assert calls[0][1]["access_token"] == "live-instagram-token"
    assert calls[1][0] == "https://graph.instagram.com/v26.0/17841400000000000/media_publish"


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


def test_publish_mode_is_normalized(client, auth_headers, monkeypatch):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "normalized-page-id",
            "account_name": "Normalized Page",
            "access_token": "normalized-token",
        },
    )
    assert social.status_code == 201, social.text
    post = _create_post(client, auth_headers)

    monkeypatch.setattr(settings, "social_publish_mode", " LIVE ")

    captured = {}

    def fake_post(url, data=None, timeout=30):
        captured["url"] = url
        return FakeResponse({"id": "normalized-post-id"})

    import app.services.social_publish as social_publish

    monkeypatch.setattr(social_publish.httpx, "post", fake_post)

    response = client.post(f"/api/v1/publishing/posts/{post['id']}", headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["mode"] == "live"
    assert captured["url"].endswith("/normalized-page-id/feed")


def test_publishing_readiness_reports_page_and_mode(client, auth_headers, monkeypatch):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "readiness-page-id",
            "account_name": "Readiness Page",
            "access_token": "readiness-token",
        },
    )
    assert social.status_code == 201, social.text
    monkeypatch.setattr(settings, "social_publish_mode", "live")

    response = client.get("/api/v1/publishing/readiness", headers=auth_headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["live"] is True
    assert payload["mode"] == "live"
    assert payload["facebook_connected"] is True
    assert payload["facebook_page_id"] == "readiness-page-id"
    assert payload["facebook_page_name"] == "Readiness Page"
    assert payload["target_type"] == "facebook_page"
    assert "running" in payload["scheduler"]


def test_facebook_profile_manual_share_schedule_does_not_require_page_connection(client, auth_headers):
    post = _create_post(client, auth_headers, platform="facebook_profile")
    schedule_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    scheduled = client.post(
        f"/api/v1/posts/{post['id']}/schedule",
        headers=auth_headers,
        json={
            "schedule_time": schedule_at.isoformat(),
            "platform": "facebook_profile",
        },
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["platform"] == "facebook_profile"
    assert scheduled.json()["publish_state"] == "scheduled"


def test_due_facebook_profile_schedule_becomes_ready_to_share(client, auth_headers):
    post = _create_post(client, auth_headers, platform="facebook_profile")
    schedule_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    scheduled = client.post(
        f"/api/v1/posts/{post['id']}/schedule",
        headers=auth_headers,
        json={
            "schedule_time": schedule_at.isoformat(),
            "platform": "facebook_profile",
        },
    )
    assert scheduled.status_code == 200, scheduled.text

    db = SessionLocal()
    try:
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post["id"]).first()
        schedule.schedule_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    processed = client.post("/api/v1/publishing/process-due", headers=auth_headers)
    assert processed.status_code == 200, processed.text
    payload = processed.json()
    assert payload["processed"] == 1
    assert payload["ready_to_share"] == 1
    assert payload["published"] == 0
    assert payload["failed"] == 0
    assert payload["results"][0]["mode"] == "manual"

    db = SessionLocal()
    try:
        row = db.query(Post).filter(Post.id == post["id"]).first()
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post["id"]).first()
        assert row.status == "ready_to_share"
        assert schedule.publish_state == "ready_to_share"
    finally:
        db.close()


def test_facebook_profile_cannot_use_automatic_publish_endpoint(client, auth_headers):
    post = _create_post(client, auth_headers, platform="facebook_profile")
    response = client.post(f"/api/v1/publishing/posts/{post['id']}", headers=auth_headers)
    assert response.status_code == 400
    assert "manual sharing" in response.json()["detail"].lower()


def test_facebook_profile_can_be_marked_shared(client, auth_headers):
    post = _create_post(client, auth_headers, platform="facebook_profile")
    schedule_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    scheduled = client.post(
        f"/api/v1/posts/{post['id']}/schedule",
        headers=auth_headers,
        json={
            "schedule_time": schedule_at.isoformat(),
            "platform": "facebook_profile",
        },
    )
    assert scheduled.status_code == 200, scheduled.text

    marked = client.post(
        f"/api/v1/publishing/posts/{post['id']}/mark-shared",
        headers=auth_headers,
    )
    assert marked.status_code == 200, marked.text
    assert marked.json()["status"] == "shared"

    db = SessionLocal()
    try:
        row = db.query(Post).filter(Post.id == post["id"]).first()
        schedule = db.query(ScheduledPost).filter(ScheduledPost.post_id == post["id"]).first()
        assert row.status == "shared"
        assert schedule.publish_state == "shared"
    finally:
        db.close()


def test_multi_platform_schedule_creates_same_timestamp_for_connected_channels(client, auth_headers):
    facebook = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "multi-page-id",
            "account_name": "Multi Page",
            "access_token": "multi-page-token",
        },
    )
    assert facebook.status_code == 201, facebook.text
    instagram = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "instagram",
            "platform_account_id": "17841411111111111",
            "account_name": "Multi Instagram",
            "username": "multi_creator",
            "access_token": "multi-instagram-token",
        },
    )
    assert instagram.status_code == 201, instagram.text

    post = _create_post(
        client,
        auth_headers,
        platform="instagram",
        media_url="https://cdn.example.com/multi-image.jpg",
    )
    schedule_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    response = client.post(
        f"/api/v1/posts/{post['id']}/schedule-multi",
        headers=auth_headers,
        json={
            "schedule_time": schedule_at.isoformat(),
            "platforms": ["instagram", "facebook"],
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["count"] == 2
    assert payload["schedule_group_id"]
    assert {item["platform"] for item in payload["items"]} == {"instagram", "facebook"}
    assert len({item["schedule_time"] for item in payload["items"]}) == 1
    assert {item["schedule_group_id"] for item in payload["items"]} == {payload["schedule_group_id"]}

    db = SessionLocal()
    try:
        rows = (
            db.query(ScheduledPost, Post)
            .join(Post, Post.id == ScheduledPost.post_id)
            .filter(Post.title == "CreatorOS QA post", Post.status == "scheduled")
            .all()
        )
        matching = [(schedule, row) for schedule, row in rows if row.platform in {"instagram", "facebook"}]
        assert len(matching) >= 2
        times = {schedule.schedule_time for schedule, _ in matching}
        assert len(times) == 1
        group_ids = {str(schedule.schedule_group_id) for schedule, _ in matching}
        assert payload["schedule_group_id"] in group_ids
    finally:
        db.close()

    rescheduled_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    rescheduled = client.put(
        f"/api/v1/schedule-groups/{payload['schedule_group_id']}",
        headers=auth_headers,
        json={"schedule_time": rescheduled_at.isoformat()},
    )
    assert rescheduled.status_code == 200, rescheduled.text
    assert rescheduled.json()["count"] == 2

    calendar = client.get("/api/v1/calendar", headers=auth_headers)
    assert calendar.status_code == 200, calendar.text
    grouped = [
        item
        for item in calendar.json()
        if item["schedule_group_id"] == payload["schedule_group_id"]
    ]
    assert len(grouped) == 2
    assert len({item["schedule_time"] for item in grouped}) == 1

    cancelled = client.delete(
        f"/api/v1/schedule-groups/{payload['schedule_group_id']}",
        headers=auth_headers,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["count"] == 2

    calendar_after_cancel = client.get("/api/v1/calendar", headers=auth_headers)
    assert calendar_after_cancel.status_code == 200, calendar_after_cancel.text
    assert not [
        item
        for item in calendar_after_cancel.json()
        if item["schedule_group_id"] == payload["schedule_group_id"]
    ]


def test_due_multi_platform_schedule_publishes_both_channels(client, auth_headers, monkeypatch):
    facebook = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "due-multi-page-id",
            "account_name": "Due Multi Page",
            "access_token": "due-multi-page-token",
        },
    )
    assert facebook.status_code == 201, facebook.text
    instagram = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "instagram",
            "platform_account_id": "17841433333333333",
            "account_name": "Due Multi Instagram",
            "username": "due_multi_creator",
            "access_token": "due-multi-instagram-token",
        },
    )
    assert instagram.status_code == 201, instagram.text

    post = _create_post(
        client,
        auth_headers,
        platform="instagram",
        media_url="https://cdn.example.com/due-multi.jpg",
    )
    schedule_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    scheduled = client.post(
        f"/api/v1/posts/{post['id']}/schedule-multi",
        headers=auth_headers,
        json={
            "schedule_time": schedule_at.isoformat(),
            "platforms": ["instagram", "facebook"],
        },
    )
    assert scheduled.status_code == 200, scheduled.text
    group_id = scheduled.json()["schedule_group_id"]

    db = SessionLocal()
    try:
        schedules = (
            db.query(ScheduledPost)
            .filter(ScheduledPost.schedule_group_id == group_id)
            .all()
        )
        assert len(schedules) == 2
        for schedule in schedules:
            schedule.schedule_time = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    monkeypatch.setattr(settings, "social_publish_mode", "live")
    calls = []

    def fake_post(url, data=None, timeout=30):
        calls.append(url)
        if url.endswith("/media_publish"):
            return FakeResponse({"id": "ig-due-published-id"})
        if "graph.instagram.com" in url and url.endswith("/media"):
            return FakeResponse({"id": "ig-due-container-id"})
        if url.endswith("/due-multi-page-id/photos"):
            return FakeResponse({"id": "fb-due-published-id"})
        raise AssertionError(f"Unexpected due multi-platform publish URL: {url}")

    def fake_get(url, params=None, timeout=30):
        if url.endswith("/ig-due-container-id"):
            return FakeResponse({"status_code": "FINISHED", "status": "Finished"})
        raise AssertionError(f"Unexpected due multi-platform status URL: {url}")

    import app.services.social_publish as social_publish

    monkeypatch.setattr(social_publish.httpx, "post", fake_post)
    monkeypatch.setattr(social_publish.httpx, "get", fake_get)

    processed = client.post("/api/v1/publishing/process-due", headers=auth_headers)
    assert processed.status_code == 200, processed.text
    payload = processed.json()
    assert payload["processed"] == 2
    assert payload["published"] == 2
    assert payload["failed"] == 0
    assert any("graph.instagram.com" in url and url.endswith("/media") for url in calls)
    assert any(url.endswith("/due-multi-page-id/photos") for url in calls)

    db = SessionLocal()
    try:
        rows = (
            db.query(ScheduledPost, Post)
            .join(Post, Post.id == ScheduledPost.post_id)
            .filter(ScheduledPost.schedule_group_id == group_id)
            .all()
        )
        assert len(rows) == 2
        assert {schedule.publish_state for schedule, _ in rows} == {"published"}
        assert {row.status for _, row in rows} == {"published"}
        assert {row.platform for _, row in rows} == {"instagram", "facebook"}
    finally:
        db.close()


def test_multi_platform_post_now_fans_out_to_instagram_and_facebook(client, auth_headers, monkeypatch):
    facebook = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "fanout-page-id",
            "account_name": "Fanout Page",
            "access_token": "fanout-page-token",
        },
    )
    assert facebook.status_code == 201, facebook.text
    instagram = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "instagram",
            "platform_account_id": "17841422222222222",
            "account_name": "Fanout Instagram",
            "username": "fanout_creator",
            "access_token": "fanout-instagram-token",
        },
    )
    assert instagram.status_code == 201, instagram.text

    post = _create_post(
        client,
        auth_headers,
        platform="instagram",
        media_url="https://cdn.example.com/fanout-image.jpg",
    )
    monkeypatch.setattr(settings, "social_publish_mode", "live")
    calls = []

    def fake_post(url, data=None, timeout=30):
        calls.append((url, data, timeout))
        if url.endswith("/media_publish"):
            return FakeResponse({"id": "ig-published-id"})
        if "graph.instagram.com" in url and url.endswith("/media"):
            return FakeResponse({"id": "ig-container-id"})
        if url.endswith("/fanout-page-id/photos"):
            return FakeResponse({"id": "fb-published-id"})
        raise AssertionError(f"Unexpected multi-platform publish URL: {url}")

    def fake_get(url, params=None, timeout=30):
        if url.endswith("/ig-container-id"):
            return FakeResponse({"status_code": "FINISHED", "status": "Finished"})
        raise AssertionError(f"Unexpected multi-platform status URL: {url}")

    import app.services.social_publish as social_publish

    monkeypatch.setattr(social_publish.httpx, "post", fake_post)
    monkeypatch.setattr(social_publish.httpx, "get", fake_get)

    response = client.post(
        f"/api/v1/publishing/posts/{post['id']}/multi",
        headers=auth_headers,
        json={"platforms": ["instagram", "facebook"]},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "published"
    assert payload["published"] == 2
    assert payload["failed"] == 0
    assert {item["platform"] for item in payload["results"]} == {"instagram", "facebook"}
    assert any("graph.instagram.com" in url and url.endswith("/media") for url, _, _ in calls)
    assert any(url.endswith("/fanout-page-id/photos") for url, _, _ in calls)
