# 大橘大利卡组库

首页的「卡组库」与「阵容库」同级，切换按钮位于两个列表面板的标题位置，展示用户发布的三卡组合，可附带阵容站位。
URL 状态为 `/?library=decks&tab=&portal=&q=&page=`，支持直接链接、刷新与前进后退；`/` 仍是阵容库。
发布与普通阵容共用 `/lineup/new`：默认是只填方案码与阵容码的「卡组投稿」，`?type=lineup` 打开普通阵容码，
`?type=deck` 仍打开完整卡组表单（直接发布，作者为自己），`/orange-decks/new` 与创作者工具链接不变。编辑仍按类型分开：`/lineup/<id>/edit` 与 `/orange-decks/<id>/edit`（需登录，noindex）。
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
| 共用渲染 | `static/orange-deck-core.js`、`static/orange-decks.css`（与 `orange_deck_macros.html` 保持一致）；卡面由 `fortune-card-art.js`、`fortune-card-frame.css` 与 Jinja 宏共同渲染；带底板图片使用 `.is-official`，旧独立插画保留 `.is-art-only`，海报与选卡同样使用 |
| 个人中心 | `frontend/components/ui/bento-card.tsx`：概览分别统计阵容码与卡组，「我的阵容 / 我的收藏」可切换卡组 |
| 后台 | `static/admin/orange-decks.js`，「内容与用户 → 卡组库」 |

## 数据与规则

投稿、署名、热门与统计的实现见下文「投稿与署名」「热门」与 [数据层接入说明](deck-data-integration.md)。

## 投稿与署名

`deck_submission_service.py` / `deck_submissions.py`。用户只提交两种代码（标题、备注选填），不会直接进入公开库：

- `POST /api/deck-submissions` 需登录与 CSRF；`request_key`（UUID）让重复点击与网络重试返回同一投稿（200, `replayed`），
  同 key 不同内容 409。同一用户、赛季、代码指纹只能有一份进行中投稿；跨用户重复留给管理员判重，不转移署名。
- 用户在 `/me/deck-submissions` 查看列表、私有详情、处理说明和发布结果；只有待处理/待补充可修改、补充重提或撤回。
  管理员认领后（处理中）用户的版本号失效，不能覆盖。页面与接口 private/no-store、noindex。
- 后台「内容与用户 → 卡组投稿」按待处理/我处理的/处理中/待补充/已处理筛选；认领、放回、转派任意管理员可做，
  请求补充、不采纳、判重、保存草稿和发布只限当前处理人。完善使用原卡组编辑器（`/admin/deck-submissions/<id>/edit`）。
- 一份投稿只关联一个草稿：首次保存在同一事务中建卡组并写 `deck_id`，投稿版本锁保证并发首存只有一个成功。
  发布按当前资料重新校验名称、三张卡、能量和赛季，并在同一事务写卡组、投稿、处理事件、通知、审计与活动事件。
  发布接口的 `note` 是卡组搭配说明，给投稿人的说明使用 `review_note`。
- `user_id` 仍是所有者（建稿管理员），`provided_by_user_id` 只用于展示：首页、详情和海报显示「由 XXX 提供」，旧卡组照旧显示作者。
  投稿卡组只能由管理员维护（草稿只能经投稿工作台；公开后可用普通编辑器保存但不能撤回为草稿或删除），供稿人不获得编辑权限；
  管理员读取私有草稿仅限投稿卡组。旧发布接口按字段白名单写入，无法伪造来源、供稿人或首次发布人。
- 「我的卡组」包含自己的普通卡组与被采纳的投稿；个人中心收到的赞/收藏按公开署名归属。

`orange_decks`、`orange_deck_favorites`、`orange_deck_likes` 独立于普通阵容，不进入阵容数量、评分、排行榜或实时榜单。
三张卡分列保存（`card_id_1..3`），不写入任何阵容码字段。

`plan_code` 保存游戏分享的完整方案码（`名称-大橘大利-Base64编码`，最多 512 字符），与普通阵容码分开。
与之独立的 `lineup_code` 为可选阵容码，接受最多 20000 字符的分享文案，复用普通阵容的 `extract_lineup_code` 提取并保存以 `#` 开头的编码。两个字段均可省略或清空；更新时未传字段会保留旧值。
首页、详情和个人中心分别提供复制入口；首页以两个固定操作区明确显示已提供/未填写，详情展示完整内容。AI 上传复用表单和 `create_deck`，其字段白名单同步接受 `lineup_code`。
PostgreSQL 对应 `0028_orange_deck_lineup_code.sql`，先迁移再部署 Web；SQLite 同步建列并保留旧卡组。

列表底部显示累计有效复制次数，成功写入剪贴板后才上报并刷新数量。每次复制手势带 `action_id`（网络重试复用），
服务端同时写一条复制动作（`copy_action_events`，含代码类型、服务端判断的 `actor_key` 与 `rank_eligible`）。
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
  卡片沿用站点中性配色：三张卡面同一基线，平放无底光与投影；传送门名称用正文色、图标用次要色（风险色只留在筛选与详情）；
  能量格统一用站点强调色，仅超限格标红。卡片内容宽度 ≥ 400px 时（容器查询）
  传送门、能量与两个复制按钮收进卡面右侧的侧栏，以减少纵向高度；更窄时（手机）改为传送门行、卡面、复制按钮自上而下排列。
  卡图下只显示卡名，品阶与能量见卡片弹窗；悬停只改变卡名或按钮颜色，不做位移、缩放或亮度动画。
- 搜索匹配卡组名称和所含卡片的当前名称；传送门为精确筛选。
- 点赞沿用普通阵容规则：同一账号对同一卡组每天 1 次、每天最多 5 次卡组点赞，累计计数；只能点赞公开卡组。
- 热门：见下节；不再要求至少一次互动。
- 推荐：管理员设置，按推荐时间排列；隐藏或删除会同时清除推荐。
- 收藏 POST/DELETE 幂等；只能收藏公开卡组，取消收藏总是允许。
- 同一可见性规则用于详情、站位、搜索、分享、“以此为基础创建”和导出海报；派生入口只对公开卡组或作者自己的草稿开放，
  被隐藏的内容不可分享或派生。管理员操作写入审计日志（`orange_deck.feature/unfeature/hide/restore`）。

## 热门

`hot_ranking()` 先取全部候选再分页，总数与页码一致；候选每次请求重新读取，隐藏、删除、资格变化立即生效。
候选：公开、名称非空、属于当前卡片赛季，三张卡都在当前资料中且能量不超过传送门上限（资料版本变化后逐卡重查，不因版本号不同清空）。

分数 = 近 30 天信号之和（每条按天龄 7 天减半）+ 新卡组加成 1.5×0.5^(发布天数/3)：

- 复制 3 分：`copy_action_events.rank_eligible=1`，按卡组/行为者/日去重，两种代码合计一次；所有者、供稿人、管理员、自动化账号不计。
- 收藏 2 分：只看当前收藏关系（取消即消失）；点赞 1 分：每人每卡组每日一条。两者都排除上述自互动。
- 三张卡完全相同的卡组每重复一次乘 0.6，避免首页被同一组合占满；零信号卡组按新卡组加成与发布时间补位。

只缓存信号聚合（60 秒，且以最新活动/复制事件 ID 为键，新互动即时可见）。推荐仍是管理员人工设置。

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
后台大数字排版、搜索焦点与慢请求、隐藏失败重试：`node tests/admin_decks_resilience.browser.cjs`（仅模拟响应，不写入数据）。
慢请求、响应乱序及切换列表时的交互检查：`node tests/deck_async_actions.browser.cjs`；
查询成本回归：`python -m pytest -q tests/test_deck_query_cost.py`（使用 SQLite 虚拟机指令预算，不依赖机器测速阈值）。
赛季包联动验证：启动时加 `--prepare-time-cards`，再运行 `node tests/time_card_packages.browser.cjs`。
该包只使用仓库现有基准，浏览器脚本在本地预览库发布后会回滚到原版本；不是新的官方补丁。
预览只监听 loopback，示例数据位于独立 `instance/deck-review-preview`，快捷登录路由仅在此测试入口注册。
浏览器验证需覆盖首页切换/历史、站位展开、卡片弹窗、发布与超限提示、阵容 iframe 往返、海报导入不覆盖草稿和后台操作。

## 卡面展示

`time_card_art.py` 从当前选中版本的本地图片读取尺寸和透明边界，生成只用于展示的 `framed` 与 `art_style`。官方正方形图片的可见卡面在统一 5:8 展示区内按卡身宽度等比缩放（占宽 96%）并对齐底边：各品阶卡身同宽、横幅与底板同高，王者及以上顶部宝石只向上延伸，异常高的轮廓才退回按高度适配；完整保留宝石、边框和底板。卡名写在官方横幅上，类型与能量点写在底板上（卡面宽度不足 120px 时由容器查询隐藏，这类位置都在卡面旁另列卡名），效果说明放在卡面外。图鉴、卡片弹窗与海报使用 `--spot` 品阶色底光，首页列表卡面不使用。不能按品阶假设固定图片尺寸，也不能仅用 `layout=icon` 或 URL 判断图片类型：旧包的短独立插画也使用该布局值。

版本发布、候选预览与回滚仍读取各自图片，不用静态基准覆盖旧包卡图。若当前发布包使用独立插画，部署样式后仍保持该包图片；切换完整卡面需要另行发布对应图片修订包。包协议与数据库结构不变。

图鉴页头为王者、史诗、传说各一张完整卡面组成的扇形陈列（仅完整卡面包显示；传说固定展示「永恒的心」`7250071`，当前包缺该卡时退回该品阶第一张完整卡面；卡片绕底部尖角旋转，地面阴影画在不旋转的容器上并保持水平，卡面文字在各断点都保留）；宽屏筛选栏吸顶，卡片为自适应栏数（约 196px 起，手机两栏）的展台卡，卡名、类型与生效回合在卡面下方，摘要限制三行，详情保留完整效果和所有生效回合；手机和键盘均可打开、关闭详情。专项浏览器检查为 `tests/orange_full_cards.browser.cjs`（`DECK_REVIEW_URL` 指向隔离预览）。
