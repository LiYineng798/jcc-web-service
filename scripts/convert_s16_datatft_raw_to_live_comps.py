from __future__ import annotations

import argparse
import json
from pathlib import Path


TIER_ORDER = ("S", "A", "B", "C", "D")
DEFAULT_IMAGE_BASE = "https://static.datatft.com/images/heros/default"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Convert a DataTFT raw season JSON file into JCC live-comps JSON without lineup codes.",
    )
    default_input = Path(__file__).resolve().parent / "datatft_s16_raw.json"
    default_output = Path(__file__).resolve().parent / "team_codes_by_tier.s16.json"
    parser.add_argument("--input", default=str(default_input), help="Path to raw DataTFT JSON")
    parser.add_argument("--output", default=str(default_output), help="Path to write converted JSON")
    parser.add_argument("--season-id", default="s16-legends", help="Season id written into meta")
    parser.add_argument("--image-base", default=DEFAULT_IMAGE_BASE, help="Hero image base URL")
    return parser.parse_args(argv)


def hero_image_url(image_base: str, hero_id: str) -> str:
    return f"{image_base.rstrip('/')}/{hero_id}.jpg"


def convert_item(item: dict, image_base: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    hero_id = str(item.get("heroId") or "").strip()
    title = str(item.get("title") or "").strip()
    tier = str(item.get("tier") or "").strip().upper()
    team_id = str(item.get("id") or "").strip()
    heroes = item.get("heros") if isinstance(item.get("heros"), list) else []
    hero_images = []
    for hero in heroes:
        if not isinstance(hero, dict):
            continue
        member_id = str(hero.get("id") or "").strip()
        if member_id:
            hero_images.append(hero_image_url(image_base, member_id))
    if not team_id or not title or tier not in TIER_ORDER or not hero_id or not hero_images:
        return None
    return {
        "id": team_id,
        "title": title,
        "tier": tier,
        "jccCode": "",
        "mainAvatar": hero_image_url(image_base, hero_id),
        "heroImages": hero_images,
        "heroId": hero_id,
        "score": item.get("score"),
        "strategyId": item.get("strategyId"),
        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
    }


def convert_payload(raw_payload: dict, season_id: str, image_base: str) -> dict:
    raw_items = raw_payload.get("data", {}).get("list", [])
    if not isinstance(raw_items, list):
        raw_items = []
    grouped = {tier: [] for tier in TIER_ORDER}
    for raw_item in raw_items:
        item = convert_item(raw_item, image_base)
        if item:
            grouped[item["tier"]].append(item)
    for tier in TIER_ORDER:
        grouped[tier].sort(key=lambda item: (-(float(item.get("score") or 0)), item["id"]))
    return {
        "meta": {
            "source": "datatft-raw-converter",
            "season_id": season_id,
            "supports_copy": False,
        },
        "tiers": grouped,
    }


def main(argv=None):
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)
    raw_payload = json.loads(input_path.read_text(encoding="utf-8"))
    converted = convert_payload(raw_payload, args.season_id, args.image_base)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(converted, ensure_ascii=False, indent=2), encoding="utf-8")
    total = sum(len(converted["tiers"][tier]) for tier in TIER_ORDER)
    print(f"[done] wrote {total} teams to {output_path}")
    for tier in TIER_ORDER:
        print(f"- {tier}: {len(converted['tiers'][tier])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
