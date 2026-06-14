import re

LINEUP_CODE_MESSAGE = '阵容码无法解析，请改成以 # 开头的阵容码后再提交'
LINEUP_CODE_PATTERN = re.compile(r'[＃#]([A-Za-z0-9]+)')


def extract_lineup_code(raw_code):
    matches = LINEUP_CODE_PATTERN.findall(str(raw_code or ''))
    if not matches:
        return None
    return f'#{max(matches, key=len)}'
