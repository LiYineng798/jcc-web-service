from flask import Flask

from route_response import respond_service_result


def test_respond_service_result_returns_json_payload():
    app = Flask(__name__)
    with app.app_context():
        response = respond_service_result({'ok': True}, None, 200)
    assert response[1] == 200
    assert response[0].get_json() == {'ok': True}


def test_respond_service_result_returns_error_payload():
    app = Flask(__name__)
    with app.app_context():
        response = respond_service_result(None, '失败', 403)
    assert response[1] == 403
    assert response[0].get_json() == {'error': '失败'}


def test_respond_service_result_returns_empty_response_for_no_content():
    response = respond_service_result(None, None, 204)
    assert response[1] == 204
    assert response[0] == ''
