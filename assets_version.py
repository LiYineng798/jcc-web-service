"""Static asset versioning for cache busting.

`static_v('app.js')` renders `/static/app.js?v=<stamp>` where the stamp is the
newest mtime among every JS/CSS file under static/, computed once per process.
A deploy (`git pull`) refreshes the mtimes, so long-lived `Cache-Control:
immutable` headers on /static stay safe without a manual version constant.
"""

from pathlib import Path

from flask import url_for

STATIC_ROOT = Path(__file__).resolve().parent / 'static'

_stamp = None
_season_data_stamp = None


def asset_stamp():
    global _stamp
    if _stamp is None:
        newest = 0
        for pattern in ('**/*.js', '**/*.css'):
            for path in STATIC_ROOT.glob(pattern):
                newest = max(newest, path.stat().st_mtime_ns)
        _stamp = str(newest or 0)
    return _stamp


def static_v(filename):
    return f"{url_for('static', filename=filename)}?v={asset_stamp()}"


def season_data_stamp():
    """Return one deploy-local version for mutable season JSON metadata."""
    global _season_data_stamp
    if _season_data_stamp is None:
        newest = 0
        season_root = STATIC_ROOT / 'season-data'
        for path in season_root.rglob('*.json'):
            newest = max(newest, path.stat().st_mtime_ns)
        _season_data_stamp = str(newest or 0)
    return _season_data_stamp


def register_asset_helpers(app):
    app.add_template_global(static_v, name='static_v')
    app.add_template_global(season_data_stamp, name='season_data_stamp')
