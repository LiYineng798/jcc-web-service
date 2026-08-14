"""Import season snapshots from the ccmax season archive into static/season-data/.

The archive (``ccmax资料/数据模板``) is the source of truth for season reference
data: ``data/catalog.json`` lists seasons, each season has ``season.json`` plus
one full snapshot per game version. This script copies the *default* version of
each season into the Web repository so production never depends on files
outside the repo:

    static/season-data/
        catalog.json              site-facing season index
        <season_id>/
            index.json            compact payload for the reference page
            champions.json        full snapshot (server-side detail pages)
            traits.json           full snapshot
            items.json            full snapshot (simulator runtime data)
            assets/...            original images plus versioned WebP images

Usage (run from the repository root)::

    python scripts/season_library/import_from_archive.py            # all seasons
    python scripts/season_library/import_from_archive.py --season s18
    python scripts/season_library/import_from_archive.py --source "D:/.../数据模板"

Source resolution order: ``--source``, ``JCC_SEASON_ARCHIVE`` env var, then a
scan of ancestor directories for ``ccmax资料/数据模板`` (and legacy ``数据模版``).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from io import BytesIO
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_ROOT = REPO_ROOT / "static" / "season-data"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from season_rich_text import enrich_rich_text_fields  # noqa: E402

from official_supplements import apply_official_supplements  # noqa: E402

ARCHIVE_DIR_NAMES = (
    os.path.join("ccmax资料", "数据模板"),
    os.path.join("ccmax资料", "数据模版"),
)

# Card-grid thumbnails: splash art ships at up to 1624x750 (~130KB each) but
# renders at ~250 CSS px. A 500px WebP keeps DPR-2 sharpness at ~15-25KB.
CARD_WIDTH = 500
CARD_QUALITY = 75
ICON_MAX_SIZE = 96
ICON_QUALITY = 82


def resolve_source(cli_value: str | None) -> Path:
    candidates = []
    if cli_value:
        candidates.append(Path(cli_value))
    env_value = os.environ.get("JCC_SEASON_ARCHIVE")
    if env_value:
        candidates.append(Path(env_value))
    for ancestor in REPO_ROOT.parents:
        candidates.extend(ancestor / name for name in ARCHIVE_DIR_NAMES)
    for candidate in candidates:
        if (candidate / "data" / "catalog.json").is_file():
            return candidate
    raise SystemExit(
        "找不到赛季档案库（需包含 data/catalog.json）。请用 --source 或 JCC_SEASON_ARCHIVE 指定 数据模板 目录。"
    )


def load_json(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, payload, *, indent: int = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=indent)
        fh.write("\n")


def image_path(image, *, prefer_optimized: bool = False) -> str | None:
    """Reduce an archive image object to its bundle-relative path."""
    if isinstance(image, dict):
        local = image.get("optimized_local_path") if prefer_optimized else None
        local = local or image.get("local_path")
        if isinstance(local, str) and local:
            return local
    return None


def strip_image_objects(value):
    """Recursively replace {'local_path': ...} image objects with plain paths."""
    if isinstance(value, dict):
        if "local_path" in value and isinstance(value.get("local_path"), str):
            return value["local_path"]
        return {key: strip_image_objects(item) for key, item in value.items()}
    if isinstance(value, list):
        return [strip_image_objects(item) for item in value]
    return value


def build_card_thumbnail(source: Path, target: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        frame = image.convert("RGB")
        if frame.width > CARD_WIDTH:
            height = round(frame.height * CARD_WIDTH / frame.width)
            frame = frame.resize((CARD_WIDTH, height), Image.LANCZOS)
        frame.save(target, format="WEBP", quality=CARD_QUALITY, method=6)
    return True


def build_icon_webp(source: Path, target: Path) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False
    image_source = source
    if source.suffix.lower() == ".svg":
        try:
            from cairosvg import svg2png
        except ImportError:
            return False
        image_source = BytesIO(
            svg2png(
                bytestring=source.read_bytes(),
                output_width=ICON_MAX_SIZE,
                output_height=ICON_MAX_SIZE,
            )
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_source) as image:
        frame = image.convert("RGBA") if image.mode in {"P", "LA", "RGBA"} else image.convert("RGB")
        frame.thumbnail((ICON_MAX_SIZE, ICON_MAX_SIZE), Image.LANCZOS)
        frame.save(target, format="WEBP", quality=ICON_QUALITY, method=6)
    return True


def add_optimized_image(
    image: dict | None,
    target_dir: Path,
    relative_target: str,
) -> bool:
    if not isinstance(image, dict):
        return False
    source_path = image.get("local_path")
    if not isinstance(source_path, str) or not (target_dir / source_path).is_file():
        return False
    if not build_icon_webp(target_dir / source_path, target_dir / relative_target):
        return False
    image["optimized_local_path"] = relative_target
    return True


def generate_optimized_images(
    target_dir: Path,
    version_id: str,
    champions_doc: dict,
    traits_doc: dict,
    items_doc: dict,
    board_units_doc: dict,
) -> tuple[int, list[str]]:
    root = f"assets/optimized/{version_id}"
    built = 0
    missing = []
    for champion in champions_doc.get("champions") or []:
        champion_id = str(champion["id"])
        images = champion.get("images") or {}
        if add_optimized_image(images.get("icon"), target_dir, f"{root}/champions/{champion_id}.webp"):
            built += 1
        else:
            missing.append(f"champion:{champion_id}")
        for position, skill in enumerate(champion.get("skills") or []):
            skill_id = str(skill.get("id") or f"{champion_id}_{position + 1}")
            if add_optimized_image(skill.get("image"), target_dir, f"{root}/skills/{skill_id}.webp"):
                built += 1
    for trait in traits_doc.get("traits") or []:
        trait_id = str(trait["id"])
        if add_optimized_image(trait.get("image"), target_dir, f"{root}/traits/{trait_id}.webp"):
            built += 1
        else:
            missing.append(f"trait:{trait_id}")
    for item in items_doc.get("items") or []:
        item_id = str(item["id"])
        if add_optimized_image(item.get("image"), target_dir, f"{root}/items/{item_id}.webp"):
            built += 1
        else:
            missing.append(f"item:{item_id}")
    for unit in board_units_doc.get("board_units") or []:
        unit_id = str(unit["id"])
        if add_optimized_image(unit.get("image"), target_dir, f"{root}/board-units/{unit_id}.webp"):
            built += 1
        else:
            missing.append(f"board-unit:{unit_id}")
    return built, missing


def compact_champion(champion: dict, card_path: str | None = None) -> dict:
    skill = (champion.get("skills") or [{}])[0]
    images = champion.get("images") or {}
    availability = champion.get("availability") or {}
    return {
        "id": champion["id"],
        "name": champion["name"],
        "cost": champion.get("cost"),
        "trait_ids": champion.get("trait_ids") or [],
        "availability": {
            "type": availability.get("type"),
            "description": availability.get("description"),
        },
        "tags": champion.get("tags") or [],
        "icon": image_path(images.get("icon"), prefer_optimized=True),
        "splash": image_path(images.get("splash")),
        "card": card_path,
        "has_stats": bool(champion.get("stats_by_star")),
        "skill": {
            "name": skill.get("name"),
            "description": skill.get("description"),
            "description_tokens": skill.get("description_tokens"),
            "image": image_path(skill.get("image"), prefer_optimized=True),
        },
    }


def compact_trait(trait: dict) -> dict:
    return {
        "id": trait["id"],
        "name": trait["name"],
        "category": trait.get("category"),
        "description": trait.get("description"),
        "description_tokens": trait.get("description_tokens"),
        "image": image_path(trait.get("image"), prefer_optimized=True),
        "breakpoints": [
            {
                "min_units": bp.get("min_units"),
                "max_units": bp.get("max_units"),
                "style": bp.get("style"),
                "effect": bp.get("effect"),
                "effect_tokens": bp.get("effect_tokens"),
            }
            for bp in trait.get("breakpoints") or []
        ],
    }


def compact_mechanics(version_dir: Path) -> list[dict]:
    index_path = version_dir / "mechanics" / "index.json"
    if not index_path.is_file():
        return []
    mechanics = []
    for entry in load_json(index_path).get("mechanics") or []:
        doc = load_json(version_dir / "mechanics" / entry["file"])
        enrich_rich_text_fields(doc)
        records = [
            {
                "id": record.get("id"),
                "name": record.get("name"),
                "description": record.get("description"),
                "description_tokens": record.get("description_tokens"),
                "image": image_path(record.get("image")),
                "data": strip_image_objects(record.get("data") or {}),
            }
            for record in doc.get("records") or []
        ]
        mechanics.append(
            {
                "id": entry["id"],
                "kind": entry.get("kind"),
                "display_name": entry.get("display_name"),
                "has_images": bool(entry.get("has_images")),
                "entries": records,
            }
        )
    return mechanics


def import_season(source_root: Path, catalog_entry: dict) -> dict:
    season_id = catalog_entry["season_id"]
    season = load_json(source_root / "data" / catalog_entry["path"])
    version_ref = next(
        (v for v in season.get("versions") or [] if v["version_id"] == season.get("default_version_id")),
        None,
    ) or (season.get("versions") or [None])[-1]
    if not version_ref:
        raise SystemExit(f"赛季 {season_id} 在 season.json 中没有可用版本")
    season_dir = (source_root / "data" / catalog_entry["path"]).parent
    version_dir = (season_dir / version_ref["path"]).parent
    version_meta = load_json(season_dir / version_ref["path"])

    target_dir = TARGET_ROOT / season_id
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True)

    champions_doc = load_json(version_dir / "champions.json")
    traits_doc = load_json(version_dir / "traits.json")
    items_path = version_dir / "items.json"
    items_doc = load_json(items_path) if items_path.is_file() else {"items": []}

    assets_dir = version_dir / "assets"
    if assets_dir.is_dir():
        shutil.copytree(assets_dir, target_dir / "assets")

    supplements = apply_official_supplements(
        version_dir,
        target_dir,
        season,
        champions_doc,
        traits_doc,
        load_json,
    )
    board_units_doc = {
        "version_id": version_meta["version_id"],
        "rich_text_version": 1,
        "board_units": supplements["board_units"],
    }
    for document in (champions_doc, traits_doc, items_doc, board_units_doc):
        document["rich_text_version"] = 1
        enrich_rich_text_fields(document)

    optimized_count, optimized_missing = generate_optimized_images(
        target_dir,
        version_meta["version_id"],
        champions_doc,
        traits_doc,
        items_doc,
        board_units_doc,
    )
    dump_json(target_dir / "champions.json", champions_doc, indent=2)
    dump_json(target_dir / "traits.json", traits_doc, indent=2)
    dump_json(target_dir / "items.json", items_doc, indent=2)
    dump_json(target_dir / "board_units.json", board_units_doc, indent=2)
    print(f"  WebP: 已生成 {optimized_count} 张 96px 版本化小图")
    if supplements["champions"]:
        print(f"  官方补全弈子: {', '.join(supplements['champions'])}")
    if supplements["board_units"]:
        print(f"  模拟器棋盘对象: {', '.join(unit['name'] for unit in supplements['board_units'])}")
    if optimized_missing:
        print(f"  警告: {season_id} 有 {len(optimized_missing)} 个模拟器小图缺少源文件")

    champions = []
    card_failures = 0
    for item in champions_doc.get("champions") or []:
        splash = image_path((item.get("images") or {}).get("splash"))
        card_path = None
        if splash and (target_dir / splash).is_file():
            candidate = f"assets/champions/card/{item['id']}.webp"
            if build_card_thumbnail(target_dir / splash, target_dir / candidate):
                card_path = candidate
            else:
                card_failures += 1
        champions.append(compact_champion(item, card_path))
    if card_failures:
        print(f"  警告: {season_id} 有 {card_failures} 张卡片缩图未生成（需要 Pillow）")
    traits = [compact_trait(item) for item in traits_doc.get("traits") or []]
    mechanics = compact_mechanics(version_dir)

    index_payload = {
        "season_id": season_id,
        "display_name": season.get("display_name"),
        "set_number": season.get("set_number"),
        "set_variant": season.get("set_variant"),
        "theme": season.get("theme"),
        "status": catalog_entry.get("status") or season.get("status"),
        "game_version": version_meta.get("game_version"),
        "version_id": version_meta.get("version_id"),
        "effective_at": version_meta.get("effective_at"),
        "champions": champions,
        "traits": traits,
        "mechanics": mechanics,
        "rich_text_version": 1,
    }
    dump_json(target_dir / "index.json", index_payload)

    missing = sorted(set(check_assets(target_dir, index_payload) + check_assets(target_dir, board_units_doc)))
    for path in missing:
        print(f"  警告: {season_id} 引用的图片不存在: {path}")

    return {
        "season_id": season_id,
        "display_name": season.get("display_name"),
        "set_number": season.get("set_number"),
        "set_variant": season.get("set_variant"),
        "theme": season.get("theme"),
        "status": catalog_entry.get("status") or season.get("status"),
        "game_version": version_meta.get("game_version"),
        "version_id": version_meta.get("version_id"),
        "effective_at": version_meta.get("effective_at"),
        "path": f"{season_id}/index.json",
        "counts": {
            "champions": len(champions),
            "traits": len(traits),
            "mechanics": sum(len(m["entries"]) for m in mechanics),
            "board_units": len(board_units_doc["board_units"]),
        },
    }


def iter_image_paths(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from iter_image_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from iter_image_paths(item)
    elif isinstance(value, str) and value.startswith("assets/"):
        yield value


def check_assets(target_dir: Path, index_payload: dict) -> list[str]:
    return sorted(
        {
            path
            for path in iter_image_paths(index_payload)
            if not (target_dir / path).is_file()
        }
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", help="数据模版 目录路径")
    parser.add_argument("--season", help="只导入指定 season_id")
    args = parser.parse_args(argv)

    source_root = resolve_source(args.source)
    catalog = load_json(source_root / "data" / "catalog.json")
    entries = catalog.get("seasons") or []
    if args.season:
        entries = [entry for entry in entries if entry["season_id"] == args.season]
        if not entries:
            raise SystemExit(f"catalog 中没有 season_id={args.season}")

    existing = {}
    catalog_path = TARGET_ROOT / "catalog.json"
    if catalog_path.is_file() and args.season:
        existing = {
            entry["season_id"]: entry
            for entry in load_json(catalog_path).get("seasons") or []
        }

    print(f"档案库: {source_root}")
    for entry in entries:
        summary = import_season(source_root, entry)
        existing[summary["season_id"]] = summary
        counts = summary["counts"]
        print(
            f"已导入 {summary['season_id']} {summary['display_name']} "
            f"(版本 {summary['game_version']}, 弈子 {counts['champions']}, "
            f"羁绊 {counts['traits']}, 机制 {counts['mechanics']})"
        )

    if not args.season:
        existing = {entry["season_id"]: existing[entry["season_id"]] for entry in entries}
    order = [entry["season_id"] for entry in catalog.get("seasons") or []]
    seasons = [existing[season_id] for season_id in order if season_id in existing]
    dump_json(catalog_path, {"format_version": "1.0.0", "seasons": seasons})
    print(f"catalog 写入 {catalog_path}（{len(seasons)} 个赛季）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
