from flask import has_request_context, request

DEVICE_LABELS = {'mobile': '手机', 'tablet': '平板', 'desktop': '电脑', 'unknown': '未知设备'}


def request_device_type():
    """Coarse UA categories only; no raw UA or fingerprint is stored."""
    if not has_request_context():
        return 'unknown'
    ua = (request.user_agent.string or '').lower()
    if not ua:
        return 'unknown'
    if 'ipad' in ua or ('macintosh' in ua and 'mobile/' in ua) or ('android' in ua and 'mobile' not in ua) or 'tablet' in ua:
        return 'tablet'
    if any(marker in ua for marker in ('iphone', 'ipod', 'android', 'windows phone', 'mobi')):
        return 'mobile'
    if any(marker in ua for marker in ('windows nt', 'macintosh', 'x11', 'cros')):
        return 'desktop'
    return 'unknown'
