"""Shared navigation catalog for the public toolbox and notice editor.

Register new tools here. Set visible=False to remove an entry from both menus;
feature-gated tools additionally follow their existing application setting.
"""
from db import get_db
from settings_service import get_setting


TOOLBOX_TOOLS = (
    dict(id='lineup-simulator', title='阵容模拟器', description='搭配弈子、装备与羁绊 · 通用工具', group='', setting='simulator_enabled'),
    dict(id='orange-fortune', title='时间卡片图鉴', description='五大品阶 · 传送门规则 · 完整效果', group='英雄联盟传奇大橘大利'),
    dict(id='orange-fortune-creator', title='大橘大利创作者工具', description='三卡构筑 · 传送门校验 · 3:4 海报', group='英雄联盟传奇大橘大利'),
    dict(id='s18-trait-ladder', title='羁绊天梯计算器', description='多羁绊阵容搜索 · 转职与阶段奖励', group='S18 · 当季工具'),
    dict(id='s18-witch-rewards', title='魔女层数奖励查询', description='9 档层数 · 概率、星级与预计价值', group='S18 · 当季工具'),
    dict(id='golden-egg', title='金蛋奖励', description='海克斯奖励一览 · 概率与物品数量', group='S18 · 当季工具'),
    dict(id='s16-5-lucky-openings', title='S16.5 恭喜发财开局推荐', description='九位五费弈子 · 专属效果与阵容码', group='S16.5 · 恭喜发财', aria_label='S16.5恭喜发财开局阵容码推荐'),
    dict(id='s11-artifacts', title='全神器装备推荐', description='31 件神器 · 装备效果与推荐弈子', group='S11 · 画之灵'),
    dict(id='s11-items', title='全弈子推荐出装', description='60 位弈子 · 推荐、备选与装备合成', group='S11 · 画之灵'),
)


def list_toolbox_tools(db=None):
    db = db if db is not None else get_db()
    return [dict(tool, url='/tools/' + tool['id']) for tool in TOOLBOX_TOOLS
            if tool.get('visible', True)
            and (not tool.get('setting') or get_setting(db, tool['setting'], 'true') == 'true')]


def tool_for_url(url, db=None):
    return next((tool for tool in list_toolbox_tools(db) if tool['url'] == url), None)
