"""Runtime visibility and ordering policy for simulator and reference seasons."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from flask import current_app, has_app_context

from audit import write_audit_best_effort
DATA_ROOT = Path(__file__).resolve().parent / "static" / "season-data"

STATUSES = {"active", "archived", "hidden", "disabled"}
PUBLIC_STATUSES = {"active", "archived"}


def _path() -> Path:
    if not has_app_context():
        return DATA_ROOT.parent.parent / "instance" / "season-visibility.json"
    return Path(current_app.config["SEASON_VISIBILITY_PATH"])


def _library_catalog() -> list[dict]:
    try:
        payload = json.loads((DATA_ROOT / "catalog.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return list(payload.get("seasons") or [])


def _default_policy() -> dict:
    seasons = _library_catalog()
    ordered = list(reversed(seasons))
    simulator = {str(item.get("season_id")): {"status": "active", "order": i + 1} for i, item in enumerate(ordered) if item.get("season_id")}
    return {
        "simulator_default_season_id": next(iter(simulator), None),
        "simulator": simulator,
        "library": {str(item.get("season_id")): {"status": "active", "order": i + 1} for i, item in enumerate(ordered) if item.get("season_id")},
    }


def load_policy() -> dict:
    base = _default_policy()
    path = _path()
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        saved = {}
    for kind in ("simulator", "library"):
        for season_id, value in (saved.get(kind) or {}).items():
            if season_id not in base[kind] or not isinstance(value, dict):
                continue
            status = value.get("status")
            if status in STATUSES:
                base[kind][season_id]["status"] = status
            try:
                base[kind][season_id]["order"] = max(1, int(value.get("order")))
            except (TypeError, ValueError):
                pass
    requested_default = str(saved.get("simulator_default_season_id") or "")
    public_simulator_ids = [
        season_id
        for season_id, setting in sorted(
            base["simulator"].items(),
            key=lambda pair: (int(pair[1].get("order") or 999), pair[0]),
        )
        if setting.get("status") in PUBLIC_STATUSES
    ]
    base["simulator_default_season_id"] = (
        requested_default if requested_default in public_simulator_ids else (public_simulator_ids[0] if public_simulator_ids else None)
    )
    return base


def save_policy(policy: dict) -> dict:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(policy, ensure_ascii=False, indent=2), encoding="utf-8")
    return policy


def public_seasons(kind: str) -> list[dict]:
    policy = load_policy().get(kind, {})
    result = []
    for item in _library_catalog():
        season_id = str(item.get("season_id") or "")
        setting = policy.get(season_id, {})
        if setting.get("status") not in PUBLIC_STATUSES:
            continue
        result.append({**item, "status": setting.get("status"), "order": setting.get("order", 999)})
    return sorted(result, key=lambda item: (int(item.get("order") or 999), item.get("season_id", "")))


def get_season(kind: str, season_id: str) -> dict | None:
    return next((item for item in public_seasons(kind) if item.get("season_id") == str(season_id)), None)


def default_season_id(kind: str) -> str | None:
    if kind != "simulator":
        return None
    return load_policy().get("simulator_default_season_id")


def admin_payload(kind: str) -> list[dict]:
    policy = load_policy().get(kind, {})
    result = []
    for item in _library_catalog():
        season_id = str(item.get("season_id") or "")
        setting = policy.get(season_id, {"status": "active", "order": 999})
        result.append({**item, "status": setting.get("status", "active"), "order": setting.get("order", 999)})
    return sorted(result, key=lambda item: (int(item.get("order") or 999), item.get("season_id", "")))


def update_season(admin_id: int, kind: str, season_id: str, data: dict):
    if kind not in ("simulator", "library"):
        return None, "展示类型无效", 400
    season_id = str(season_id or "")
    if not any(item.get("season_id") == season_id for item in _library_catalog()):
        return None, "赛季不存在", 404
    policy = load_policy()
    before = deepcopy(policy[kind].get(season_id, {}))
    entry = dict(policy[kind].get(season_id, {"status": "active", "order": 999}))
    if "status" in data:
        if data["status"] not in STATUSES:
            return None, "赛季状态无效", 400
        entry["status"] = data["status"]
    if "order" in data:
        try:
            target = max(1, int(data["order"]))
        except (TypeError, ValueError):
            return None, "展示顺序无效", 400
        ordered = sorted(policy[kind].items(), key=lambda pair: (int(pair[1].get("order") or 999), pair[0]))
        ordered = [(sid, value) for sid, value in ordered if sid != season_id]
        ordered.insert(min(len(ordered), target - 1), (season_id, entry))
        for index, (sid, value) in enumerate(ordered, 1):
            value["order"] = index
            policy[kind][sid] = value
    policy[kind][season_id] = entry
    if data.get("is_default"):
        if kind != "simulator":
            return None, "只有阵容模拟器可以设置默认赛季", 400
        if entry.get("status") not in PUBLIC_STATUSES:
            return None, "默认赛季必须处于展示或归档状态", 400
        policy["simulator_default_season_id"] = season_id
    if kind == "simulator" and policy.get("simulator_default_season_id") == season_id and entry.get("status") not in PUBLIC_STATUSES:
        policy["simulator_default_season_id"] = next(
            (
                sid for sid, value in sorted(
                    policy["simulator"].items(),
                    key=lambda pair: (int(pair[1].get("order") or 999), pair[0]),
                ) if value.get("status") in PUBLIC_STATUSES
            ),
            None,
        )
    save_policy(policy)
    write_audit_best_effort(
        admin_id,
        f"update_{kind}_season_visibility",
        "season",
        before=before,
        after=entry,
        target_key=season_id,
    )
    return {
        "items": admin_payload(kind),
        "season": next(item for item in admin_payload(kind) if item["season_id"] == season_id),
        "default_season_id": policy.get("simulator_default_season_id") if kind == "simulator" else None,
    }, None, 200
