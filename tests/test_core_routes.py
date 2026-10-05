import io

from PIL import Image

from datetime import datetime, timedelta, timezone
from uuid import uuid4


def test_profile_update_and_password_change(client):
    email = f"profile-{uuid4().hex[:10]}@example.com"
    old_password = "StrongPass123"
    new_password = "EvenStrongerPass456"

    registered = client.post(
        "/api/v1/auth/register",
        json={"name": "Profile User", "email": email, "password": old_password},
    )
    assert registered.status_code == 201, registered.text

    token = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    updated = client.put(
        "/api/v1/users/me",
        headers=headers,
        json={"name": "Updated Creator", "bio": "CreatorOS profile QA"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Updated Creator"
    assert updated.json()["bio"] == "CreatorOS profile QA"

    changed = client.put(
        "/api/v1/users/me/password",
        headers=headers,
        json={"current_password": old_password, "new_password": new_password},
    )
    assert changed.status_code == 200, changed.text

    old_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": old_password},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    )
    assert new_login.status_code == 200


def test_post_crud_schedule_reschedule_and_cancel(client, auth_headers):
    social = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "calendar-page-id",
            "account_name": "Calendar Test Page",
            "access_token": "calendar-token",
        },
    )
    assert social.status_code == 201, social.text

    created = client.post(
        "/api/v1/posts",
        headers=auth_headers,
        json={
            "title": "Original title",
            "caption": "Original caption",
            "platform": "facebook",
        },
    )
    assert created.status_code == 201, created.text
    post_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/posts/{post_id}",
        headers=auth_headers,
        json={"title": "Updated title", "caption": "Updated caption"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["title"] == "Updated title"

    first_time = datetime.now(timezone.utc) + timedelta(hours=1)
    scheduled = client.post(
        f"/api/v1/posts/{post_id}/schedule",
        headers=auth_headers,
        json={"schedule_time": first_time.isoformat(), "platform": "facebook"},
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["publish_state"] == "scheduled"

    second_time = datetime.now(timezone.utc) + timedelta(hours=2)
    rescheduled = client.put(
        f"/api/v1/posts/{post_id}/schedule",
        headers=auth_headers,
        json={"schedule_time": second_time.isoformat(), "platform": "facebook"},
    )
    assert rescheduled.status_code == 200, rescheduled.text

    calendar = client.get("/api/v1/calendar", headers=auth_headers)
    assert calendar.status_code == 200
    assert any(item["post_id"] == post_id for item in calendar.json())

    cancelled = client.delete(f"/api/v1/posts/{post_id}/schedule", headers=auth_headers)
    assert cancelled.status_code == 200, cancelled.text

    fetched = client.get(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "draft"
    assert fetched.json()["scheduled_time"] is None

    deleted = client.delete(f"/api/v1/posts/{post_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/posts/{post_id}", headers=auth_headers).status_code == 404


def test_media_upload_and_type_validation(client, auth_headers, monkeypatch, tmp_path):
    from app.core.config import settings

    monkeypatch.setattr(settings, "supabase_url", None)
    monkeypatch.setattr(settings, "supabase_service_role_key", None)
    monkeypatch.setattr(settings, "media_local_dir", str(tmp_path))

    rejected = client.post(
        "/api/v1/media/upload",
        headers=auth_headers,
        files={"file": ("notes.txt", b"not media", "text/plain")},
    )
    assert rejected.status_code == 415

    invalid_image = client.post(
        "/api/v1/media/upload",
        headers=auth_headers,
        files={"file": ("photo.png", b"fake-png-bytes", "image/png")},
    )
    assert invalid_image.status_code == 400

    image = Image.new("RGB", (640, 640), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    uploaded = client.post(
        "/api/v1/media/upload",
        headers=auth_headers,
        files={"file": ("photo.png", buffer.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    payload = uploaded.json()
    assert payload["storage"] == "local"
    assert payload["url"].startswith("/media/files/")
    assert any(tmp_path.iterdir())


def test_social_disconnect(client, auth_headers):
    created = client.post(
        "/api/v1/social-accounts",
        headers=auth_headers,
        json={
            "platform": "facebook",
            "platform_account_id": "disconnect-page",
            "account_name": "Disconnect Page",
            "access_token": "disconnect-token",
        },
    )
    assert created.status_code == 201, created.text
    account_id = created.json()["id"]

    listed = client.get("/api/v1/social-accounts", headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == account_id for item in listed.json())

    deleted = client.delete(f"/api/v1/social-accounts/{account_id}", headers=auth_headers)
    assert deleted.status_code == 200

    listed_again = client.get("/api/v1/social-accounts", headers=auth_headers)
    assert all(item["id"] != account_id for item in listed_again.json())


def test_analytics_post_history_and_report(client, auth_headers):
    post = client.post(
        "/api/v1/posts",
        headers=auth_headers,
        json={
            "title": "Analytics QA",
            "caption": "Measure this post",
            "platform": "facebook",
        },
    )
    assert post.status_code == 201, post.text
    post_id = post.json()["id"]

    for reach, likes in [(100, 10), (250, 40)]:
        snapshot = client.post(
            f"/api/v1/analytics/posts/{post_id}",
            headers=auth_headers,
            json={
                "followers": 500,
                "reach": reach,
                "likes": likes,
                "comments": 5,
                "shares": 2,
            },
        )
        assert snapshot.status_code == 201, snapshot.text

    history = client.get(f"/api/v1/analytics/posts/{post_id}", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) == 2

    dashboard = client.get("/api/v1/analytics/dashboard", headers=auth_headers)
    assert dashboard.status_code == 200
    # Snapshots are cumulative point-in-time values. The dashboard should use
    # the latest value for this post instead of summing 100 + 250.
    assert dashboard.json()["reach"] == 250
    assert dashboard.json()["likes"] == 40

    overview = client.get("/api/v1/analytics/overview", headers=auth_headers)
    assert overview.status_code == 200
    assert overview.json()["platform_reach"]["facebook"] == 250
    assert overview.json()["top_posts"][0]["reach"] == 250

    best_time = client.get("/api/v1/recommendations/best-time", headers=auth_headers)
    assert best_time.status_code == 200
    assert best_time.json()["sample_size"] == 1

    report = client.get("/api/v1/analytics/report", headers=auth_headers)
    assert report.status_code == 200
    assert report.headers["content-type"].startswith("text/csv")
    assert "engagement_rate" in report.text
