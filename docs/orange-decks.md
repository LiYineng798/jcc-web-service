# 大橘大利卡组库

首页的「卡组库」与「阵容库」同级，切换按钮位于两个列表面板的标题位置，展示用户发布的三卡组合，可附带阵容站位。
URL 状态为 `/?library=decks&tab=&portal=&q=&page=`，支持直接链接、刷新与前进后退；`/` 仍是阵容库。
发布与普通阵容共用 `/lineup/new`：页内按钮切换「阵容码 / 大橘大利卡组」，`?type=deck` 直接打开卡组表单，
`/orange-decks/new` 重定向至此。编辑仍按类型分开：`/lineup/<id>/edit` 与 `/orange-decks/<id>/edit`（需登录，noindex）。
详情页 `/orange-decks/<id>` 服务端渲染完整内容。

## 代码入口

| 范围 | 文件 |
| --- | --- |
| 路由（身份、参数、响应） | `orange_decks.py` |
| 规则、序列化、可见性、后台操作 | `orange_deck_service.py` |
| SQLite 结构 | `orange_deck_schema.py`；PostgreSQL 为 DB 仓库 `0025_orange_decks.sql` |
| 首页列表 | `templates/index.html`、`static/orange-deck-library.js`；卡片沿用 `home-lineup-card.css` 外壳与图标增强 |
| 发布 / 编辑 | `lineup_form.html`（含切换与 `orange_deck_fields.html`）、`orange_deck_form.html`、`publish.js/css`、`orange-deck-editor.js` |
| 详情 | `orange_deck_detail.html`、`orange_deck_macros.html`、`orange-deck-detail.js` |
| 共用渲染 | `static/orange-deck-core.js`、`static/orange-decks.css`（与 `orange_deck_macros.html` 保持一致）；卡面复用图鉴的 `fortune-card-frame.css` 与包边模板，使用纯卡图变体 `.is-art-only`（不叠加名称/描述底、星点与类型，卡图居中铺满），海报与选卡同样使用 |
| 个人中心 | `frontend/components/ui/bento-card.tsx`：概览分别统计阵容码与卡组，「我的阵容 / 我的收藏」可切换卡组 |
| 后台 | `static/admin/orange-decks.js`，「内容与用户 → 卡组库」 |

## 数据与规则

`orange_decks`、`orange_deck_favorites`、`orange_deck_likes` 独立于普通阵容，不进入阵容数量、评分、排行榜或实时榜单。
三张卡分列保存（`card_id_1..3`），不写入任何阵容码字段。

`plan_code` 保存游戏分享的完整方案码（`名称-大橘大利-Base64编码`，最多 512 字符），与普通阵容码分开。
与之独立的 `lineup_code` 为可选阵容码，接受最多 20000 字符的分享文案，复用普通阵容的 `extract_lineup_code` 提取并保存以 `#` 开头的编码。两个字段均可省略或清空；更新时未传字段会保留旧值。
首页、详情和个人中心分别提供复制入口；首页以两个固定操作区明确显示已提供/未填写，详情展示完整内容。AI 上传复用表单和 `create_deck`，其字段白名单同步接受 `lineup_code`。
PostgreSQL 对应 `0028_orange_deck_lineup_code.sql`，先迁移再部署 Web；SQLite 同步建列并保留旧卡组。

列表底部显示累计有效复制次数，成功写入剪贴板后才上报并刷新数量。
首页、详情和个人中心统一记录到 `orange_deck_copies`：同一账号（游客按 IP）在同一卡组的
5 分钟时间窗口内只计一次，沿用普通阵容的去重规则。只统计含有所复制类型代码的公开卡组（`code_type=plan|lineup`，省略默认方案码）；两种复制共用原有卡组去重窗口，历史未记录的次数从 0 开始；
统计同步失败不影响已完成的复制。此计数独立于普通阵容统计和卡组热门排序。
PostgreSQL 对应 DB migration `0027_orange_deck_copies.sql`，需要先于 Web 部署；SQLite 启动时同步建表。
服务端校验格式，不推断游戏内编码与三张卡是否一致；派生草稿不继承可能已不匹配的方案码或阵容码。
`season_id` 记录时间卡片所属资料赛季，不能随创作者默认赛季改变；新增字段对应 DB 迁移 `0026_deck_codes_and_permissions.sql`。

- 品阶、能量、传送门上限复用 `orange_fortune_service` 的 `TIERS`、`PORTALS`、`DECK_SIZE`；`energy` 由服务端按资料计算后保存。
- 公开发布（及被隐藏的已发布内容）必须三张不同且存在的卡，能量不超过所选传送门上限；草稿可缺卡、可超限。
  海报工具允许超限导出的行为不变。
- `card_version`（`版本@时间`）与 `card_snapshot_json`（每张卡保存时的名称与品阶）用于资料更新后的对比：
  卡片消失显示为“失效”，改名或改品阶逐项列出，能量按当前资料重算；不会用其他卡替换。
  含失效卡的卡组不能再保存，需由作者重新选卡；“以此为基础创建”会留空失效卡槽并提示。
- 状态：`draft`（仅作者）、`published`、`hidden`（管理员隐藏，作者与管理员可见，作者可改内容但不能自行恢复公开）、
  `deleted`（任何入口不可见）。编辑使用 `version` 乐观检查。

时间卡片读取当前赛季 release 的 `data/time_cards.json` 和包内图片；图鉴、海报选卡、卡组编辑及详情共用它。
管理员候选预览固定读取候选 ZIP，发布/回滚与资料库、模拟器同步，无需重启。刚上传但尚未发布的包不会影响公开页面。
大橘大利新 ZIP 必须包含完整时间卡片快照；静态基准和本能力上线前已发布的旧包兼容 `static/tools/orange-fortune/cards.json`。
首页点击时间卡片时重新请求详情，打开的旧页面也能查看最新效果；列表卡面、编辑器和海报选卡需刷新页面。
下架卡保留保存时卡名并标为失效，不自动删除卡组或换卡；品阶/能量按当前资料显示，方案码不自动重写。

## 阵容站位

编辑复用创作者模拟器：`/tools/lineup-simulator?creator=orange-fortune&deck=1`（deck 模式）不读写浏览器存储，
父页面通过 `jcc:orange-formation-ready` → `jcc:orange-formation-load` → `jcc:orange-formation-load-result` 载入已保存阵容，
随后的 `jcc:orange-formation` 消息带有结构化 `payload`（与模拟器草稿同构：`board[28]{championId, items}`、`augmentIds`）。

- 服务端只接受创作者入口当前默认且公开的赛季；弈子（含 `~choice-` 选择形态）、装备、强化符文须存在于该赛季资料。
- 星级（1–3）由卡组编辑页设置并随 `board[].star` 保存；模拟器本身不处理星级，重新编辑时按弈子出现顺序保留。
- 羁绊保存模拟器计算的结果（羁绊 ID、数量、档位），名称和图标在展示时按 ID 从资料读取；资料版本变化时标注“为保存时的计算结果”。
  卡片带来的额外羁绊、变身等不自动计算；该说明只在编辑页提示，详情页不重复展示。
- 详情页棋盘复用模拟器的蜂窝几何：每行 7 格，第 2、4 行右移半格，格高为宽的 1.14 倍，行距为格高的 0.78 倍。
- 创作者赛季被隐藏或切换后，旧阵容保留但不显示站位、不可在编辑器修改；作者可以移除后重新配置。
- 首页列表不展示站位与搭配说明，详情页服务端渲染站位；编辑页预览按需请求 `/api/orange-decks/<id>/formation`，不为列表创建模拟器或 iframe。

## 列表、互动与可见性

- 列表卡片右上角只标注「推荐 / 草稿 / 已隐藏 / 含失效卡片」；资料版本、改名或改品阶的说明只在详情、编辑与后台展示。
  卡图下只显示卡名，品阶与能量见卡片弹窗；卡图悬停只轻微提亮，不做位移。
- 搜索匹配卡组名称和所含卡片的当前名称；传送门为精确筛选。
- 点赞沿用普通阵容规则：同一账号对同一卡组每天 1 次、每天最多 5 次卡组点赞，累计计数；只能点赞公开卡组。
- 热门：按累计点赞数加收藏账号数排序（取消收藏即扣除），只列至少有 1 次互动的公开卡组，同分按发布时间。
- 推荐：管理员设置，按推荐时间排列；隐藏或删除会同时清除推荐。
- 收藏 POST/DELETE 幂等；只能收藏公开卡组，取消收藏总是允许。
- 同一可见性规则用于详情、站位、搜索、分享、“以此为基础创建”和导出海报；派生入口只对公开卡组或作者自己的草稿开放，
  被隐藏的内容不可分享或派生。管理员操作写入审计日志（`orange_deck.feature/unfeature/hide/restore`）。

## 分享与海报

- 列表提供独立的“复制方案码”和“复制阵容码”按钮；对应代码未填写时显示“未提供”并禁用。不在卡面显示编码文本。
- 详情页提供两种代码的展示/独立复制、点赞、收藏与作者的编辑/删除。`/api/orange-decks/<id>/fork`、`/export` 与创作者工具的
  `?deck=<id>` 导入仍保留在服务端与海报工具中，目前页面不再提供入口。
- 海报导入只在本页编辑，不读取也不改写 `jcc-orange-creator-v1` 与 `jcc-orange-formation-v1:*`，页头提供返回原草稿的链接。
- 反向入口：创作者页“发布到卡组库”打开 `/orange-decks/new?from=creator`，只读两个草稿键；编辑页未提交的新卡组暂存在
  `jcc-orange-deck-draft-v1`，替换前会确认。图鉴卡片详情可跳转到含该卡的卡组搜索。

## 验证

`python -m pytest -q tests/test_orange_decks.py tests/test_deck_codes_permissions.py tests/test_deck_lineup_codes.py tests/test_deck_copies.py`；DB 仓库
`tests/test_orange_deck_migration.py`、`tests/test_deck_codes_permissions_migration.py`、`tests/test_deck_lineup_code_migration.py`。
本地交互验证：`python tests/serve_deck_review_preview.py` → `node tests/orange_decks.browser.cjs`（需 Playwright Core）。
双码状态、剪贴板、键盘、编辑与深浅主题窄屏检查：同一预览运行 `node tests/deck_dual_codes.browser.cjs`。
后台推荐、行内填写隐藏原因与恢复：`node tests/admin_decks.browser.cjs`（自建并删除一个虚构卡组）。
慢请求、响应乱序及切换列表时的交互检查：`node tests/deck_async_actions.browser.cjs`；
查询成本回归：`python -m pytest -q tests/test_deck_query_cost.py`（使用 SQLite 虚拟机指令预算，不依赖机器测速阈值）。
赛季包联动验证：启动时加 `--prepare-time-cards`，再运行 `node tests/time_card_packages.browser.cjs`。
该包只使用仓库现有基准，浏览器脚本在本地预览库发布后会回滚到原版本；不是新的官方补丁。
预览只监听 loopback，示例数据位于独立 `instance/deck-review-preview`，快捷登录路由仅在此测试入口注册。
浏览器验证需覆盖首页切换/历史、站位展开、卡片弹窗、发布与超限提示、阵容 iframe 往返、海报导入不覆盖草稿和后台操作。
