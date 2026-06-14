from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

TIER_ORDER = ("S", "A", "B", "C", "D")
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


def normalize_server_url(value: str) -> str:
    url = str(value or "").strip().rstrip("/")
    if not url:
        raise ValueError("服务器地址不能为空")
    if not url.startswith(("http://", "https://")):
        raise ValueError("服务器地址必须以 http:// 或 https:// 开头")
    return url


def request_json(url: str, timeout: int = 30):
    req = urllib.request.Request(url, headers={"User-Agent": "JCC-Manual-Live-Comps-Tool/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict, token: str, timeout: int = 180):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Upload-Token": token,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def normalized_image_suffix(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".jpeg":
        suffix = ".jpg"
    if suffix not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("图片格式只支持 jpg、png、webp、gif")
    return suffix


def asset_filename_for_bytes(filename: str, data: bytes) -> str:
    suffix = normalized_image_suffix(filename)
    digest = hashlib.sha256(data).hexdigest()
    return f"manual-{digest[:24]}{suffix}"


def asset_filename(path: Path) -> str:
    data = path.read_bytes()
    suffix = normalized_image_suffix(path.name)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"manual-{digest[:24]}{suffix}"


def validate_live_comps_payload(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValueError("实时阵容 payload 必须是对象")
    tiers = payload.get("tiers")
    if not isinstance(tiers, dict):
        raise ValueError("实时阵容 payload 缺少 tiers")
    for tier in TIER_ORDER:
        items = tiers.get(tier, [])
        if not isinstance(items, list):
            raise ValueError(f"{tier} 分组必须是数组")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("阵容项必须是对象")
            for field in ("id", "title", "tier", "jccCode", "mainAvatar", "heroImages"):
                if field not in item:
                    raise ValueError(f"缺少字段 {field}")
            if not item.get("id"):
                raise ValueError("阵容 id 不能为空")
            if not item.get("title"):
                raise ValueError("阵容名称不能为空")
            if item.get("tier") not in TIER_ORDER:
                raise ValueError("阵容等级必须是 S/A/B/C/D")
            if not item.get("mainAvatar"):
                raise ValueError("主图不能为空")
            if not isinstance(item.get("heroImages"), list):
                raise ValueError("heroImages 必须是数组")


def current_live_comps_payload(server: str, season_id: str) -> dict:
    season_id = str(season_id or "").strip()
    query = urllib.parse.urlencode({"season": season_id}) if season_id else ""
    summary_url = f"{server}/api/live-comps/summary{f'?{query}' if query else ''}"
    summary = request_json(summary_url)
    tiers = {tier: [] for tier in TIER_ORDER}
    for tier in TIER_ORDER:
        page = 1
        while True:
            params = {"tier": tier, "page": page}
            if season_id:
                params["season"] = season_id
            page_data = request_json(f"{server}/api/live-comps?{urllib.parse.urlencode(params)}")
            tiers[tier].extend(page_data.get("items") or [])
            total_pages = int(page_data.get("total_pages") or 1)
            if page >= total_pages:
                break
            page += 1
    return {
        "meta": {
            **(summary.get("source_meta") or {}),
            "source": (summary.get("source_meta") or {}).get("source") or "server-live-comps",
            "season_id": (summary.get("season") or {}).get("id") or season_id,
            "season_name": (summary.get("season") or {}).get("name") or "",
        },
        "tiers": tiers,
    }


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static")

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/seasons")
    def seasons():
        try:
            server = normalize_server_url(request.args.get("server", ""))
            return jsonify(request_json(f"{server}/api/live-comps/seasons"))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.get("/api/current-live-comps")
    def current_live_comps():
        try:
            server = normalize_server_url(request.args.get("server", ""))
            payload = current_live_comps_payload(server, request.args.get("season_id", ""))
            validate_live_comps_payload(payload)
            return jsonify(payload)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/upload-image")
    def upload_image():
        try:
            data = request.get_json(silent=True) or {}
            server = normalize_server_url(data.get("server", ""))
            token = str(data.get("token") or "").strip()
            if not token:
                raise ValueError("上传 token 不能为空")
            raw_base64 = str(data.get("content_base64") or "").strip()
            if raw_base64:
                raw_data = base64.b64decode(raw_base64, validate=True)
                original_name = str(data.get("filename") or "manual-image.jpg")
                filename = asset_filename_for_bytes(original_name, raw_data)
                content_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
            else:
                path = Path(str(data.get("path") or "")).expanduser()
                if not path.exists() or not path.is_file():
                    raise ValueError("图片文件不存在")
                raw_data = path.read_bytes()
                filename = asset_filename(path)
                content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            payload = {
                "filename": filename,
                "content_base64": base64.b64encode(raw_data).decode("ascii"),
                "content_type": content_type,
            }
            result = post_json(f"{server}/api/live-comps/assets/upload", payload, token, timeout=60)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    @app.post("/api/upload-live-comps")
    def upload_live_comps():
        try:
            data = request.get_json(silent=True) or {}
            server = normalize_server_url(data.get("server", ""))
            token = str(data.get("token") or "").strip()
            season_id = str(data.get("season_id") or "").strip()
            payload = data.get("payload")
            if not token:
                raise ValueError("上传 token 不能为空")
            if not season_id:
                raise ValueError("请选择赛季")
            if isinstance(payload, dict):
                payload.setdefault("meta", {})
                payload["meta"].setdefault("source", "manual-live-comps-tool")
                payload["meta"]["generated_at"] = datetime.now().isoformat(timespec="seconds")
            validate_live_comps_payload(payload)
            query = urllib.parse.urlencode({"season": season_id})
            result = post_json(f"{server}/api/live-comps/upload?{query}", payload, token, timeout=180)
            return jsonify(result)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8765, debug=False, use_reloader=False)
