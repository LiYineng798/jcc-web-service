"""Collect augment data for released seasons with explicit provenance.

Tencent's season manifest exposes one ``hex.js`` document per game version.
It is authoritative for names, descriptions, tiers and images, but does not
currently expose category or per-augment stage restrictions. Categories remain
reviewable description-based classifications. Appearance stages come from a
versioned DataJ observed-match snapshot and are never filled by assumption.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode, urlparse


OFFICIAL_JS_ROOT = "https://game.gtimg.cn/images/lol/act/jkzlk/js"
DATAJ_STAGE_STATS_ROOT = "https://www.dataj.cc/api/web/stats/hex"
STANDARD_AUGMENT_STAGES = ["2-1", "3-2", "4-2"]
TIER_META = {
    "1": ("silver", "一级强化符文", 1),
    "2": ("gold", "二级强化符文", 2),
    "3": ("prismatic", "三级强化符文", 3),
}
CATEGORY_LABELS = {
    "economy": "经济",
    "combat": "战力",
    "equipment": "装备",
    "trait": "羁绊",
    "exclusive": "专属",
    "other": "其他",
}

TRAIT_PATTERN = re.compile(r"羁绊|纹章|徽章|转职|之心|之徽|之冕")
EQUIPMENT_PATTERN = re.compile(
    r"装备|散件|基础装备|成装|组件|锻造器|重铸器|拆卸器|装备复制器|神器|光明武器|辅助装"
)
ECONOMY_PATTERN = re.compile(
    r"金币|经验值|经验|利息|商店刷新|免费刷新|刷新商店|购买经验|升级费用|等级|售出|战利品|宝箱"
)
COMBAT_PATTERN = re.compile(
    r"战斗开始|你的弈子|弈子们|攻击|伤害|生命|护甲|魔法抗性|魔抗|法力|治疗|护盾|攻速|攻击速度|法术加成|物理加成|暴击|全能吸血"
)


def _request_json(url: str) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": "jcc-season-library/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def _request_hex_document(hex_path: str, game_version: str | None) -> tuple[dict, str, str | None]:
    candidates = [(f"{OFFICIAL_JS_ROOT}{hex_path}", game_version)]
    base_version = re.sub(r"[A-Za-z]+$", "", str(game_version or ""))
    if game_version and base_version and base_version != game_version:
        fallback_path = hex_path.replace(str(game_version), base_version, 1)
        candidates.append((f"{OFFICIAL_JS_ROOT}{fallback_path}", base_version))
    last_error = None
    for url, resolved_version in candidates:
        try:
            return _request_json(url), url, resolved_version
        except Exception as exc:  # noqa: BLE001 - try the documented base-patch fallback
            last_error = exc
    raise last_error or RuntimeError("official hex document unavailable")


def _records(document: dict) -> list[dict]:
    data = document.get("data")
    if isinstance(data, dict):
        return [record for record in data.values() if isinstance(record, dict)]
    if isinstance(data, list):
        return [record for record in data if isinstance(record, dict)]
    return []


def _safe_image_name(url: str, seen: dict[str, str]) -> str:
    raw_name = Path(urlparse(url).path).name or "augment.png"
    name = re.sub(r"[^A-Za-z0-9._-]", "_", raw_name)
    previous = seen.get(name)
    if previous and previous != url:
        stem = Path(name).stem
        suffix = Path(name).suffix or ".png"
        name = f"{stem}-{hashlib.sha256(url.encode('utf-8')).hexdigest()[:10]}{suffix}"
    seen[name] = url
    return name


def _download_images(entries: list[tuple[str, Path]]) -> list[dict[str, str]]:
    failures = []

    def download(url: str, target: Path) -> None:
        request = urllib.request.Request(url, headers={"User-Agent": "jcc-season-library/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
        if not content:
            raise RuntimeError("empty response")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    unique_entries = list(dict.fromkeys(entries))
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(download, url, target): (url, target) for url, target in unique_entries}
        for future in as_completed(futures):
            url, target = futures[future]
            try:
                future.result()
            except Exception as exc:  # noqa: BLE001 - collect every broken official asset
                failures.append({"url": url, "target": str(target), "error": str(exc)})
    return failures


def classify_augment(record: dict, augment_type: str) -> str:
    """Assign the site's display category with stable, reviewable rules."""
    if augment_type == "hero":
        return "exclusive"
    if augment_type == "special":
        return "other"
    fetter_id = str(record.get("fetterId") or "").strip()
    text = f"{record.get('name') or ''} {record.get('desc') or ''}"
    if fetter_id not in {"", "0"} or TRAIT_PATTERN.search(text):
        return "trait"
    if EQUIPMENT_PATTERN.search(text):
        return "equipment"
    if ECONOMY_PATTERN.search(text):
        return "economy"
    if COMBAT_PATTERN.search(text):
        return "combat"
    return "other"


def _augment_type(season_id: str, level: str) -> str:
    if level != "4":
        return "standard"
    return "hero" if season_id == "s8" else "special"


def _observed_game_version(game_version: str | None) -> str | None:
    """Translate an archive version such as 17.17.8b to DataJ's 17.8b."""
    value = str(game_version or "").strip()
    duplicated_major = re.fullmatch(r"(\d+)\.\1\.(.+)", value)
    if duplicated_major:
        return f"{duplicated_major.group(1)}.{duplicated_major.group(2)}"
    return value or None


def _season_set_id(season_id: str) -> int | None:
    match = re.fullmatch(r"s(\d+)(?:_\d+)?", season_id)
    return int(match.group(1)) if match else None


def _request_stage_document(season_id: str, game_version: str | None) -> tuple[dict, dict] | tuple[None, None]:
    set_id = _season_set_id(season_id)
    observed_version = _observed_game_version(game_version)
    if set_id is None or not observed_version:
        return None, None
    source_url = f"{DATAJ_STAGE_STATS_ROOT}?{urlencode({'setId': set_id, 'gameVersion': observed_version})}"
    document = _request_json(source_url)
    if document.get("code") != 200 or document.get("success") is not True or not isinstance(document.get("data"), list):
        raise RuntimeError(f"强化符文出现回合统计响应异常: {source_url}")
    source = {
        "type": "dataj_observed_match_rounds",
        "url": source_url,
        "snapshot_path": "source-snapshots/augment-stage-stats.json",
        "set_id": set_id,
        "requested_game_version": game_version,
        "observed_game_version": observed_version,
        "record_count": len(document["data"]),
        "provenance_note": "版本化实战样本观察结果，并非腾讯官方逐条配置",
        "methodology_context": [
            "https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/teamfight-tactics-patch-13-1-notes/",
            "https://teamfighttactics.leagueoflegends.com/en-us/news/game-updates/teamfight-tactics-patch-13-6-notes/",
        ],
    }
    return document, source


def _stage_rows(document: dict | None) -> dict[str, dict]:
    rows = {}
    for row in (document or {}).get("data") or []:
        augment_id = str(row.get("hexId") or "").strip()
        if augment_id:
            rows[augment_id] = row
    return rows


def _appearance_stages(
    augment_id: str,
    augment_type: str,
    stage_rows: dict[str, dict],
    stage_source: dict | None,
) -> tuple[list[str], str, dict]:
    if augment_type == "special":
        return [], "not_applicable", {"status": "not_applicable"}
    row = stage_rows.get(augment_id)
    sample_count = int((row or {}).get("sampleCount") or 0)
    stages = [stage for stage in STANDARD_AUGMENT_STAGES if stage in ((row or {}).get("rounds") or [])]
    if row and sample_count > 0 and stages:
        return stages, "dataj_observed_match_rounds", {
            "status": "observed",
            "match_method": "official_id",
            "sample_count": sample_count,
            "source_url": (stage_source or {}).get("url"),
            "game_version": (stage_source or {}).get("observed_game_version"),
        }
    reason = "observed_record_has_no_round_breakdown" if row and sample_count > 0 else "no_versioned_observed_match_record"
    return [], "stage_data_unavailable", {
        "status": "unavailable",
        "reason": reason,
        "sample_count": sample_count,
        "source_url": (stage_source or {}).get("url"),
        "game_version": (stage_source or {}).get("observed_game_version"),
    }


def build_change_report(previous: dict | None, current: dict) -> dict:
    fields = ("name", "description", "tier", "augment_type", "category", "appearance_stages", "image")
    before = {str(item["id"]): item for item in (previous or {}).get("augments") or []}
    after = {str(item["id"]): item for item in current.get("augments") or []}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = []
    for augment_id in sorted(set(before) & set(after)):
        changed_fields = []
        for field in fields:
            before_value = before[augment_id].get(field)
            after_value = after[augment_id].get(field)
            if field == "image":
                comparable_keys = ("local_path", "source_url", "alt")
                before_value = {key: (before_value or {}).get(key) for key in comparable_keys}
                after_value = {key: (after_value or {}).get(key) for key in comparable_keys}
            if before_value != after_value:
                changed_fields.append(field)
        if changed_fields:
            changed.append({"id": augment_id, "name": after[augment_id].get("name"), "fields": changed_fields})
    return {
        "version_id": current.get("version_id"),
        "previous_version_id": (previous or {}).get("version_id"),
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed)},
        "added_ids": added,
        "removed_ids": removed,
        "changed": changed,
    }


def collect_official_augments(
    version_dir: Path,
    target_dir: Path,
    season_id: str,
    version_id: str,
    previous: dict | None = None,
) -> tuple[dict, dict]:
    """Fetch and normalize one released season's official augment snapshot."""
    empty = {
        "version_id": version_id,
        "source": None,
        "category_labels": CATEGORY_LABELS,
        "stage_options": STANDARD_AUGMENT_STAGES,
        "augments": [],
    }
    if season_id == "s18":
        return empty, build_change_report(previous, empty)

    version_entry_path = version_dir / "source-snapshots" / "version-entry.json"
    if not version_entry_path.is_file():
        return empty, build_change_report(previous, empty)
    version_entry = json.loads(version_entry_path.read_text(encoding="utf-8"))
    hex_path = version_entry.get("hexurl")
    if not hex_path:
        return empty, build_change_report(previous, empty)

    requested_version = version_entry.get("version")
    document, source_url, resolved_version = _request_hex_document(hex_path, requested_version)
    snapshot_path = target_dir / "source-snapshots" / "hex.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    stage_document, stage_source = _request_stage_document(season_id, requested_version)
    if stage_document is not None:
        stage_snapshot_path = target_dir / "source-snapshots" / "augment-stage-stats.json"
        stage_snapshot_path.write_text(json.dumps(stage_document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    observed_stage_rows = _stage_rows(stage_document)

    seen_names: dict[str, str] = {}
    image_entries: list[tuple[str, Path]] = []
    augments = []
    for record in _records(document):
        augment_id = str(record.get("id") or "").strip()
        if not augment_id:
            continue
        level = str(record.get("level") or "").strip()
        augment_type = _augment_type(season_id, level)
        tier, tier_label, tier_order = TIER_META.get(level, (augment_type, "英雄强化" if augment_type == "hero" else "特殊强化", 4))
        stages, stage_provenance, stage_evidence = _appearance_stages(
            augment_id,
            augment_type,
            observed_stage_rows,
            stage_source,
        )
        category = classify_augment(record, augment_type)
        icon_url = str(record.get("icon") or "").strip()
        image = None
        if icon_url:
            filename = _safe_image_name(icon_url, seen_names)
            local_path = f"assets/augments/{filename}"
            image_entries.append((icon_url, target_dir / local_path))
            image = {"local_path": local_path, "source_url": icon_url, "alt": f"{record.get('name') or augment_id}强化符文图标"}
        augments.append({
            "id": augment_id,
            "name": record.get("name") or "未知强化符文",
            "description": record.get("desc") or "",
            "tier": tier,
            "tier_label": tier_label,
            "tier_order": tier_order,
            "augment_type": augment_type,
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "appearance_stages": stages,
            "image": image,
            "source_ids": {
                "official_id": augment_id,
                "official_level": level,
                "fetter_id": str(record.get("fetterId") or "") or None,
                "fetter_type": str(record.get("fetterType") or "") or None,
            },
            "extensions": {
                "category_source": "description_rule_v1",
                "appearance_stage_source": stage_provenance,
                "appearance_stage_evidence": stage_evidence,
                "is_legend": record.get("is_legend"),
                "hero_enhancement_type": record.get("hero_enhancement_type"),
            },
        })

    failures = _download_images(image_entries)
    if failures:
        raise RuntimeError(f"官方强化符文图片下载失败 {len(failures)} 个: {failures[:3]}")
    augments.sort(key=lambda item: (item["tier_order"], item["category"], item["name"], item["id"]))
    payload = {
        "version_id": version_id,
        "source": {
            "type": "official_jkzlk_hex",
            "url": source_url,
            "snapshot_path": "source-snapshots/hex.json",
            "source_version": document.get("version"),
            "source_time": document.get("time"),
            "requested_version": requested_version,
            "resolved_version": resolved_version,
            "used_base_patch_fallback": bool(resolved_version and resolved_version != requested_version),
        },
        "stage_source": stage_source,
        "category_labels": CATEGORY_LABELS,
        "stage_options": STANDARD_AUGMENT_STAGES,
        "augments": augments,
    }
    return payload, build_change_report(previous, payload)
