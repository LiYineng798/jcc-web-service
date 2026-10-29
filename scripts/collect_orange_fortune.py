"""Archive the official S400001 time-card data and diff it against the shipped snapshot.

Downloads are treated as data only: JSON is parsed, never evaluated, and raw bytes are
kept beside every parse result. The branch is chosen from the official version
directory at run time; nothing below pins a patch number.
"""
import argparse
import concurrent.futures
import hashlib
import io
import json
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://game.gtimg.cn/images/lol/act/jkzlk/js'
DIRECTORY_URL = f'{BASE}/config/versiondataconfig.js'
BEIJING = timezone(timedelta(hours=8))
KNOWN_CARD_FIELDS = ('id', 'iRarityTier', 'sName', 'sIcon', 'sTags', 'sArgs', 'sDesc')
IMAGE_MAGIC = {b'\x89PNG\r\n\x1a\n': 'PNG', b'\xff\xd8\xff': 'JPEG', b'GIF8': 'GIF', b'RIFF': 'WEBP'}
PUNCTUATION = re.compile(r'[\s，。、；：！？,.;:!?（）()【】\[\]「」“”"\'‘’…·—\-]+')
NUMBER = re.compile(r'\d+(?:\.\d+)?')


def now():
    return datetime.now(BEIJING).isoformat(timespec='seconds')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def fetch(url, timeout, attempts):
    """Return a result dict; 4xx is final, timeouts/5xx/network errors are retried a few times."""
    record = {'url': url, 'attempts': 0}
    for attempt in range(1, attempts + 1):
        record['attempts'] = attempt
        record['requested_at'] = now()
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'jcc-orange-fortune-archiver/1'})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                record.update(status=response.status, error=None, body=body,
                              etag=response.headers.get('ETag'),
                              last_modified=response.headers.get('Last-Modified'),
                              content_type=response.headers.get('Content-Type'))
                return record
        except urllib.error.HTTPError as error:
            record.update(status=error.code, error=f'http_{error.code}', body=None,
                          etag=error.headers.get('ETag'), last_modified=error.headers.get('Last-Modified'),
                          content_type=error.headers.get('Content-Type'))
            if error.code < 500:
                return record
        except (socket.timeout, TimeoutError) as error:
            record.update(status=None, error='timeout', detail=str(error), body=None)
        except urllib.error.URLError as error:
            kind = 'timeout' if isinstance(error.reason, (socket.timeout, TimeoutError)) else 'network_error'
            record.update(status=None, error=kind, detail=str(error.reason), body=None)
        if attempt < attempts:
            time.sleep(attempt)
    return record


def parse_json(data):
    try:
        return json.loads(data.decode('utf-8-sig')), None
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return None, f'{type(error).__name__}: {error}'


def parse_arguments(value):
    """Ordered pairs so duplicate or bare segments survive; split on the first '=' only."""
    pairs = []
    for part in value.split('^') if value else []:
        key, sep, rest = part.partition('=')
        pairs.append([key, rest if sep else None])
    return pairs


def args_dict(pairs):
    return {key: value for key, value in pairs}


def describe_text_change(old, new):
    kinds = []
    if PUNCTUATION.sub('', old) == PUNCTUATION.sub('', new):
        return ['punctuation_or_whitespace_only']
    if NUMBER.findall(old) != NUMBER.findall(new):
        kinds.append('numbers_changed')
    if NUMBER.sub('#', PUNCTUATION.sub('', old)) != NUMBER.sub('#', PUNCTUATION.sub('', new)):
        kinds.append('wording_changed')
    return kinds


def inspect_image(data):
    if not data:
        return None, 'empty'
    kind = next((name for magic, name in IMAGE_MAGIC.items() if data.startswith(magic)), None)
    if kind is None:
        return None, 'not_image'
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            return {'format': image.format, 'width': image.width, 'height': image.height}, None
    except Exception as error:  # Pillow raises several unrelated types for corrupt files.
        return None, f'decode_error: {type(error).__name__}: {error}'


def pixels(data):
    with Image.open(io.BytesIO(data)) as image:
        return image.size, image.convert('RGBA').tobytes()


class Archive:
    def __init__(self, path):
        self.path = path
        self.entries = []

    def save(self, relative, data, source=None, fetched=None):
        target = self.path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        entry = {'path': relative, 'size': len(data), 'sha256': sha256(data)}
        if source:
            entry['source_url'] = source
        if fetched:
            entry.update({key: fetched.get(key) for key in ('status', 'requested_at', 'etag', 'last_modified', 'content_type')})
        self.entries.append(entry)
        return entry

    def save_json(self, relative, value):
        data = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        return self.save(relative, data)


def download_image(key, card, timeout, attempts):
    url = card.get('sIcon')
    if not url:
        return {'card_id': key, 'url': url, 'error': 'no_icon_url'}, None
    result = fetch(url, timeout, attempts)
    record = {'card_id': key, 'url': url, 'status': result.get('status'), 'downloaded_at': result.get('requested_at'),
              'attempts': result.get('attempts'), 'etag': result.get('etag'),
              'last_modified': result.get('last_modified'), 'content_type': result.get('content_type')}
    if result['body'] is None:
        record['error'] = result['error']
        return record, None
    meta, image_error = inspect_image(result['body'])
    record.update(meta or {}, error=image_error, size=len(result['body']), sha256=sha256(result['body']))
    return record, result['body']


def store_image(archive, key, record, body):
    if body is not None:
        suffix = (record.get('format') or 'bin').lower().replace('jpeg', 'jpg')
        folder = 'images' if not record.get('error') else 'images/rejected'
        record['local_path'] = archive.save(f'{folder}/{key}.{suffix}', body, record['url'])['path']
    return record


def select_branch(directory, mode, season):
    candidates = [entry for entry in directory if str(entry.get('mode')) == mode and entry.get('season') == season]
    # Newest start time wins; the is_newest_version flag has been 0 for a live branch before.
    ordered = sorted(candidates, key=lambda entry: str(entry.get('version_start_time') or ''), reverse=True)
    return ordered[0] if ordered else None, ordered


def collect(output, mode, season, baseline_path, baseline_images, timeout, attempts, workers):
    archive = Archive(output)
    failures = []
    fetched = fetch(DIRECTORY_URL, timeout, attempts)
    if fetched['body'] is None:
        failures.append({k: v for k, v in fetched.items() if k != 'body'})
        archive.save_json('failures.json', failures)
        raise SystemExit(f'Version directory failed: {fetched["error"]}')
    archive.save('raw/config/versiondataconfig.js', fetched['body'], DIRECTORY_URL, fetched)
    directory, error = parse_json(fetched['body'])
    if error:
        raise SystemExit(f'Version directory is not JSON: {error}')
    archive.save_json('parsed/config/versiondataconfig.json', directory)

    entry, candidates = select_branch(directory, mode, season)
    archive.save_json('selection.json', {
        'mode': mode, 'season': season, 'selected': entry,
        'candidates': candidates,
        'same_mode_other_seasons': sorted({e.get('season') for e in directory if str(e.get('mode')) == mode} - {season}),
        'rule': 'mode 与 season 同时匹配；多条时取 version_start_time 最新者；不依据 is_newest_version 或 name 过滤。',
    })
    if entry is None:
        archive.save_json('failures.json', [{'error': 'branch_not_found', 'mode': mode, 'season': season}])
        raise SystemExit(f'Branch mode={mode} season={season} not found; nothing else was substituted.')

    endpoints = {}
    for field, path in sorted(entry.items()):
        if not field.endswith('url') or not path:
            continue
        url = BASE + path
        result = fetch(url, timeout, attempts)
        info = {'field': field, 'url': url, **{k: result.get(k) for k in
                ('status', 'error', 'attempts', 'requested_at', 'etag', 'last_modified', 'content_type', 'detail')}}
        if result['body'] is not None:
            info['raw'] = archive.save('raw' + path, result['body'], url, result)['path']
            payload, parse_error = parse_json(result['body'])
            info['parse_error'] = parse_error
            if payload is not None:
                info['parsed'] = archive.save_json('parsed' + path.rsplit('.', 1)[0] + '.json', payload)['path']
                if isinstance(payload, dict):
                    info['top_level'] = {key: payload.get(key) for key in ('version', 'season', 'setId', 'time') if key in payload}
                    data = payload.get('data')
                    info['record_count'] = len(data) if isinstance(data, (list, dict)) else None
                endpoints[field] = payload
        else:
            failures.append(info)
        endpoints.setdefault(field, None)
        archive.save_json(f'endpoints/{field}.json', info)

    cards_payload = endpoints.get('cardurl')
    if not isinstance(cards_payload, dict) or not isinstance(cards_payload.get('data'), dict):
        archive.save_json('failures.json', failures)
        raise SystemExit('card.js missing or not a JSON object with data; see endpoints/cardurl.json')

    normalized = {key: cards_payload.get(key) for key in ('version', 'season', 'setId', 'time')}
    normalized['unknown_top_level'] = {k: v for k, v in cards_payload.items() if k not in ('version', 'season', 'setId', 'time', 'data')}
    normalized['cards'] = {}
    problems = []
    for key, card in cards_payload['data'].items():
        if not isinstance(card, dict) or str(card.get('id')) != key:
            problems.append({'key': key, 'issue': 'id_mismatch_or_not_object'})
        missing = [field for field in KNOWN_CARD_FIELDS if field not in card] if isinstance(card, dict) else list(KNOWN_CARD_FIELDS)
        if missing:
            problems.append({'key': key, 'issue': 'missing_fields', 'fields': missing})
        card = card if isinstance(card, dict) else {}
        normalized['cards'][key] = {
            'raw': card,
            'unknown_fields': sorted(set(card) - set(KNOWN_CARD_FIELDS)),
            'args': parse_arguments(card.get('sArgs') or ''),
            'tags': (card.get('sTags') or '').split('|'),
            'tags_meaning': 'inferred',
            'energy': None,
            'energy_note': '官方未提供',
        }
    normalized['problems'] = problems
    archive.save_json('cards/normalized.json', normalized)

    images = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {key: pool.submit(download_image, key, card, timeout, attempts)
                for key, card in sorted(cards_payload['data'].items())}
        for key, job in jobs.items():
            images[key] = store_image(archive, key, *job.result())
    if baseline_path:
        baseline_path, baseline_images = archive_baseline(archive, baseline_path, baseline_images)
    summary, diff = finalize(archive, cards_payload, images, failures, entry, baseline_path, baseline_images)
    return summary, diff


def archive_baseline(archive, baseline_path, baseline_images):
    """Copy the compared snapshot and its art so the diff stays reproducible after an import."""
    if not (archive.path / 'baseline/cards.json').is_file():
        archive.save('baseline/cards.json', Path(baseline_path).read_bytes(), str(baseline_path))
    for image in sorted(Path(baseline_images).glob('*.png')):
        if not (archive.path / 'baseline/images' / image.name).is_file():
            archive.save(f'baseline/images/{image.name}', image.read_bytes(), str(image))
    return archive.path / 'baseline/cards.json', archive.path / 'baseline/images'


def finalize(archive, cards_payload, images, failures, entry, baseline_path, baseline_images, extra=None):
    output = archive.path
    archive.save_json('images/manifest.json', images)
    image_failures = [r for r in images.values() if r.get('error')]
    archive.save_json('images/failures.json', image_failures)
    diff = build_diff(cards_payload, images, output, baseline_path, baseline_images)
    archive.save_json('diff.json', diff)
    archive.save_json('failures.json', failures + [{'kind': 'image', **r} for r in image_failures])
    summary = {'collected_at': now(), 'directory_url': DIRECTORY_URL, 'branch': entry,
               'card_count': len(cards_payload['data']), 'image_failures': len(image_failures),
               'endpoint_failures': len(failures), **(extra or {})}
    # Later saves of the same path replace earlier manifest rows.
    files = list({entry['path']: entry for entry in archive.entries}.values())
    manifest = {**summary, 'files': files}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return summary, diff


def retry_images(output, baseline_path, baseline_images, timeout, attempts):
    """Re-request only transient image failures; 404 and decode failures stay as recorded."""
    load = lambda name: json.loads((output / name).read_text(encoding='utf-8'))
    manifest, selection = load('manifest.json'), load('selection.json')
    entry = selection['selected']
    cards_payload = load('parsed' + entry['cardurl'].rsplit('.', 1)[0] + '.json')
    images = load('images/manifest.json')
    failures = [f for f in load('failures.json') if f.get('kind') != 'image']
    archive = Archive(output)
    archive.entries = manifest['files']
    baseline_path, baseline_images = archive_baseline(archive, baseline_path, baseline_images)
    history = manifest.get('image_retries', [])
    for key, record in sorted(images.items()):
        if record.get('error') not in ('timeout', 'network_error'):
            continue
        new_record, body = download_image(key, cards_payload['data'][key], timeout, attempts)
        new_record['previous_failures'] = record.get('previous_failures', []) + [
            {k: record.get(k) for k in ('error', 'status', 'downloaded_at', 'attempts')}]
        images[key] = store_image(archive, key, new_record, body)
        history.append({'card_id': key, 'at': new_record['downloaded_at'], 'result': new_record.get('error') or 'ok'})
    return finalize(archive, cards_payload, images, failures, entry, baseline_path, baseline_images,
                    {'first_collected_at': manifest.get('first_collected_at', manifest['collected_at']), 'image_retries': history})


def build_diff(current, images, output, baseline_path, baseline_images):
    if not baseline_path:
        return {'baseline': None}
    baseline = json.loads(Path(baseline_path).read_text(encoding='utf-8-sig'))
    old_cards, new_cards = baseline['data'], current['data']
    meta = {key: {'old': baseline.get(key), 'new': current.get(key)}
            for key in ('version', 'season', 'setId', 'time') if baseline.get(key) != current.get(key)}
    changes = {}
    for key in sorted(set(old_cards) & set(new_cards), key=int):
        old, new = old_cards[key], new_cards[key]
        fields = {}
        for field in sorted(set(old) | set(new)):
            if old.get(field) != new.get(field):
                fields[field] = {'old': old.get(field), 'new': new.get(field)}
        if 'sArgs' in fields:
            before, after = args_dict(parse_arguments(old.get('sArgs', ''))), args_dict(parse_arguments(new.get('sArgs', '')))
            fields['sArgs']['params'] = {
                name: {'old': before.get(name), 'new': after.get(name)}
                for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
            fields['sArgs']['order_only'] = before == after
        if 'sDesc' in fields:
            fields['sDesc']['kinds'] = describe_text_change(old.get('sDesc', ''), new.get('sDesc', ''))
        image = compare_image(key, images.get(key), output, baseline, baseline_images)
        if fields or image['status'] != 'same_bytes':
            changes[key] = {'name': new.get('sName'), 'fields': fields, 'image': image}
    added = sorted(set(new_cards) - set(old_cards), key=int)
    removed = sorted(set(old_cards) - set(new_cards), key=int)
    return {
        'baseline': {'path': str(baseline_path), 'version': baseline.get('version'), 'time': baseline.get('time'),
                     'count': len(old_cards)},
        'current': {'version': current.get('version'), 'time': current.get('time'), 'count': len(new_cards)},
        'metadata_changes': meta,
        'added': [{'id': key, 'card': new_cards[key], 'image': compare_image(key, images.get(key), output, baseline, baseline_images)} for key in added],
        'removed': [{'id': key, 'card': old_cards[key]} for key in removed],
        'retained': len(set(old_cards) & set(new_cards)),
        'changed': changes,
    }


def compare_image(key, record, output, baseline, baseline_images):
    old_asset = (baseline.get('assets') or {}).get(key)
    old_url = (baseline['data'].get(key) or {}).get('sIcon')
    result = {'old_url': old_url, 'new_url': (record or {}).get('url')}
    if not record or record.get('error'):
        result['status'] = 'download_failed'
        result['error'] = (record or {}).get('error')
        result['old_local'] = bool(old_asset)
        return result
    if not old_asset:
        result['status'] = 'no_baseline_image'
        return result
    old_bytes = (Path(baseline_images) / Path(old_asset['file']).name).read_bytes()
    new_bytes = (output / record['local_path']).read_bytes()
    result.update(old_sha256=sha256(old_bytes), new_sha256=record['sha256'])
    if old_bytes == new_bytes:
        result['status'] = 'same_bytes'
    elif pixels(old_bytes) == pixels(new_bytes):
        result['status'] = 'same_pixels_different_bytes'
    else:
        result['status'] = 'content_changed'
        result['old_size'], result['new_size'] = [old_asset['width'], old_asset['height']], [record['width'], record['height']]
    return result


def md(value):
    """Upstream text is shown in a Markdown table, so neutralize table/HTML syntax."""
    text = '' if value is None else str(value)
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '\\|').replace('\n', ' ')


def write_report(output):
    load = lambda name: json.loads((output / name).read_text(encoding='utf-8'))
    manifest, selection, diff = load('manifest.json'), load('selection.json'), load('diff.json')
    images = load('images/manifest.json')
    normalized = load('cards/normalized.json')
    endpoints = [load(f'endpoints/{path.name}') for path in sorted((output / 'endpoints').glob('*.json'))]
    entry = selection['selected']
    directory = next(e for e in manifest['files'] if e['path'] == 'raw/config/versiondataconfig.js')
    lines = ['# 大橘大利时间卡片官方资料采集报告', '',
             f"- 采集完成（北京时间）：{manifest['collected_at']}",
             f"- 版本目录：{DIRECTORY_URL}（HTTP {directory.get('status')}，ETag {directory.get('etag')}，"
             f"Last-Modified {directory.get('last_modified')}，{directory['size']} 字节）", '',
             '## 分支选择', '',
             f"- 规则：{selection['rule']}",
             f"- 匹配 mode={selection['mode']}、season={selection['season']} 的条目共 {len(selection['candidates'])} 条：" +
             '；'.join(f"{c['version']}（start {c.get('version_start_time')}，is_newest_version={c.get('is_newest_version')}，name={c.get('name')}）"
                      for c in selection['candidates']),
             f"- 选中：version={entry['version']}，cardurl={entry['cardurl']}",
             f"- 同 mode 的其他 season（未采用）：{', '.join(selection['same_mode_other_seasons'])}", '',
             '## 官方接口', '', '| 字段 | HTTP | 尝试 | version | season | setId | time | 记录数 | ETag | Last-Modified | 解析 |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for e in endpoints:
        top = e.get('top_level') or {}
        lines.append(f"| {e['field']} | {e.get('status')} | {e.get('attempts')} | {md(top.get('version'))} | {md(top.get('season'))} | "
                     f"{md(top.get('setId'))} | {md(top.get('time'))} | {e.get('record_count')} | {md(e.get('etag'))} | "
                     f"{md(e.get('last_modified'))} | {'失败：' + md(e.get('error') or e.get('parse_error')) if e.get('error') or e.get('parse_error') else 'JSON'} |")
    current, baseline = diff['current'], diff.get('baseline')
    tiers = {}
    for card in normalized['cards'].values():
        tiers[card['raw'].get('iRarityTier')] = tiers.get(card['raw'].get('iRarityTier'), 0) + 1
    lines += ['', '## 卡片数量', '',
              f"- 本次：{current['count']} 张，version={current['version']}，time={current['time']}；星级分布 " +
              '、'.join(f'{k} 星 {tiers[k]}' for k in sorted(tiers)),
              f"- 对比快照：{baseline['count']} 张，version={baseline['version']}，time={baseline['time']}" if baseline else '- 无对比快照',
              f"- 新增 {len(diff.get('added', []))}，删除 {len(diff.get('removed', []))}，保留 {diff.get('retained')}，"
              f"字段有变化 {sum(bool(c['fields']) for c in diff.get('changed', {}).values())}",
              f"- 卡片未知字段：{sorted({f for c in normalized['cards'].values() for f in c['unknown_fields']}) or '无'}；"
              f"结构问题：{len(normalized['problems'])}；顶层未知字段：{list(normalized['unknown_top_level']) or '无'}"]
    for item in diff.get('added', []):
        card = item['card']
        lines.append(f"- 新增 `{item['id']}` {md(card.get('sName'))}（{card.get('iRarityTier')} 星，sTags `{md(card.get('sTags'))}`，"
                     f"sArgs `{md(card.get('sArgs'))}`）：{md(card.get('sDesc'))}")
    for item in diff.get('removed', []):
        lines.append(f"- 删除 `{item['id']}` {md(item['card'].get('sName'))}")
    lines += ['', '## 元数据变化（与卡片内容分开统计）', '']
    lines += [f"- {key}：{md(v['old'])} → {md(v['new'])}" for key, v in diff.get('metadata_changes', {}).items()] or ['- 无']
    changed = diff.get('changed', {})
    field_counts = {}
    for c in changed.values():
        for field in c['fields']:
            field_counts[field] = field_counts.get(field, 0) + 1
    lines += ['', '## 字段变化统计', '', '| 字段 | 变化卡片数 |', '| --- | --- |']
    lines += [f'| {k} | {v} |' for k, v in sorted(field_counts.items())]
    round_rows, value_rows, other_rows = [], [], []
    for key, c in changed.items():
        params = c['fields'].get('sArgs', {}).get('params', {})
        for name, v in params.items():
            row = f"| `{key}` | {md(c['name'])} | {md(name)} | {md(v['old']) if v['old'] is not None else '（无）'} | {md(v['new']) if v['new'] is not None else '（无）'} |"
            (round_rows if re.fullmatch(r'round\d*', name) else value_rows).append(row)
        if c['fields'].get('sArgs', {}).get('order_only'):
            other_rows.append(f"- `{key}` {md(c['name'])}：sArgs 仅参数顺序变化")
    head = ['| ID | 名称 | 参数 | 旧值 | 新值 |', '| --- | --- | --- | --- | --- |']
    lines += ['', f"## 生效回合变化（round / round2；{len({r.split('|')[1] for r in round_rows})} 张卡）", ''] + (head + round_rows if round_rows else ['- 无'])
    lines += ['', f"## 其他参数变化（{len(value_rows)} 项）", '', '参数含义除回合外均为根据描述的推断；此处仅列原文数值。', ''] + (head + value_rows if value_rows else ['- 无'])
    lines += other_rows
    kinds = {}
    for c in changed.values():
        for kind in c['fields'].get('sDesc', {}).get('kinds', []):
            kinds[kind] = kinds.get(kind, 0) + 1
    labels = {'punctuation_or_whitespace_only': '仅标点/空白', 'numbers_changed': '数字变化', 'wording_changed': '措辞变化'}
    lines += ['', '## 描述（sDesc）变化分类', '', '一张卡可同时属于“数字变化”和“措辞变化”；分类为机械比较，不代表加强或削弱。', '']
    lines += [f'- {labels[k]}：{v} 张' for k, v in kinds.items()] or ['- 无']
    for field, label in (('sName', '名称'), ('iRarityTier', '星级'), ('sTags', '标签'), ('sIcon', '图片 URL')):
        rows = [f"- `{key}`：{md(c['fields'][field]['old'])} → {md(c['fields'][field]['new'])}" for key, c in changed.items() if field in c['fields']]
        lines += ['', f'## {label}变化', ''] + (rows or ['- 无'])
    lines += ['', '## 描述原文变化（逐张）', '']
    for key, c in changed.items():
        d = c['fields'].get('sDesc')
        if d:
            lines += [f"- `{key}` {md(c['name'])}（{'、'.join(labels[k] for k in d['kinds'])}）", f"  - 旧：{md(d['old'])}", f"  - 新：{md(d['new'])}"]
    statuses = {}
    for key, c in changed.items():
        statuses.setdefault(c['image']['status'], []).append(key)
    ok = [r for r in images.values() if not r.get('error')]
    sizes = {}
    for r in ok:
        sizes[f"{r['width']}×{r['height']}"] = sizes.get(f"{r['width']}×{r['height']}", 0) + 1
    lines += ['', '## 图片', '',
              f"- 按 sIcon 逐条下载：成功 {len(ok)}，失败 {len(images) - len(ok)}；格式 {sorted({r['format'] for r in ok})}；尺寸 " +
              '、'.join(f'{k} {v}' for k, v in sorted(sizes.items())),
              f"- 与旧本地图逐字节一致：{sum(1 for k in images if k not in changed or changed[k]['image']['status'] == 'same_bytes') - len(diff.get('added', []))} 张"]
    for status, label in (('same_pixels_different_bytes', '字节不同但像素一致'), ('content_changed', '图片内容变化'),
                          ('no_baseline_image', '旧快照无本地图（本次下载成功）'), ('download_failed', '本次下载失败')):
        if statuses.get(status):
            lines.append(f"- {label}：{', '.join('`' + k + '`' for k in statuses[status])}")
    lines += ['', '### 下载失败清单', '']
    lines += [f"- `{r['card_id']}`：{r.get('url')} → {r.get('error')}（HTTP {r.get('status')}，{r.get('downloaded_at')}，尝试 {r.get('attempts')} 次）"
              for r in images.values() if r.get('error')] or ['- 无']
    lines += ['', '## 来源划分', '',
              '- 来自本次腾讯官方响应：版本目录与分支条目、各接口的 HTTP 状态/头/内容、卡片全部字段、图片字节与尺寸、404 与超时记录。',
              '- 来自本地历史资料：对比基准 `baseline/cards.json` 与 `baseline/images/`（上一版站内快照及当时下载的图片，本次未重新核验其来源）。',
              '- 推断：sTags 分类含义、除 round/round2 以外的参数语义、描述变化的机械分类；能量字段官方未提供，记为 null。',
              '', '## 尚不能确认', '',
              '- 404 的图片何时上传、上传后是否沿用现有 URL；需再次采集核对。',
              '- sTags 第二段与参数名没有官方字典；detail 引用编号的指向没有官方说明。',
              '- 卡片能量：已采集接口中均无可关联卡片 ID 的能量字段；未列入版本目录的接口未检查。',
              '', '本脚本只写入归档目录，不修改网站资料，也不发布。']
    (output / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='new, empty archive directory')
    parser.add_argument('--report-only', action='store_true', help='regenerate report.md for an existing archive')
    parser.add_argument('--retry-images', action='store_true', help='retry timeout/network image failures in an existing archive')
    parser.add_argument('--mode', default='16')
    parser.add_argument('--season', default='S400001')
    parser.add_argument('--baseline', type=Path, default=ROOT / 'static/tools/orange-fortune/cards.json')
    parser.add_argument('--baseline-images', type=Path, default=ROOT / 'static/tools/orange-fortune/images')
    parser.add_argument('--timeout', type=float, default=20)
    parser.add_argument('--attempts', type=int, default=3)
    parser.add_argument('--workers', type=int, default=4)
    options = parser.parse_args()
    if options.report_only or options.retry_images:
        if options.retry_images:
            retry_images(options.output, options.baseline, options.baseline_images, options.timeout, max(1, options.attempts))
        write_report(options.output)
        sys.exit(0)
    if options.output.exists() and any(options.output.iterdir()):
        sys.exit(f'{options.output} is not empty; use a new archive directory.')
    options.output.mkdir(parents=True, exist_ok=True)
    summary, diff = collect(options.output, options.mode, options.season, options.baseline,
                            options.baseline_images, options.timeout, max(1, options.attempts), max(1, options.workers))
    write_report(options.output)
    print(json.dumps({**summary, 'added': len(diff.get('added', [])), 'removed': len(diff.get('removed', [])),
                      'changed': len(diff.get('changed', {}))}, ensure_ascii=False, indent=2))
