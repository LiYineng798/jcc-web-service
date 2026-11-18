"""Presentation geometry derived from the selected release's own image, never its URL.

R2 short portraits and official square cards both use layout=icon. Do not change
that package enum or substitute baseline art into a published/preview release.
"""
from PIL import Image, ImageStat, UnidentifiedImageError


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
            left = (100 - width * scale) / 2 - x * scale
            at_x = lambda px: left + image.width * px / 512 * scale
            at_y = lambda px: (top + (image.height * px / 512 - y) * scale) / 1.6
            # Official template landmarks on the 512px canvas: ribbon centre, plinth centre,
            # the copy area between ribbon and notch, tier pips under the gem and the tip seal.
            values = {'art-width': image.width * scale, 'art-left': left, 'art-top': (top - y * scale) / 1.6,
                      'ribbon-top': at_y(341), 'seal-top': at_y(405),
                      'copy-top': at_y(362), 'copy-bottom': 100 - at_y(472),
                      'copy-left': at_x(150), 'copy-right': 100 - at_x(362),
                      'pips-top': at_y(134), 'tip-top': at_y(480)}
            style = ';'.join(f'--{key}:{value:.4f}%' for key, value in values.items())
            # Most plinths are pale foil; many legendary ones carry dark art. Pick the copy ink
            # from the plinth itself so either kind stays legible.
            plinth = image.convert('L').crop(tuple(round(image.width * v / 512) for v in (170, 372, 342, 440)))
            dark = ImageStat.Stat(plinth).mean[0] < 140
            return {'framed': True, 'art_style': f'{style};--face-dark:{int(dark)}'}
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError):
        return fallback
