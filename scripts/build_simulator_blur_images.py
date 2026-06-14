"""Build 16x16 blur placeholder images for the lineup simulator."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = ROOT / 'static' / 'tools' / 'lineup-simulator'
DEFAULT_OUTPUT_ROOT = DEFAULT_SOURCE_ROOT / 'blur'
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp'}
DEFAULT_INCLUDE_DIRS = (
    'mode17s18_hero_by_cost_cn',
    'mode17s18_equip_by_type',
    'mode17s18_trait_icons',
    'assets/pets',
    'webp',
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


def build_blur_image_path(image_path: str | Path, source_root: str | Path, output_root: str | Path) -> Path:
    source = Path(image_path)
    relative_path = source.relative_to(Path(source_root))
    return Path(output_root) / relative_path


def build_one_blur_image(image_path: str | Path, target_path: str | Path, size: int = 16) -> Path:
    source = Path(image_path)
    target = Path(target_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(source) as image:
        blurred = image.convert('RGBA')
        blurred.thumbnail((size, size), Image.Resampling.LANCZOS)
        canvas = Image.new('RGBA', (size, size), (255, 255, 255, 0))
        left = (size - blurred.width) // 2
        top = (size - blurred.height) // 2
        canvas.alpha_composite(blurred, (left, top))
        canvas = canvas.filter(ImageFilter.GaussianBlur(radius=1.2))
        canvas.save(target, optimize=True)
    return target


def build_simulator_blur_images(
    source_root: str | Path = DEFAULT_SOURCE_ROOT,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    image_paths: Iterable[str | Path] | None = None,
    size: int = 16,
) -> list[Path]:
    source = Path(source_root)
    output = Path(output_root)
    paths = list(image_paths) if image_paths is not None else iter_source_images(source)

    written: list[Path] = []
    for image_path in paths:
        target = build_blur_image_path(image_path, source, output)
        written.append(build_one_blur_image(image_path, target, size=size))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description='??????? 16x16 ?????')
    parser.add_argument('--source-root', default=str(DEFAULT_SOURCE_ROOT), help='???????????')
    parser.add_argument('--output-root', default=str(DEFAULT_OUTPUT_ROOT), help='???????')
    parser.add_argument('--size', type=int, default=16, help='???????? 16')
    args = parser.parse_args()

    written = build_simulator_blur_images(args.source_root, args.output_root, size=args.size)
    print(f'??? {len(written)} ????????????{args.output_root}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
