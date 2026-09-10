"""Resolve one immutable data release per request; preserve bundled-data fallback."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from flask import abort, current_app, g, has_app_context, has_request_context, request

BASE_ROOT = Path(__file__).resolve().parent / 'static/season-data'


def package_root():
    return Path(current_app.config['SEASON_PACKAGE_ROOT'])


def release_root(release_id):
    from season_package_format import ID

    if not isinstance(release_id, str) or not ID.fullmatch(release_id):
        abort(404)
    return package_root() / 'releases' / release_id


def baseline_catalog():
    return json.loads((BASE_ROOT / 'catalog.json').read_text(encoding='utf-8'))['seasons']


def _selection():
    if not has_app_context():
        return {}
    if '_season_selections' not in g:
        from db import get_db

        g._season_selections = {
            r['season_id']: dict(r)
            for r in get_db()
            .execute(
                '''
            SELECT a.season_id,a.release_id,p.manifest_json FROM season_active_releases a
            JOIN season_release_packages p ON p.id=a.release_id'''
            )
            .fetchall()
        }
        if has_request_context() and request.args.get('preview_release'):
            from auth import admin_required

            _, error = admin_required()
            if error:
                abort(error[1])
            release = (
                get_db()
                .execute(
                    'SELECT * FROM season_release_packages WHERE id=? AND state=?',
                    (request.args['preview_release'], 'ready'),
                )
                .fetchone()
            )
            if not release:
                abort(404)
            g.season_preview_id = release['id']
            g._season_selections[release['season_id']] = {
                'release_id': release['id'],
                'manifest_json': release['manifest_json'],
            }
    return g._season_selections


def selected_release(season_id):
    return _selection().get(season_id, {}).get('release_id')


def data_directory(season_id):
    selected = selected_release(season_id)
    return release_root(selected) / 'data' if selected else BASE_ROOT / season_id


def asset_url(season_id):
    selected = selected_release(season_id)
    return f'/season-assets/{selected}' if selected else f'/static/season-data/{season_id}'


def data_url(season_id):
    return asset_url(season_id) + ('/data' if selected_release(season_id) else '')


def catalog(bundled=None):
    result = []
    for entry in bundled if bundled is not None else baseline_catalog():
        sid = entry['season_id']
        selected = selected_release(sid)
        if selected:
            updated = json.loads((data_directory(sid) / 'season.json').read_text(encoding='utf-8'))
            # A package never changes ordering, visibility or canonical season identity.
            entry = {
                **entry,
                **{
                    k: updated[k]
                    for k in ('game_version', 'version_id', 'effective_at', 'counts')
                    if k in updated
                },
            }
        result.append(
            {
                **entry,
                'release_id': selected,
                'data_root': data_url(sid),
                'asset_root': asset_url(sid),
            }
        )
    return result


def preview_suffix():
    if not has_request_context() or not request.args.get('preview_release'):
        return ''
    _selection()
    value = g.get('season_preview_id') if has_app_context() else None
    return '?' + urlencode({'preview_release': value}) if value else ''


def clear_request_selection():
    if has_app_context():
        g.pop('_season_selections', None)
