import json
import secrets
from pathlib import Path

from flask import Blueprint, current_app, jsonify, session, url_for, request

captcha_bp = Blueprint('captcha', __name__)


def _manifest_path():
    return Path(current_app.root_path) / 'captcha_manifest.json'


def load_manifest():
    with _manifest_path().open('r', encoding='utf-8-sig') as handle:
        return json.load(handle)


def create_challenge():
    manifest = load_manifest()
    image_name = secrets.choice(list(manifest.keys()))
    token = secrets.token_urlsafe(24)
    challenges = session.setdefault('captcha_challenges', {})
    challenges[token] = {
        'image': image_name,
        'answer': manifest[image_name].lower(),
        'verified': False,
    }
    if current_app.config.get('TESTING'):
        current_app.config.setdefault('TEST_CAPTCHA_ANSWERS', {})[token] = manifest[image_name]
    session.modified = True
    return token, image_name


def verify_captcha_answer(token, answer, consume=False):
    challenges = session.get('captcha_challenges', {})
    challenge = challenges.get(token)
    if not challenge:
        return False
    ok = str(answer or '').strip().lower() == challenge['answer']
    if ok:
        challenge['verified'] = True
        if consume:
            challenges.pop(token, None)
        session.modified = True
    return ok


def is_captcha_verified(token):
    return bool(session.get('captcha_challenges', {}).get(token, {}).get('verified'))


def lookup_answer_for_tests(token):
    if not current_app.config.get('TESTING'):
        raise RuntimeError('test helper only')
    return current_app.config.get('TEST_CAPTCHA_ANSWERS', {}).get(token)


@captcha_bp.get('/api/captcha')
def captcha_challenge():
    token, image_name = create_challenge()
    return jsonify({
        'captcha_token': token,
        'image_url': url_for('static', filename=f'captcha/{image_name}'),
    })


@captcha_bp.post('/api/captcha/verify')
def captcha_verify():
    data = request.get_json(silent=True) or {}
    ok = verify_captcha_answer(data.get('captcha_token'), data.get('captcha_answer'))
    if not ok:
        return jsonify({'error': '验证码错误'}), 400
    return jsonify({'ok': True})


