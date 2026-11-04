"""Convert the collector's local official time-card archive for a season ZIP."""
import json
from pathlib import Path

from PIL import Image

from orange_fortune_service import parse_catalog
from season_package_format import PackageError, dump, require, validate_time_cards


def import_time_cards(official, payload, destination, season_id, version_id, game_version):
    official, destination = Path(official).resolve(), Path(destination).resolve()
    manifest = official / 'images/manifest.json'
    images = json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
    assets = {}
    for key in payload.get('data', {}):
        require(isinstance(key, str) and key.isdigit(), '时间卡片 ID 无效')
        record = images.get(key) or {}
        # An explicit upstream 404 may be published as missing art; transient failures must be retried.
        if record.get('error') in ('http_404', 'no_icon_url'):
            assets[key] = None
            continue
        require(record and not record.get('error'), f'时间卡片 {key} 图片未成功采集，请重试')
        path = (official / str(record.get('local_path', ''))).resolve()
        require(path.is_relative_to(official) and path.is_file(), f'时间卡片 {key} 图片路径无效')
        require(not path.is_symlink(), f'时间卡片 {key} 图片不能是符号链接')
        target = destination / 'assets/time-cards' / f'{key}.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(path) as image:
            require(getattr(image, 'n_frames', 1) == 1, '不允许动画时间卡片')
            # Re-encode archived images without fetching remote URLs or substituting older art.
            image.convert('RGBA').save(target)
            layout = 'portrait' if image.height / image.width >= 1.5 else 'icon'
        assets[key] = {'file': f'{key}.png', 'layout': layout}
    try:
        normalized = parse_catalog({**payload, 'assets': assets}, 'assets/time-cards')
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageError('官方时间卡片字段不完整或无效') from exc
    doc = {key: normalized[key] for key in ('version', 'season', 'setId', 'time')}
    doc.update(season_id=season_id, version_id=version_id,
               time_cards=[{key: card[key] for key in ('id', 'name', 'tier', 'description', 'category_id',
                                                      'round', 'rounds', 'image', 'layout', 'source')}
                           for card in normalized['cards']])
    validate_time_cards(doc, {'season_id': season_id, 'version_id': version_id, 'game_version': game_version})
    dump(destination / 'time_cards.json', doc)
    return len(doc['time_cards'])
