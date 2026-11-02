"""Loopback-only patch note preview with fictional notes; never registered in the real app."""
import os

from serve_search_device_preview import create_preview_app

NOTES = [
    {
        'title': 'S18 魔法乱斗 18.3 版本更新公告',
        'version': '18.3',
        'published_at': '2026-10-29',
        'summary_markdown': '''本次更新重点削弱前期连胜过强的约德尔人与野兽之灵，同时补强后期法师与护卫的上限，并调整了部分装备与强化符文。
预计更新时间为 10 月 29 日 06:00—09:00，更新期间无法进入对局。

## 版本重点

强势前期体系的连胜收益下调，四费与五费核心弈子的稳定性得到增强。
新增 6 个强化符文，下线 3 个出场率过低的强化符文。

## 羁绊调整

- [nerf] 约德尔人：(3) 攻速加成 25% => 20%；(6) 攻速加成 60% => 50%
- [nerf] 野兽之灵：变身后获得的生命值 300/550/900 => 260/500/850
- [buff] 护卫：(2) 护甲与魔抗 20 => 25；(4) 护甲与魔抗 45 => 55
- [buff] 大元素使：每次施法回复法力值 10/20/35 => 12/24/40
- [adjust] 日月双蚀：日蚀骑士与月蚀骑士同时在场时，额外效果改为在战斗开始后 4 秒触发，此前为立即触发。

## 弈子调整

- [nerf] 提莫：技能伤害 260/390/585 => 240/360/540
- [nerf] 雷克塞：攻击速度 0.75 => 0.7；法力值 0/60 => 0/70
- [buff] 卡尔玛：技能伤害 180/270/420 => 200/300/460
- [buff] 维迦：每层叠加的法术强度 2 => 3
- [buff] 阿兹尔：沙兵持续时间 4秒 => 5秒；法力值 30/90 => 30/80
- [nerf] 卡西奥佩娅：毒雾伤害 85/130/400 => 80/120/360
- [adjust] 赫卡里姆：冲锋目标由“距离最远的敌人”改为“生命值最低的远程敌人”，冲锋距离不变。
- [buff] 莫甘娜：护盾值 350/475/1200 => 380/520/1300
- [nerf] 卡兹克：隔离目标额外伤害 40% => 35%

## 装备调整

- [buff] 无尽之刃：暴击率 35% => 40%
- [nerf] 汲取剑：全能吸血 20% => 18%
- [adjust] 斯特拉克的挑战护手：护盾不再随星级缩放，改为固定为最大生命值的 25%。
- [buff] 泰坦的坚决：每层提供的攻击力与法术强度 2% => 2.5%

## 强化符文

- [adjust] 新增“花园漫步”“月下双生”“荆棘王冠”等 6 个强化符文。
- [adjust] 下线“快速思考”“额外装备”“宝石盛宴”。
- [nerf] 冷静思考：每回合获得的经验值 4 => 3
- [buff] 野性呼唤：野兽之灵变身所需时间 8秒 => 6秒

## 系统与体验

- [adjust] 9 级商店概率：4 费弈子 30% => 28%；5 费弈子 15% => 17%
- [adjust] 观战界面新增羁绊悬浮提示，可直接查看对手当前已激活的羁绊。
修复了部分安卓机型在结算页面偶现黑屏的问题。
修复了“魔女”羁绊在对手复制单位时计数错误的问题。
''',
        'original_text': '''亲爱的弈士：

《金铲铲之战》将于 10 月 29 日 06:00—09:00 进行版本更新，更新期间将无法进入对局，请合理安排游戏时间。

一、版本重点
本次更新重点削弱前期连胜过强的约德尔人与野兽之灵，同时补强后期法师与护卫的上限。四费与五费核心弈子的稳定性得到增强。

二、羁绊调整
约德尔人
(3) 攻速加成：25% → 20%
(6) 攻速加成：60% → 50%
野兽之灵
变身后获得的生命值：300/550/900 → 260/500/850
护卫
(2) 护甲与魔抗：20 → 25
(4) 护甲与魔抗：45 → 55

三、弈子调整
提莫
技能伤害：260/390/585 → 240/360/540
雷克塞
攻击速度：0.75 → 0.7
法力值：0/60 → 0/70
……（以下为预览用虚构原文，仅演示长文本排版）

四、问题修复
修复了部分安卓机型在结算页面偶现黑屏的问题。
修复了“魔女”羁绊在对手复制单位时计数错误的问题。

感谢各位弈士的支持，祝大家游戏愉快！''',
    },
    {
        'title': '18.2b 平衡性热更新',
        'version': '18.2b',
        'published_at': '2026-10-16',
        'summary_markdown': '''针对上周末对局数据进行的小幅平衡调整，无需下载更新包。

## 弈子调整

- [nerf] 乐芙兰：技能伤害 300/450/700 => 280/420/650
- [nerf] 凯特琳：攻击力 60 => 55
- [buff] 瑟庄妮：护盾值 400/500/650 => 450/575/750

## 羁绊调整

- [buff] 花仙子：(3) 治疗量 15% => 18%
''',
        'original_text': '',
    },
    {
        'title': '18.2 版本更新公告：仙灵回合与新强化符文',
        'version': '18.2',
        'published_at': '2026-10-09',
        'summary_markdown': '''仙灵回合加入新的随机事件，同时上线一批与“永恒之森”相关的强化符文。

## 赛季玩法

- [adjust] 仙灵回合：新增“林间馈赠”事件，可在三个奖励中选择其一。
- [adjust] 第 4-6 回合的野怪掉落中加入成装概率。

## 弈子调整

- [buff] 阿利斯塔：冲撞眩晕时长 1.5秒 => 1.75秒
- [buff] 蕾欧娜：伤害减免 40/60/80 => 50/70/100
- [nerf] 霞：攻击速度 0.75 => 0.7
- [nerf] 崔丝塔娜：技能伤害 180/270/420 => 170/255/400

## 装备调整

- [nerf] 鬼索的狂暴之刃：每层攻速 5% => 4%
- [buff] 虚空之杖：魔抗削减 30% => 35%
''',
        'original_text': '仙灵回合加入新的随机事件……（预览用虚构原文）',
    },
    {
        'title': '国庆活动与通行证更新说明',
        'version': '',
        'published_at': '2026-09-30',
        'summary_markdown': '''国庆期间限时活动、通行证奖励与商城上新说明，本次不涉及对局平衡。

## 活动

- [adjust] 10 月 1 日—10 月 7 日每日登录可领取限定表情与 200 星钻。
- [adjust] 双人作战模式开放时间延长至每日 24 小时。

## 通行证

- [adjust] 新增 S18 通行证第二期，奖励包含小小英雄“森灵小鹿”。
''',
        'original_text': '',
    },
    {
        'title': '18.1 版本更新公告',
        'version': '18.1',
        'published_at': '2026-09-18',
        'summary_markdown': '''## 羁绊调整

- [buff] 黑荆棘：(2) 攻击力加成 15% => 18%
- [nerf] 赏金猎人：(4) 每回合额外金币 1 => 0；改为每 2 回合获得 1 金币

## 弈子调整

- [buff] 奥恩：技能护盾 300/400/550 => 350/450/600
- [nerf] 卡蜜尔：技能伤害 200/300/450 => 190/285/420
''',
        'original_text': '',
    },
    {
        'title': 'S17 星神 收官版本 17.24 更新公告',
        'version': '17.24',
        'published_at': '2026-08-20',
        'summary_markdown': '''S17 星神的最后一次平衡调整，为赛季收官做准备。

## 弈子调整

- [buff] 崔斯特：技能伤害 240/360/540 => 260/390/585
- [nerf] 金克丝：攻击速度 0.8 => 0.75
''',
        'original_text': '',
    },
    {
        'title': '17.23 版本更新公告',
        'version': '17.23',
        'published_at': '2026-07-30',
        'summary_markdown': '''## 羁绊调整

- [adjust] 幻灵战队：(5) 效果重做，具体说明见官方原文。
- [nerf] 暗星：每层黑洞伤害 8% => 6%
''',
        'original_text': '',
    },
]


def create_app():
    app = create_preview_app()
    with app.app_context():
        from db import get_db, now_text
        db = get_db()
        if not db.execute('SELECT id FROM patch_notes LIMIT 1').fetchone():
            now = now_text()
            for index, note in enumerate(reversed(NOTES)):
                db.execute(
                    '''INSERT INTO patch_notes(title,version,source_url,summary_markdown,original_text,status,published_at,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?)''',
                    (note['title'], note['version'], f'https://example.com/jcc/notice/{index + 1}', note['summary_markdown'],
                     note['original_text'], 'published', note['published_at'], now, now),
                )
            db.execute(
                '''INSERT INTO patch_notes(title,version,source_url,summary_markdown,original_text,status,published_at,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?)''',
                ('18.4 草稿（不应公开）', '18.4', '', '- [adjust] 草稿内容', '', 'draft', '2026-11-05', now, now),
            )
            db.commit()
    return app


if __name__ == '__main__':
    port = int(os.environ.get('PATCH_NOTES_PREVIEW_PORT', '5150'))
    print(f'Preview http://127.0.0.1:{port}/patch-notes; admin login /__preview__/login/admin', flush=True)
    create_app().run(host='127.0.0.1', port=port, debug=False, use_reloader=False, threaded=True)
