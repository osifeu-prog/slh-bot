from io import BytesIO

from PIL import Image

import webapp


def test_social_catalog_and_generated_image_routes(monkeypatch):
    monkeypatch.setattr(webapp, "authenticated_uid", lambda: "8789977826")
    client = webapp.app.test_client()

    catalog = client.get("/api/v1/social/assets")
    assert catalog.status_code == 200
    data = catalog.get_json()
    assert data["ok"] is True
    assert {x["id"] for x in data["assets"]} >= {"brand", "academy", "agents"}

    image = client.get("/api/v1/social/assets/brand.png")
    assert image.status_code == 200
    assert image.mimetype == "image/png"
    assert image.headers["X-Content-Type-Options"] == "nosniff"
    assert Image.open(BytesIO(image.data)).size == (1200, 630)

    unknown = client.get("/api/v1/social/assets/no-such-asset.png")
    assert unknown.status_code == 404


def test_share_landing_has_platform_preview_tags_and_uses_own_asset(monkeypatch):
    client = webapp.app.test_client()
    response = client.get("/share/academy")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'property="og:image"' in body
    assert 'name="twitter:card" content="summary_large_image"' in body
    assert "/api/v1/social/assets/academy.png" in body
    assert 'property="og:image:width" content="1200"' in body
    assert "/mini-app-v4" in body


def test_social_catalog_and_telegram_delivery_require_telegram_auth(monkeypatch):
    monkeypatch.setattr(webapp, "authenticated_uid", lambda: None)
    client = webapp.app.test_client()
    assert client.get("/api/v1/social/assets").status_code == 401
    response = client.post("/api/v1/social/send-to-telegram", json={"asset_id": "brand"})
    assert response.status_code == 401


def test_send_to_telegram_posts_only_the_authenticated_users_selected_asset(monkeypatch):
    monkeypatch.setattr(webapp, "authenticated_uid", lambda: "8789977826")
    monkeypatch.setenv("BOT_TOKEN", "test-token:123")
    calls = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"ok": True, "result": {"message_id": 42}}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr(webapp.requests, "post", fake_post)
    client = webapp.app.test_client()
    response = client.post("/api/v1/social/send-to-telegram", json={"asset_id": "brand"})

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "sent": True, "asset_id": "brand"}
    assert calls["url"].endswith("/sendPhoto")
    assert calls["data"]["chat_id"] == "8789977826"
    assert "/share/brand" in calls["data"]["caption"]
    filename, image_bytes, content_type = calls["files"]["photo"]
    assert filename == "slh-spark-brand.png"
    assert content_type == "image/png"
    assert Image.open(BytesIO(image_bytes)).size == (1200, 630)
    assert calls["timeout"] == (3, 15)


def test_telegram_delivery_never_echoes_bot_api_error_payload(monkeypatch):
    monkeypatch.setattr(webapp, "authenticated_uid", lambda: "8789977826")
    monkeypatch.setenv("BOT_TOKEN", "test-token:123")

    class FakeResponse:
        status_code = 400

        @staticmethod
        def json():
            return {"ok": False, "description": "secret upstream detail"}

    monkeypatch.setattr(webapp.requests, "post", lambda *args, **kwargs: FakeResponse())
    client = webapp.app.test_client()
    response = client.post("/api/v1/social/send-to-telegram", json={"asset_id": "brand"})
    assert response.status_code == 502
    assert response.get_json() == {"error": "TELEGRAM_DELIVERY_FAILED"}
    assert b"secret upstream detail" not in response.data
