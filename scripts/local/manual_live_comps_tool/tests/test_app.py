import base64
import importlib.util
import json
from pathlib import Path

import pytest

TOOL_DIR = Path(__file__).resolve().parents[1]
APP_PATH = TOOL_DIR / "app.py"
spec = importlib.util.spec_from_file_location("manual_live_comps_tool_app", APP_PATH)
manual_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manual_app)


class DummyResponse:
    def __init__(self, body, status=200, headers=None):
        self._body = body
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._body


@pytest.fixture
def client(monkeypatch):
    app = manual_app.create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def test_fetch_seasons_proxies_server_manifest(client, monkeypatch):
    captured = {}

    def fake_open(request, timeout=30):
        captured["url"] = request.full_url
        return DummyResponse(json.dumps({
            "default_season_id": "s17-star-god",
            "seasons": [{"id": "s17-star-god", "name": "S17 · 星神"}],
        }).encode("utf-8"))

    monkeypatch.setattr(manual_app.urllib.request, "urlopen", fake_open)

    response = client.get("/api/seasons?server=https://jcc.example")

    assert response.status_code == 200
    assert captured["url"] == "https://jcc.example/api/live-comps/seasons"
    assert response.get_json()["default_season_id"] == "s17-star-god"


def test_upload_image_posts_base64_asset_and_returns_asset_url(client, monkeypatch, tmp_path):
    image_path = tmp_path / "hero.webp"
    image_path.write_bytes(b"image-bytes")
    captured = {}

    def fake_open(request, timeout=30):
        captured["url"] = request.full_url
        captured["token"] = request.get_header("X-upload-token")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return DummyResponse(b'{"ok": true, "url": "/api/live-comps/assets/hero.webp"}')

    monkeypatch.setattr(manual_app.urllib.request, "urlopen", fake_open)

    response = client.post("/api/upload-image", json={
        "server": "https://jcc.example",
        "token": "secret",
        "path": str(image_path),
    })

    assert response.status_code == 200
    assert captured["url"] == "https://jcc.example/api/live-comps/assets/upload"
    assert captured["token"] == "secret"
    assert captured["body"]["filename"].endswith(".webp")
    assert base64.b64decode(captured["body"]["content_base64"]) == b"image-bytes"
    assert response.get_json()["url"] == "/api/live-comps/assets/hero.webp"


def test_upload_image_accepts_browser_base64_payload(client, monkeypatch):
    captured = {}

    def fake_open(request, timeout=30):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return DummyResponse(b'{"ok": true, "url": "/api/live-comps/assets/browser.png"}')

    monkeypatch.setattr(manual_app.urllib.request, "urlopen", fake_open)

    response = client.post("/api/upload-image", json={
        "server": "https://jcc.example",
        "token": "secret",
        "filename": "browser.png",
        "content_base64": base64.b64encode(b"browser-bytes").decode("ascii"),
    })

    assert response.status_code == 200
    assert captured["body"]["filename"].endswith(".png")
    assert base64.b64decode(captured["body"]["content_base64"]) == b"browser-bytes"


def test_upload_live_comps_posts_payload_to_selected_season(client, monkeypatch):
    captured = {}
    payload = {
        "meta": {"source": "manual-tool"},
        "tiers": {
            "S": [{
                "id": "manual-s-001",
                "title": "机甲九五",
                "tier": "S",
                "jccCode": "#ABC123",
                "mainAvatar": "/api/live-comps/assets/main.webp",
                "heroImages": ["/api/live-comps/assets/hero.webp"],
            }],
            "A": [],
            "B": [],
            "C": [],
            "D": [],
        },
    }

    def fake_open(request, timeout=180):
        captured["url"] = request.full_url
        captured["token"] = request.get_header("X-upload-token")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return DummyResponse(b'{"ok": true, "total": 1}')

    monkeypatch.setattr(manual_app.urllib.request, "urlopen", fake_open)

    response = client.post("/api/upload-live-comps", json={
        "server": "https://jcc.example",
        "token": "secret",
        "season_id": "s18-new-season",
        "payload": payload,
    })

    assert response.status_code == 200
    assert captured["url"] == "https://jcc.example/api/live-comps/upload?season=s18-new-season"
    assert captured["token"] == "secret"
    assert captured["payload"]["tiers"]["S"][0]["title"] == "机甲九五"
    assert response.get_json()["ok"] is True


def test_current_live_comps_fetches_all_tier_pages(client, monkeypatch):
    calls = []

    def fake_open(request, timeout=30):
        calls.append(request.full_url)
        if request.full_url == "https://jcc.example/api/live-comps/summary?season=s18-new-season":
            return DummyResponse(json.dumps({
                "season": {"id": "s18-new-season", "name": "S18"},
                "source_meta": {"source": "server"},
            }).encode("utf-8"))
        if request.full_url == "https://jcc.example/api/live-comps?tier=S&page=1&season=s18-new-season":
            return DummyResponse(json.dumps({
                "tier": "S",
                "page": 1,
                "total_pages": 2,
                "items": [{"id": "s-1", "title": "第一页", "tier": "S", "jccCode": "", "mainAvatar": "/api/live-comps/assets/a.png", "heroImages": []}],
            }).encode("utf-8"))
        if request.full_url == "https://jcc.example/api/live-comps?tier=S&page=2&season=s18-new-season":
            return DummyResponse(json.dumps({
                "tier": "S",
                "page": 2,
                "total_pages": 2,
                "items": [{"id": "s-2", "title": "第二页", "tier": "S", "jccCode": "", "mainAvatar": "/api/live-comps/assets/b.png", "heroImages": []}],
            }).encode("utf-8"))
        tier = request.full_url.split("tier=", 1)[1].split("&", 1)[0]
        return DummyResponse(json.dumps({"tier": tier, "page": 1, "total_pages": 1, "items": []}).encode("utf-8"))

    monkeypatch.setattr(manual_app.urllib.request, "urlopen", fake_open)

    response = client.get("/api/current-live-comps?server=https://jcc.example&season_id=s18-new-season")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["meta"]["source"] == "server"
    assert [item["id"] for item in payload["tiers"]["S"]] == ["s-1", "s-2"]
    assert "https://jcc.example/api/live-comps?tier=A&page=1&season=s18-new-season" in calls


def test_upload_live_comps_rejects_missing_required_fields(client):
    response = client.post("/api/upload-live-comps", json={
        "server": "https://jcc.example",
        "token": "secret",
        "season_id": "s18-new-season",
        "payload": {"tiers": {"S": [{"title": "缺字段"}], "A": [], "B": [], "C": [], "D": []}},
    })

    assert response.status_code == 400
    assert "缺少字段 id" in response.get_json()["error"]


def test_frontend_cost_filters_include_six_and_seven_cost_units():
    script = (TOOL_DIR / "static" / "app.js").read_text(encoding="utf-8")

    assert "6费" in script
    assert "7费" in script
    assert "for (const cost of ['1', '2', '3', '4', '5', '6', '7'])" in script


def test_frontend_has_import_json_and_fetch_current_controls():
    html = (TOOL_DIR / "static" / "index.html").read_text(encoding="utf-8")
    script = (TOOL_DIR / "static" / "app.js").read_text(encoding="utf-8")

    assert 'id="jsonImportInput"' in html
    assert 'id="fetchCurrentButton"' in html
    assert "importJsonFile" in script
    assert "fetchCurrentLiveComps" in script
