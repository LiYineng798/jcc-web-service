import argparse
import json
import sys
import urllib.request
from urllib.error import HTTPError, URLError


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Upload live comps JSON to JCC server.')
    parser.add_argument('--file', required=True, help='Path to team_codes_by_tier.verify.json')
    parser.add_argument('--url', required=True, help='Upload endpoint URL')
    parser.add_argument('--token', required=True, help='Upload token sent via X-Upload-Token')
    parser.add_argument('--timeout', type=int, default=180, help='Upload timeout in seconds')
    return parser.parse_args(argv)


def upload_payload(file_path, url, token, timeout=180, opener=urllib.request.urlopen):
    with open(file_path, 'r', encoding='utf-8') as file:
        payload = json.load(file)
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=body,
        method='POST',
        headers={
            'Content-Type': 'application/json',
            'X-Upload-Token': token,
        },
    )
    with opener(request, timeout=timeout) as response:
        return response.read().decode('utf-8')


def main(argv=None, opener=urllib.request.urlopen):
    args = parse_args(argv)
    try:
        print(upload_payload(args.file, args.url, args.token, timeout=args.timeout, opener=opener))
        return 0
    except HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        print(f'upload failed: HTTP {exc.code} {detail}', file=sys.stderr)
        return 1
    except URLError as exc:
        print(f'upload failed: {exc}', file=sys.stderr)
        return 1
    except Exception as exc:
        print(f'upload failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
