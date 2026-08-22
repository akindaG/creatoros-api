from datetime import datetime, timedelta, timezone


def test_health(client):
    assert client.get("/health").status_code == 200
    db = client.get("/health/db")
    assert db.status_code == 200
    assert db.json()["result"] == 1


def test_auth_profile_and_password_reset(client, auth_headers):
    me = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "creator@example.com"
    forgot = client.post("/api/v1/auth/forgot-password", json={"email": "creator@example.com"})
    assert forgot.status_code == 200
    token = forgot.json()["reset_token"]
    reset = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "NewStrongPass123"})
    assert reset.status_code == 200
    login = client.post("/api/v1/auth/login", json={"email": "creator@example.com", "password": "NewStrongPass123"})
    assert login.status_code == 200


def test_end_to_end_mvp(client):
    email = "journey@example.com"
    password = "StrongPass123"
    assert client.post("/api/v1/auth/register", json={"name": "Journey User", "email": email, "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    social = client.post("/api/v1/social-accounts", headers=headers, json={"platform": "instagram", "account_name": "17890000000000000", "username": "creator", "access_token": "demo-token"})
    assert social.status_code == 201, social.text

    post = client.post("/api/v1/posts", headers=headers, json={"title": "AI productivity", "caption": "Three tools that save me time. What do you think? Save this post.", "platform": "instagram"})
    assert post.status_code == 201, post.text
    post_id = post.json()["id"]

    schedule_at = datetime.now(timezone.utc) + timedelta(days=1)
    scheduled = client.post(f"/api/v1/posts/{post_id}/schedule", headers=headers, json={"schedule_time": schedule_at.isoformat()})
    assert scheduled.status_code == 200, scheduled.text
    assert client.get("/api/v1/calendar", headers=headers).status_code == 200

    caption = client.post("/api/v1/ai/caption", headers=headers, json={"topic": "AI productivity tools", "description": "Three tools for creators", "tone": "professional", "platform": "instagram"})
    assert caption.status_code == 200, caption.text
    assert caption.json()["caption"]
    assert caption.json()["hashtags"]

    analyze = client.post("/api/v1/ai/analyze", headers=headers, json={"caption": "Three tools that save me time. What do you think? Save this post.", "platform": "instagram"})
    assert analyze.status_code == 200
    assert 0 <= analyze.json()["score"] <= 100

    snapshot = client.post(f"/api/v1/analytics/posts/{post_id}", headers=headers, json={"followers": 1200, "reach": 1000, "likes": 100, "comments": 20, "shares": 10})
    assert snapshot.status_code == 201, snapshot.text
    dashboard = client.get("/api/v1/analytics/dashboard", headers=headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["reach"] == 1000

    best = client.get("/api/v1/recommendations/best-time", headers=headers)
    assert best.status_code == 200
    assert best.json()["sample_size"] >= 1

    growth = client.post("/api/v1/recommendations/growth", headers=headers)
    assert growth.status_code == 200
    assert growth.json()["recommendations"]

    publish = client.post(f"/api/v1/publishing/posts/{post_id}", headers=headers)
    assert publish.status_code == 200, publish.text
    assert publish.json()["mode"] == "simulate"

    filtered = client.get("/api/v1/posts?platform=instagram&status=published", headers=headers)
    assert filtered.status_code == 200
    assert any(item["id"] == post_id for item in filtered.json())

    report = client.get("/api/v1/analytics/report", headers=headers)
    assert report.status_code == 200
    assert "engagement_rate" in report.text
