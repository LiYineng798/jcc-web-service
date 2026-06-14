"""Build split JSON data files for the lineup simulator."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / 'static' / 'tools' / 'lineup-simulator' / 'local-data.js'
DEFAULT_OUTPUT = ROOT / 'static' / 'tools' / 'lineup-simulator' / 'data'
REQUIRED_FIELDS = ('heroCostTabs', 'equipTabs', 'heroes', 'equips', 'traits', 'pets')


def _strip_legacy_js_assignment(text: str) -> str:
    stripped = text.strip()
    prefix = 'window.LOCAL_SIMULATOR_DATA'
    if not stripped.startswith(prefix):
        return stripped

    equals_index = stripped.find('=')
    if equals_index == -1:
        raise ValueError('local-data.js 格式不正确：找不到赋值符号 =')

    payload = stripped[equals_index + 1 :].strip()
    if payload.endswith(';'):
        payload = payload[:-1].strip()
    return payload


def _load_legacy_js_with_node(source_path: Path) -> dict[str, Any]:
    node_script = f"""
const path = require('path');
global.window = global;
require(path.resolve({json.dumps(str(source_path))}));
if (!global.LOCAL_SIMULATOR_DATA) {{
  throw new Error('LOCAL_SIMULATOR_DATA missing');
}}
process.stdout.write(JSON.stringify(global.LOCAL_SIMULATOR_DATA));
"""
    try:
        result = subprocess.run(
            ['node', '-e', node_script],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise ValueError(f'无法解析旧 JS 数据源：{source_path}，请安装 Node.js 或改用合并 JSON 源文件') from error

    data = json.loads(result.stdout)
    if not isinstance(data, dict):
        raise ValueError('旧 JS 数据源顶层必须是对象')
    return data


def load_source_data(source: str | Path) -> dict[str, Any]:
    source_path = Path(source)
    text = source_path.read_text(encoding='utf-8-sig')
    payload = _strip_legacy_js_assignment(text)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as error:
        if source_path.suffix.lower() == '.js':
            return _load_legacy_js_with_node(source_path)
        raise ValueError(f'数据源不是有效 JSON：{source_path} ({error})') from error

    if not isinstance(data, dict):
        raise ValueError('数据源顶层必须是对象')
    return data


def _validate_data(data: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise ValueError(f'缺少必需字段：{", ".join(missing)}')

    for field in REQUIRED_FIELDS:
        if not isinstance(data[field], list):
            raise ValueError(f'{field} 必须是数组')


def _version_payload(data: dict[str, Any], source: Path) -> dict[str, Any]:
    version = data.get('version')
    if isinstance(version, dict):
        payload = dict(version)
    else:
        payload = {}

    payload.setdefault('set', data.get('set', 'manual'))
    payload.setdefault('version', data.get('dataVersion', 'manual'))
    payload.setdefault('updatedAt', data.get('updatedAt', 'manual'))
    payload.setdefault('source', str(source))
    payload.setdefault('note', '由 scripts/build_simulator_data.py 自动生成')
    return payload



def _rewrite_image_to_webp(image_path: str) -> str:
    normalized = image_path.replace('\\', '/').lstrip('./')
    if normalized.startswith('webp/'):
        return str(Path(normalized).with_suffix('.webp')).replace('\\', '/')
    return f"webp/{Path(normalized).with_suffix('.webp').as_posix()}"


def _rewrite_section_images(items: list[Any], image_format: str) -> list[Any]:
    if image_format == 'source':
        return items
    if image_format != 'webp':
        raise ValueError('image_format ??? source ? webp')

    rewritten: list[Any] = []
    for item in items:
        if isinstance(item, dict) and isinstance(item.get('image'), str):
            clone = dict(item)
            clone['image'] = _rewrite_image_to_webp(clone['image'])
            rewritten.append(clone)
        else:
            rewritten.append(item)
    return rewritten

def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def build_simulator_data(
    source: str | Path = DEFAULT_SOURCE,
    output: str | Path = DEFAULT_OUTPUT,
    image_format: str = 'source',
) -> list[Path]:
    source_path = Path(source)
    output_path = Path(output)
    data = load_source_data(source_path)
    _validate_data(data)
    if image_format not in {'source', 'webp'}:
        raise ValueError('image_format ??? source ? webp')

    output_path.mkdir(parents=True, exist_ok=True)
    files = {
        'version.json': _version_payload(data, source_path),
        'tabs.json': {
            'heroCostTabs': data['heroCostTabs'],
            'equipTabs': data['equipTabs'],
        },
        'heroes.json': _rewrite_section_images(data['heroes'], image_format),
        'equips.json': _rewrite_section_images(data['equips'], image_format),
        'traits.json': _rewrite_section_images(data['traits'], image_format),
        'pets.json': _rewrite_section_images(data['pets'], image_format),
    }

    written: list[Path] = []
    for filename, value in files.items():
        target = output_path / filename
        _write_json(target, value)
        written.append(target)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description='生成阵容模拟器 JSON 数据文件')
    parser.add_argument(
        '--source',
        default=str(DEFAULT_SOURCE),
        help='源数据文件：合并 JSON 或旧 local-data.js',
    )
    parser.add_argument(
        '--output',
        default=str(DEFAULT_OUTPUT),
        help='输出目录，默认写入模拟器 data 目录',
    )
    parser.add_argument(
        '--image-format',
        choices=('source', 'webp'),
        default='source',
        help='???????source ??????webp ??? WebP ??',
    )
    args = parser.parse_args()

    written = build_simulator_data(args.source, args.output, image_format=args.image_format)
    print('已生成阵容模拟器数据：')
    for path in written:
        print(f'- {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
