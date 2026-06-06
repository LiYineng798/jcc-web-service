from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
import urllib.request


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    if spec.loader is None:
        raise RuntimeError(f'无法加载模块: {path}')
    spec.loader.exec_module(module)
    return module


SCRIPT_DIR = Path(__file__).resolve().parent
CONVERTER = load_module('convert_s16_datatft_raw_to_live_comps', SCRIPT_DIR / 'convert_s16_datatft_raw_to_live_comps.py')
UPLOADER = load_module('upload_live_comps', SCRIPT_DIR / 'upload_live_comps.py')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='Convert local DataTFT S16 raw JSON and upload it to the JCC live-comps endpoint in one command.',
    )
    parser.add_argument('--input', default=str(SCRIPT_DIR / 'datatft_s16_raw.json'), help='Path to raw DataTFT S16 JSON')
    parser.add_argument('--output', default=str(SCRIPT_DIR / 'team_codes_by_tier.s16.json'), help='Path to write converted JCC JSON')
    parser.add_argument('--url', required=True, help='Upload endpoint URL, e.g. https://jcc.np5.top/api/live-comps/upload')
    parser.add_argument('--token', required=True, help='Upload token sent via X-Upload-Token')
    parser.add_argument('--season-id', default='s16-legends', help='Season id used for upload and payload meta')
    parser.add_argument('--timeout', type=int, default=180, help='Upload timeout in seconds')
    parser.add_argument('--image-base', default=CONVERTER.DEFAULT_IMAGE_BASE, help='Hero image base URL')
    return parser.parse_args(argv)


def build_payload(input_path: Path, season_id: str, image_base: str) -> dict:
    raw_payload = json.loads(input_path.read_text(encoding='utf-8'))
    return CONVERTER.convert_payload(raw_payload, season_id, image_base)


def write_payload(payload: dict, output_path: Path) -> tuple[int, dict[str, int]]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    tier_counts = {tier: len(payload['tiers'].get(tier, [])) for tier in CONVERTER.TIER_ORDER}
    total = sum(tier_counts.values())
    return total, tier_counts


def main(argv=None, upload_func=None, opener=urllib.request.urlopen):
    args = parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)
    upload_func = upload_func or UPLOADER.upload_payload
    try:
        payload = build_payload(input_path, args.season_id, args.image_base)
        total, tier_counts = write_payload(payload, output_path)
        print(f'[1/2] 已生成上传文件：{output_path}')
        print(f'[info] 总阵容数：{total}')
        for tier in CONVERTER.TIER_ORDER:
            print(f'- {tier}: {tier_counts[tier]}')
        print('[2/2] 开始上传到 JCC 服务器')
        result = upload_func(
            str(output_path),
            args.url,
            args.token,
            timeout=args.timeout,
            season_id=args.season_id,
            opener=opener,
        )
        print(result)
        return 0
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        print(f'upload failed: HTTP {exc.code} {detail}', file=sys.stderr)
        return 1
    except URLError as exc:
        print(f'upload failed: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        print(f'upload failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
