from flask import jsonify


def respond_service_result(result, service_error, status_code):
    if service_error:
        return jsonify({'error': service_error}), status_code
    if result is None and status_code == 204:
        return '', status_code
    return jsonify(result), status_code
