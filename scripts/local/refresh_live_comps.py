import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scripts.local import upload_live_comps


BASE_DIR = PROJECT_DIR
DEFAULT_FETCH_SCRIPT = BASE_DIR / '实时获取阵容码' / '阵容码代理获取' / 'fetch_tiered_codes.py'
DEFAULT_OUTPUT_PATH = BASE_DIR / '实时获取阵容码' / '阵容码代理获取' / 'team_codes_by_tier.verify.json'
DEFAULT_UPLOAD_URL = 'https://jcc.np5.top/api/live-comps/upload'
ASSET_UPLOAD_PATH = '/api/live-comps/assets/upload'
ASSET_ROUTE = '/api/live-comps/assets'
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
CONTENT_TYPE_EXTENSIONS = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/webp': '.webp',
    'image/gif': '.gif',
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Fetch live comps JSON and upload it to JCC server.')
    parser.add_argument('--fetch-script', default=str(DEFAULT_FETCH_SCRIPT), help='Path to fetch_tiered_codes.py')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT_PATH), help='Generated team_codes_by_tier.verify.json path')
    parser.add_argument('--url', default=DEFAULT_UPLOAD_URL, help='Live comps upload endpoint')
    parser.add_argument('--token', default=os.environ.get('JCC_LIVE_COMPS_UPLOAD_TOKEN', ''), help='Upload token; defaults to env JCC_LIVE_COMPS_UPLOAD_TOKEN')
    parser.add_argument('--upload-timeout', type=int, default=180, help='Upload timeout in seconds')
    parser.add_argument('--image-timeout', type=int, default=20, help='Image download/upload timeout in seconds')
    parser.add_argument('--skip-image-upload', action='store_true', help='Do not pre-cache images before uploading JSON')
    parser.add_argument('--season', default='17')
    parser.add_argument('--tier', default='ALL')
    parser.add_argument('--time', dest='time_window', default='7')
    parser.add_argument('--country-code', default='CN')
    parser.add_argument('--count-per-protocol', type=int, default=6)
    parser.add_argument('--max-rounds', type=int, default=0)
    parser.add_argument('--skip-fetch', action='store_true', help='Upload existing output JSON without fetching again')
    return parser.parse_args(argv)


def fetch_live_comps(args, runner=subprocess.run):
    command = [
        sys.executable,
        args.fetch_script,
        '--output', args.output,
        '--season', str(args.season),
        '--tier', str(args.tier),
        '--time', str(args.time_window),
        '--country-code', str(args.country_code),
        '--count-per-protocol', str(args.count_per_protocol),
        '--max-rounds', str(args.max_rounds),
    ]
    return runner(command, cwd=str(BASE_DIR), check=True)


def load_payload(path):
    path = Path(path)
    if not path.exists():
        return None
    with path.open('r', encoding='utf-8') as file:
        return json.load(file)


def flatten_payload(payload):
    if not isinstance(payload, dict):
        return {}
    flattened = {}
    tiers = payload.get('tiers') or {}
    for tier, items in tiers.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict) or item.get('id') is None:
                continue
            item_id = str(item.get('id'))
            flattened[item_id] = {
                'id': item_id,
                'title': str(item.get('title') or ''),
                'tier': str(item.get('tier') or tier),
                'jccCode': str(item.get('jccCode') or ''),
                'heroId': str(item.get('heroId') or ''),
            }
    return flattened


def compare_payloads(old_payload, new_payload):
    old_items = flatten_payload(old_payload)
    new_items = flatten_payload(new_payload)
    old_ids = set(old_items)
    new_ids = set(new_items)
    added = [new_items[item_id] for item_id in sorted(new_ids - old_ids)]
    removed = [old_items[item_id] for item_id in sorted(old_ids - new_ids)]
    code_changed = []
    info_changed = []
    for item_id in sorted(old_ids & new_ids):
        old_item = old_items[item_id]
        new_item = new_items[item_id]
        if old_item['jccCode'] != new_item['jccCode']:
            code_changed.append({'before': old_item, 'after': new_item})
            continue
        if any(old_item[key] != new_item[key] for key in ['title', 'tier', 'heroId']):
            info_changed.append({'before': old_item, 'after': new_item})
    return {
        'added': added,
        'removed': removed,
        'code_changed': code_changed,
        'info_changed': info_changed,
    }


def format_item(item):
    return f"{item.get('tier', '-')}/{item.get('title', '-')}(id={item.get('id', '-')})"


def format_diff_summary(diff, limit=30):
    lines = [
        '[更新对比]',
        f"新增阵容：{len(diff['added'])}",
        f"移除阵容：{len(diff['removed'])}",
        f"阵容码变化：{len(diff['code_changed'])}",
        f"名称/段位变化：{len(diff['info_changed'])}",
    ]
    sections = [
        ('新增', [format_item(item) for item in diff['added']]),
        ('移除', [format_item(item) for item in diff['removed']]),
        ('阵容码变化', [f"{format_item(change['before'])} -> {format_item(change['after'])}" for change in diff['code_changed']]),
        ('名称/段位变化', [f"{format_item(change['before'])} -> {format_item(change['after'])}" for change in diff['info_changed']]),
    ]
    for label, items in sections:
        if not items:
            continue
        lines.append(f'[{label}]')
        lines.extend(f'- {item}' for item in items[:limit])
        if len(items) > limit:
            lines.append(f'- 还有 {len(items) - limit} 项未展示')
    return '\n'.join(lines)


def is_local_asset_url(value):
    return isinstance(value, str) and value.startswith(f'{ASSET_ROUTE}/')


def is_remote_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)


def extension_for_url(url, content_type=''):
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in ALLOWED_IMAGE_EXTENSIONS:
        return '.jpg' if suffix == '.jpeg' else suffix
    return CONTENT_TYPE_EXTENSIONS.get(str(content_type or '').split(';', 1)[0].lower(), '.jpg')


def asset_filename_for_url(url, content_type=''):
    return f"{hashlib.sha256(url.encode('utf-8')).hexdigest()}{extension_for_url(url, content_type)}"


def download_image(url, timeout=20, opener=urllib.request.urlopen):
    request = urllib.request.Request(url, headers={'User-Agent': 'JCC-Lineup-Manager/1.0'})
    with opener(request, timeout=timeout) as response:
        content_type = response.headers.get('Content-Type', '') if getattr(response, 'headers', None) else ''
        data = response.read()
    return data, content_type


def upload_asset(filename, data, upload_url, token, timeout=20, opener=urllib.request.urlopen):
    payload = json.dumps({
        'filename': filename,
        'content_base64': base64.b64encode(data).decode('ascii'),
    }).encode('utf-8')
    request = urllib.request.Request(
        upload_url,
        data=payload,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-Upload-Token': token,
        },
    )
    with opener(request, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


def asset_upload_url(upload_url):
    return upload_url.rsplit('/api/live-comps/upload', 1)[0] + ASSET_UPLOAD_PATH


def collect_image_urls(payload):
    urls = []
    for items in (payload.get('tiers') or {}).values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            urls.append(item.get('mainAvatar'))
            urls.extend(item.get('heroImages') or [])
    return sorted({url for url in urls if is_remote_url(url) and not is_local_asset_url(url)})


def rewrite_payload_images(payload, replacements):
    for items in (payload.get('tiers') or {}).values():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get('mainAvatar') in replacements:
                item['mainAvatar'] = replacements[item['mainAvatar']]
            item['heroImages'] = [replacements.get(url, url) for url in (item.get('heroImages') or [])]
    return payload


def precache_images(payload, args, opener=urllib.request.urlopen):
    urls = collect_image_urls(payload)
    replacements = {}
    upload_url = asset_upload_url(args.url)
    for index, url in enumerate(urls, start=1):
        data, content_type = download_image(url, timeout=args.image_timeout, opener=opener)
        filename = asset_filename_for_url(url, content_type)
        result = upload_asset(filename, data, upload_url, args.token, timeout=args.image_timeout, opener=opener)
        replacements[url] = result['url']
        print(f'[image {index}/{len(urls)}] {url} -> {result["url"]}')
    return rewrite_payload_images(payload, replacements), len(replacements)


def refresh_live_comps(args, runner=subprocess.run, opener=upload_live_comps.urllib.request.urlopen):
    if not args.token:
        raise ValueError('缺少上传令牌：请传 --token 或设置环境变量 JCC_LIVE_COMPS_UPLOAD_TOKEN')
    output_path = Path(args.output)
    old_payload = load_payload(output_path)
    if not args.skip_fetch:
        fetch_live_comps(args, runner=runner)
    if not output_path.exists():
        raise FileNotFoundError(f'实时阵容 JSON 不存在：{output_path}')
    new_payload = load_payload(output_path)
    diff = compare_payloads(old_payload, new_payload)
    if not args.skip_image_upload:
        new_payload, image_count = precache_images(new_payload, args, opener=opener)
        output_path.write_text(json.dumps(new_payload, ensure_ascii=False, indent=2), encoding='utf-8')
    else:
        image_count = 0
    return upload_live_comps.upload_payload(
        file_path=str(output_path),
        url=args.url,
        token=args.token,
        timeout=args.upload_timeout,
        opener=opener,
    ), diff, image_count


def main(argv=None, runner=subprocess.run, opener=upload_live_comps.urllib.request.urlopen):
    args = parse_args(argv)
    try:
        print('[1/2] 获取实时阵容 JSON' if not args.skip_fetch else '[1/2] 跳过获取，使用已有 JSON')
        result, diff, image_count = refresh_live_comps(args, runner=runner, opener=opener)
        print(format_diff_summary(diff))
        if not args.skip_image_upload:
            print(f'[图片缓存] 已预上传 {image_count} 张图片')
        print('[2/2] 上传完成')
        print(result)
        return 0
    except subprocess.CalledProcessError as exc:
        print(f'获取实时阵容失败，退出码：{exc.returncode}', file=sys.stderr)
        return exc.returncode or 1
    except Exception as exc:
        print(f'刷新实时阵容失败：{exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
