
from pathlib import Path

from PIL import Image

from scripts.build_simulator_blur_images import build_blur_image_path, build_simulator_blur_images


def test_build_blur_image_path_preserves_relative_tree():
    source_root = Path('static/tools/lineup-simulator')
    output_root = source_root / 'blur'
    image_path = source_root / 'mode17s18_hero_by_cost_cn' / 'price-4' / '???.png'

    result = build_blur_image_path(image_path, source_root, output_root)

    assert result == output_root / 'mode17s18_hero_by_cost_cn' / 'price-4' / '???.png'


def test_build_simulator_blur_images_creates_16px_png(tmp_path):
    source_root = tmp_path / 'simulator'
    image_path = source_root / 'heroes' / 'morgana.png'
    output_root = source_root / 'blur'
    image_path.parent.mkdir(parents=True)
    Image.new('RGBA', (96, 96), (120, 80, 200, 255)).save(image_path)

    written = build_simulator_blur_images(source_root, output_root, [image_path], size=16)

    assert written == [output_root / 'heroes' / 'morgana.png']
    with Image.open(written[0]) as image:
        assert image.size == (16, 16)
        assert image.mode == 'RGBA'
