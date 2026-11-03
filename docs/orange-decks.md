# 大橘大利卡组库

首页的「卡组库」与「阵容库」同级，展示用户发布的三卡组合，可附带阵容站位。
URL 状态为 `/?library=decks&tab=&portal=&q=&page=`，支持直接链接、刷新与前进后退；`/` 仍是阵容库。
详情页 `/orange-decks/<id>` 服务端渲染完整内容，编辑页为 `/orange-decks/new` 与 `/orange-decks/<id>/edit`（需登录，noindex）。

## 代码入口

| 范围 | 文件 |
| --- | --- |
| 路由（身份、参数、响应） | `orange_decks.py` |
| 规则、序列化、可见性、后台操作 | `orange_deck_service.py` |
| SQLite 结构 | `orange_deck_schema.py`；PostgreSQL 为 DB 仓库 `0025_orange_decks.sql` |
| 首页列表 | `templates/index.html`、`static/orange-deck-library.js` |
| 详情 / 编辑 | `orange_deck_detail.html`、`orange_deck_form.html`、`orange_deck_macros.html`、`orange-deck-detail.js`、`orange-deck-editor.js` |
| 共用渲染 | `static/orange-deck-core.js`、`static/orange-decks.css`（与 `orange_deck_macros.html` 保持一致） |
| 后台 | `static/admin/orange-decks.js`，「内容与用户 → 卡组库」 |

## 数据与规则

`orange_decks` 与 `orange_deck_favorites` 独立于普通阵容，不进入阵容数量、评分、排行榜或实时榜单。
三张卡分列保存（`card_id_1..3`），不写入任何阵容码字段。

- 品阶、能量、传送门上限复用 `orange_fortune_service` 的 `TIERS`、`PORTALS`、`DECK_SIZE`；`energy` 由服务端按资料计算后保存。
- 公开发布（及被隐藏的已发布内容）必须三张不同且存在的卡，能量不超过所选传送门上限；草稿可缺卡、可超限。
  海报工具允许超限导出的行为不变。
- `card_version`（`版本@时间`）与 `card_snapshot_json`（每张卡保存时的名称与品阶）用于资料更新后的对比：
  卡片消失显示为“失效”，改名或改品阶逐项列出，能量按当前资料重算；不会用其他卡替换。
  含失效卡的卡组不能再保存，需由作者重新选卡；“以此为基础创建”会留空失效卡槽并提示。
- 状态：`draft`（仅作者）、`published`、`hidden`（管理员隐藏，作者与管理员可见，作者可改内容但不能自行恢复公开）、
  `deleted`（任何入口不可见）。编辑使用 `version` 乐观检查。

## 阵容站位

编辑复用创作者模拟器：`/tools/lineup-simulator?creator=orange-fortune&deck=1`（deck 模式）不读写浏览器存储，
父页面通过 `jcc:orange-formation-ready` → `jcc:orange-formation-load` → `jcc:orange-formation-load-result` 载入已保存阵容，
随后的 `jcc:orange-formation` 消息带有结构化 `payload`（与模拟器草稿同构：`board[28]{championId, items}`、`augmentIds`）。

- 服务端只接受创作者入口当前默认且公开的赛季；弈子（含 `~choice-` 选择形态）、装备、强化符文须存在于该赛季资料。
- 星级（1–3）由卡组编辑页设置并随 `board[].star` 保存；模拟器本身不处理星级，重新编辑时按弈子出现顺序保留。
- 羁绊保存模拟器计算的结果（羁绊 ID、数量、档位），名称和图标在展示时按 ID 从资料读取；资料版本变化时标注“为保存时的计算结果”。
  卡片带来的额外羁绊、变身等不自动计算，页面以固定说明标注边界。
- 创作者赛季被隐藏或切换后，旧阵容保留但不显示站位、不可在编辑器修改；作者可以移除后重新配置。
- 首页列表只在点击“展开站位”时请求 `/api/orange-decks/<id>/formation`，不为每条记录创建模拟器或 iframe。

## 列表、互动与可见性

- 搜索匹配卡组名称和所含卡片的当前名称；传送门为精确筛选。
- 热门：按收藏账号数排序（每账号 1 次，取消即扣除），只列至少被收藏 1 次的公开卡组，同数按发布时间。
- 推荐：管理员设置，按推荐时间排列；隐藏或删除会同时清除推荐。
- 收藏 POST/DELETE 幂等；只能收藏公开卡组，取消收藏总是允许。
- 同一可见性规则用于详情、站位、搜索、分享、“以此为基础创建”和导出海报；派生入口只对公开卡组或作者自己的草稿开放，
  被隐藏的内容不可分享或派生。管理员操作写入审计日志（`orange_deck.feature/unfeature/hide/restore`）。

## 分享与海报

- 复制文本包含卡组名称、三张卡名（品阶·能量）、推荐传送门、能量与详情链接；页面注明它不是游戏内可导入的卡组码。
- “导出海报”打开 `/tools/orange-fortune-creator?deck=<id>`：纯卡组进入卡组推荐版，带站位进入攻略版。
  导入只在本页编辑，不读取也不改写 `jcc-orange-creator-v1` 与 `jcc-orange-formation-v1:*`，页头提供返回原草稿的链接。
- 反向入口：创作者页“发布到卡组库”打开 `/orange-decks/new?from=creator`，只读两个草稿键；编辑页未提交的新卡组暂存在
  `jcc-orange-deck-draft-v1`，替换前会确认。图鉴卡片详情可跳转到含该卡的卡组搜索。

## 验证

`python -m pytest -q tests/test_orange_decks.py`；DB 仓库 `tests/test_orange_deck_migration.py`。
浏览器验证需覆盖首页切换/历史、站位展开、卡片弹窗、发布与超限提示、阵容 iframe 往返、海报导入不覆盖草稿和后台操作。
