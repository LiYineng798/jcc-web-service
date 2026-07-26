"""Static asset versioning for cache busting.

`static_v('app.js')` renders `/static/app.js?v=<stamp>` where the stamp is the
newest mtime among the site's top-level JS/CSS files (and static/admin/),
computed once per process. A deploy (`git pull`) refreshes the mtimes, so
long-lived `Cache-Control: immutable` headers on /static stay safe without a
manual version constant.
"""

from pathlib import Path

from flask import url_for

STATIC_ROOT = Path(__file__).resolve().parent / 'static'

_stamp = None


def asset_stamp():
    global _stamp
    if _stamp is None:
        newest = 0
        for pattern in ('*.js', '*.css', 'admin/*.js', 'vendor/lucide/*.js'):
            for path in STATIC_ROOT.glob(pattern):
                newest = max(newest, int(path.stat().st_mtime))
        _stamp = str(newest or 0)
    return _stamp


def static_v(filename):
    return f"{url_for('static', filename=filename)}?v={asset_stamp()}"


def register_asset_helpers(app):
    app.add_template_global(static_v, name='static_v')
