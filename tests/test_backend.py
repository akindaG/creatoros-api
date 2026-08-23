from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.database import SessionLocal
from app.models.social_account import SocialAccount
from app.services.token_crypto import decrypt_token


def test_health(client):
    assert client.get("/health").status_code == 200
    db = client.get("/health/db")
    assert db.status_code == 200
    assert db.json()["result"] == 1


def test_auth_profile_and_password_reset(client):
    email = f"reset-{uuid4().hex[:10]}@example.com"
    password = "StrongPass123"
    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Reset Creator", "email": email, "password": password},
    )
    assert registered.status_code == 201, registered.text
    access_token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == email
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    token = forgot.json()["reset_token"]
    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": "NewStrongPass123"},
    )
    assert reset.status_code == 200
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "NewStrongPass123"},
    )
    assert login.status_code == 200


def test_social_credentials_are_encrypted(client, auth_headers):
    response = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "account_name": "123456789",
            "username": "creator-page",
            "access_token": "plain-secret-token",
        },
    )
    assert response.status_code == 201, response.text

    account_id = response.json()["id"]
    db = SessionLocal()
    try:
        account = db.query(SocialAccount).filter(SocialAccount.id == account_id).first()
        assert account is not None
        assert account.access_token != "plain-secret-token"
        assert account.access_token.startswith("enc:v1:")
        assert decrypt_token(account.access_token) == "plain-secret-token"
    finally:
        db.close()


def test_internal_cron_is_protected(client):
    denied = client.post("/api/v1/internal/process-due", headers={"X-Cron-Secret": "wrong"})
    assert denied.status_code == 401
    allowed = client.post("/api/v1/internal/process-due", headers={"X-Cron-Secret": "test-cron-secret"})
    assert allowed.status_code == 200
    assert "processed" in allowed.json()


def test_end_to_end_mvp(client):
    email = f"journey-{uuid4().hex[:10]}@example.com"
    password = "StrongPass123"
    assert client.post(
        "/api/v1/auth/register",
        json={"name": "Journey User", "email": email, "password": password},
    ).status_code == 201
    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    social = client.post(
        "/api/v1/social-accounts",
        headers=headers,
        json={
            "platform": "instagram",
            "account_name": "17890000000000000",
            "username": "creator",
            "access_token": "demo-token",
        },
    )
    assert social.status_code == 201, social.text

    post = client.post(
        "/api/v1/posts",
        headers=headers,
        json={
            "title": "AI productivity",
            "caption": "Three tools that save me time. What do you think? Save this post.",
            "platform": "instagram",
        },
    )
    assert post.status_code == 201, post.text
    post_id = post.json()["id"]

    schedule_at = datetime.now(timezone.utc) + timedelta(days=1)
    scheduled = client.post(
        f"/api/v1/posts/{post_id}/schedule",
        headers=headers,
        json={"schedule_time": schedule_at.isoformat()},
    )
    assert scheduled.status_code == 200, scheduled.text
    assert client.get("/api/v1/calendar", headers=headers).status_code == 200

    caption = client.post(
        "/api/v1/ai/caption",
        headers=headers,
        json={
            "topic": "AI productivity tools",
            "description": "Three tools for creators",
            "tone": "professional",
            "platform": "instagram",
        },
    )
    assert caption.status_code == 200, caption.text
    assert caption.json()["caption"]
    assert caption.json()["hashtags"]

    analyze = client.post(
        "/api/v1/ai/analyze",
        headers=headers,
        json={
            "caption": "Three tools that save me time. What do you think? Save this post.",
            "platform": "instagram",
        },
    )
    assert analyze.status_code == 200
    assert 0 <= analyze.json()["score"] <= 100

    snapshot = client.post(
        f"/api/v1/analytics/posts/{post_id}",
        headers=headers,
        json={"followers": 1200, "reach": 1000, "likes": 100, "comments": 20, "shares": 10},
    )
    assert snapshot.status_code == 201, snapshot.text

    dashboard = client.get("/api/v1/analytics/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["reach"] == 1000

    overview = client.get("/api/v1/analytics/overview", headers=headers)
    assert overview.status_code == 200, overview.text
    assert overview.json()["metrics"]["reach"] == 1000
    assert overview.json()["series"]
    assert overview.json()["top_posts"][0]["post_id"] == post_id
    assert overview.json()["platform_reach"]["instagram"] == 1000

    best = client.get("/api/v1/recommendations/best-time", headers=headers)
    assert best.status_code == 200
    assert best.json()["sample_size"] >= 1

    growth = client.post("/api/v1/recommendations/growth", headers=headers)
    assert growth.status_code == 200
    assert growth.json()["recommendations"]

    publish = client.post(f"/api/v1/publishing/posts/{post_id}", headers=headers)
    assert publish.status_code == 200, publish.text
    assert publish.json()["mode"] == "simulate"
    assert publish.json()["status"] == "published"

    filtered = client.get("/api/v1/posts?platform=instagram&status=published", headers=headers)
    assert filtered.status_code == 200
    assert any(item["id"] == post_id for item in filtered.json())

    report = client.get("/api/v1/analytics/report", headers=headers)
    assert report.status_code == 200
    assert "engagement_rate" in report.text
