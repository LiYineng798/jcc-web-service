"""Presentation geometry derived from the selected release's own image, never its URL.

R2 short portraits and official square cards both use layout=icon. Do not change
that package enum or substitute baseline art into a published/preview release.
"""
from PIL import Image, UnidentifiedImageError


def presentation(path):
    fallback = {'framed': False, 'art_style': ''}
    try:
        with Image.open(path) as image:
            if image.width != image.height or image.width < 256:
                return fallback
            bounds = image.convert('RGBA').getchannel('A').point(lambda alpha: 255 if alpha > 16 else 0).getbbox()
            if not bounds:
                return fallback
            x, y, right, bottom = bounds
            width, height = right - x, bottom - y
            if not 1.4 < height / width < 1.9:
                return fallback
            # Two source pixels preserve the faint antialiasing around the official rim.
            padding = image.width / 256
            x, y, width, height = x - padding, y - padding, width + 2 * padding, height + 2 * padding
            # Every surface uses a 5:8 stage (100 x 160 width units). Official tiers share
            # one card body width; only higher tiers add a gem above it. Scaling by width and
            # standing every card on the same baseline keeps bodies, ribbons and plinths
            # aligned across tiers. Unusually tall silhouettes fall back to fitting the height.
            scale = min(96 / width, 158 / height)
            top = 159 - height * scale
            values = {'art-width': image.width * scale,
                      'art-left': (100 - width * scale) / 2 - x * scale,
                      'art-top': (top - y * scale) / 1.6,
                      'ribbon-top': (top + (image.height * 341 / 512 - y) * scale) / 1.6,
                      'seal-top': (top + (image.height * 405 / 512 - y) * scale) / 1.6}
            return {'framed': True,
                    'art_style': ';'.join(f'--{key}:{value:.4f}%' for key, value in values.items())}
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return fallback
