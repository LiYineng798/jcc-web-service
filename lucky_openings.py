"""Fixed S16.5 opening recommendations transcribed from the supplied posters.

Rules/codes are editorial content; art follows the current public library release.
Do not import these recommendations into user lineups or alter copy rankings.
"""
import re

from lineup_code import extract_lineup_code
from season_data_repository import asset_url
from season_reference_service import champion_summaries, get_season_entry

SEASON_ID = 's16_5'

OPENINGS = (
    {
        'name': '阿兹尔开局',
        'champion_ids': ('5290',),
        'headline': '黄沙不灭 财源不息',
        'effect': (
            '在玩家对战回合中，战斗开始时在场上的2个沙兵，任意1个存活超过15秒，掉落1金币；'
            '战斗结束时2个都存活，阿兹尔额外永久获得4%法术强度。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA0ODUyMjYz',
    },
    {
        'name': '稻草人开局',
        'champion_ids': ('5287',),
        'headline': '群鸦掠野 枯木春发',
        'effect': (
            '在玩家对战回合中，费德提克每4次参与击败，获得1经验值；'
            '回合内达成2次击败，永久获得2%增伤。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA0OTQxNDcy',
    },
    {
        'name': '卢锡安开局',
        'champion_ids': ('5398', '5397'),
        'headline': '光影交替 金落法凝',
        'effect': (
            '在玩家对战回合中，卢锡安和赛娜每3次置换，掉落1金币并永久降低2点最大法力值'
            '（上限30点）。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MDI4Nzkw',
    },
    {
        'name': '希瓦娜开局',
        'champion_ids': ('5278',),
        'headline': '龙鳞铸金甲 一怒山河裂',
        'effect': (
            '在玩家对战回合中，希瓦娜每5次击败获得1金币；'
            '存活超过18秒，永久获得2%伤害加成和1%生命汲取。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MTA4MTQx',
    },
    {
        'name': '基兰开局',
        'champion_ids': ('5270',),
        'headline': '钟表滴答走 杀意不曾休',
        'effect': (
            '在玩家对战回合中，基兰每次完成击败都会获得永久叠加的1%法术加成，'
            '每完成5次斩杀，还会获得1法力回复。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MjMyMDU2',
    },
    {
        'name': '安妮开局',
        'champion_ids': ('5292',),
        'headline': '杀敌饲熊 承伤换金',
        'effect': (
            '在玩家对战回合中，安妮每完成1次击杀，提伯斯获得永久50点生命值。'
            '提伯斯在首次承受30次伤害时，掉落1金币。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1MzE2NDMz',
    },
    {
        'name': '千珏开局',
        'champion_ids': ('5284',),
        'headline': '狼魂未泯 羊佑禄长',
        'effect': (
            '在玩家对战回合中，在战斗结束时千珏存活，永久获得3%攻击速度，'
            '所有存活的队友15%概率掉落1金币。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1NDM5Nzkx',
    },
    {
        'name': '杰斯开局',
        'champion_ids': ('5402',),
        'headline': '前阵分兵甲 后排斩将金',
        'effect': (
            '在玩家对战回合中，杰斯在前2排时与最近2名友军额外分享1件随机装备，'
            '在后2排时达成2次击败获得1金币。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1NTIwMjQz',
    },
    {
        'name': '奥恩开局',
        'champion_ids': ('5281',),
        'headline': '身上无闲铁 手中淬乾坤',
        'effect': (
            '在玩家对战回合中，战斗开始时场上友军穿戴的每件神器装备为奥恩提供永久的1护甲和魔抗；'
            '奥恩携带时每件额外提供1护甲和魔抗。'
        ),
        'code': 'MjIwMDM1MDM4MDY5NTE2NjYxNzg4OTA1NTY2OTg4',
    },
)


def build_lucky_openings():
    season = get_season_entry(SEASON_ID)
    champions = {c['id']: c for c in champion_summaries(SEASON_ID)}
    root = asset_url(SEASON_ID) if season else ''
    version = season.get('version_id', '') if season else ''
    cards = []
    for opening in OPENINGS:
        champion = next((champions[cid] for cid in opening['champion_ids'] if cid in champions), {})
        path = champion.get('card') or champion.get('splash') or champion.get('icon')
        effect = opening['effect'].removeprefix('在玩家对战回合中，')
        cards.append({
            **opening,
            'champion_name': champion.get('name') or opening['name'].removesuffix('开局'),
            'copy_code': extract_lineup_code(f"【阵容码】#{opening['name']}#{opening['code']}"),
            'art': f'{root}/{path}?v={version}' if path else '',
            'effect_parts': [
                {'text': text, 'highlight': bool(re.fullmatch(r'\d+%?', text))}
                for text in re.split(r'(\d+%?)', effect) if text
            ],
        })
    return cards
