
from pathlib import Path

from PIL import Image

from scripts.build_simulator_webp_images import build_simulator_webp_images, to_webp_image_path


def test_to_webp_image_path_preserves_tree_with_webp_extension():
    source_root = Path('static/tools/lineup-simulator')
    output_root = source_root / 'webp'
    image_path = source_root / 'mode17s18_hero_by_cost_cn' / 'price-4' / '???.png'

    result = to_webp_image_path(image_path, source_root, output_root)

    assert result == output_root / 'mode17s18_hero_by_cost_cn' / 'price-4' / '???.webp'


def test_build_simulator_webp_images_creates_96px_webp(tmp_path):
    source_root = tmp_path / 'simulator'
    image_path = source_root / 'heroes' / 'morgana.png'
    output_root = source_root / 'webp'
    image_path.parent.mkdir(parents=True)
    Image.new('RGBA', (96, 96), (120, 80, 200, 255)).save(image_path)

    written = build_simulator_webp_images(source_root, output_root, [image_path], quality=82)

    assert written == [output_root / 'heroes' / 'morgana.webp']
    with Image.open(written[0]) as image:
        assert image.size == (96, 96)
        assert image.format == 'WEBP'
