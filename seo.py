import html
import re
from urllib.parse import urljoin

from flask import request

from seasons import season_catalog

SITE_NAME = '金铲铲阵容库'
DEFAULT_TITLE = '金铲铲阵容库 - 实时阵容排行与阵容码分享'
DEFAULT_DESCRIPTION = '金铲铲阵容库收录金铲铲之战阵容码、实时阵容排行、赛季阵容搜索和玩家分享阵容，支持复制、收藏、点赞和查看更新公告。'
DEFAULT_IMAGE_PATH = '/static/favicon.png'
INDEX_ROBOTS = 'index, follow'
NOINDEX_ROBOTS = 'noindex, nofollow'


def absolute_url(path):
    selected_path = path or request.path or '/'
    if selected_path.startswith('http://') or selected_path.startswith('https://'):
        return selected_path
    return urljoin(request.url_root, selected_path.lstrip('/'))


def truncate_text(value, max_length=155):
    plain = re.sub(r'\s+', ' ', str(value or '')).strip()
    if len(plain) <= max_length:
        return plain
    return plain[:max(0, max_length - 3)].rstrip() + '...'


def code_preview(code, max_length=11):
    text = str(code or '').strip()
    if len(text) <= max_length:
        return text
    return text[:max_length] + '...'


def season_label(season_id):
    for season in season_catalog():
        if season['id'] == season_id:
            return season['name']
    return str(season_id or '')


def make_seo(title=None, description=None, path=None, noindex=False, og_type='website', image_path=DEFAULT_IMAGE_PATH, json_ld=None):
    selected_title = title or DEFAULT_TITLE
    selected_description = truncate_text(description or DEFAULT_DESCRIPTION)
    canonical_url = absolute_url(path)
    return {
        'title': selected_title,
        'description': selected_description,
        'canonical_url': canonical_url,
        'robots': NOINDEX_ROBOTS if noindex else INDEX_ROBOTS,
        'noindex': bool(noindex),
        'og_type': og_type,
        'og_image': absolute_url(image_path),
        'site_name': SITE_NAME,
        'json_ld': list(json_ld or []),
    }


def website_json_ld():
    return {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        'name': SITE_NAME,
        'url': absolute_url('/'),
        'description': DEFAULT_DESCRIPTION,
    }


def breadcrumb_json_ld(items):
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {
                '@type': 'ListItem',
                'position': index + 1,
                'name': item['name'],
                'item': absolute_url(item['path']),
            }
            for index, item in enumerate(items)
        ],
    }


def webpage_json_ld(name, description, path):
    return {
        '@context': 'https://schema.org',
        '@type': 'WebPage',
        'name': name,
        'description': truncate_text(description),
        'url': absolute_url(path),
    }


def article_json_ld(note, path):
    return {
        '@context': 'https://schema.org',
        '@type': 'Article',
        'headline': note['title'],
        'description': truncate_text(note.get('summary_markdown') or note['title']),
        'datePublished': note['published_at'],
        'dateModified': note.get('updated_at') or note['published_at'],
        'url': absolute_url(path),
    }


def xml_escape(value):
    return html.escape(str(value or ''), quote=True)
