"""Build WebP image assets for the lineup simulator."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT / 'static' / 'tools' / 'lineup-simulator'
DEFAULT_OUTPUT_ROOT = DEFAULT_SOURCE_ROOT / 'webp'
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg'}
DEFAULT_INCLUDE_DIRS = (
    'mode17s18_hero_by_cost_cn',
    'mode17s18_equip_by_type',
    'mode17s18_trait_icons',
    'assets/pets',
)


def iter_source_images(source_root: str | Path = DEFAULT_SOURCE_ROOT) -> list[Path]:
    root = Path(source_root)
    images: list[Path] = []
    for relative_dir in DEFAULT_INCLUDE_DIRS:
        directory = root / relative_dir
        if not directory.exists():
            continue
        images.extend(
            path
            for path in directory.rglob('*')
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        )
    return sorted(images)


def to_webp_image_path(image_path: str | Path, source_root: str | Path, output_root: str | Path) -> Path:
    source = Path(image_path)
    relative_path = source.relative_to(Path(source_root))
    return (Path(output_root) / relative_path).with_suffix('.webp')


def build_one_webp_image(image_path: str | Path, target_path: str | Path, quality: int = 82) -> Path:
    source = Path(image_path)
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        frame = image.convert('RGBA') if image.mode in {'P', 'LA'} else image
        frame.save(target, format='WEBP', quality=quality, method=6)
    return target


def build_simulator_webp_images(
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    image_paths: Iterable[str | Path] | None = None,
    quality: int = 82,
) -> list[Path]:
    source = Path(source_root)
    output = Path(output_root)
    paths = list(image_paths) if image_paths is not None else iter_source_images(source)

    written: list[Path] = []
    for image_path in paths:
        target = to_webp_image_path(image_path, source, output)
        written.append(build_one_webp_image(image_path, target, quality=quality))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description='??????? WebP ????')
    parser.add_argument('--source-root', default=str(DEFAULT_SOURCE_ROOT), help='????????')
    parser.add_argument('--output-root', default=str(DEFAULT_OUTPUT_ROOT), help='WebP ????')
    parser.add_argument('--quality', type=int, default=82, help='WebP ????? 82')
    args = parser.parse_args()

    written = build_simulator_webp_images(args.source_root, args.output_root, quality=args.quality)
    print(f'??? {len(written)} ? WebP ???{args.output_root}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
