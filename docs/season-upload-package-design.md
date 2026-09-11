# 后台上传赛季更新包

本分支已实现。运行与首次部署见 [操作手册](season-package-operations.md)。日常数据更新流程为：本地处理 → 完整 ZIP → 后台上传 → 校验与预览 → 发布。Git 负责网站代码和数据库结构升级。

## 数据边界

一个包是一个已登记赛季的完整快照，含弈子、羁绊、装备、强化符文、棋盘对象、该版本玩法、全部图片、更新说明和来源。没有增量补丁或在线编辑；修正内容需要重新打包并提高资料修订号。上传不修改用户、用户阵容、实时排行榜 JSON 或赛季公开状态。

服务器只验证数据，不下载来源 URL、不抓取第三方、不运行包内脚本、不执行 SQL、Git、pip 或服务重启。更新说明是供管理员阅读的内容，公共「更新公告」仍由原工作台单独发布。

## 包协议 1.0

```text
manifest.json
release-notes.json
provenance.json
supplements.json
data/
  season.json
  index.json
  champions.json
  traits.json
  items.json
  augments.json
  board_units.json
  tft-codebook.json             可选
  mechanics/<mechanic-id>.json  每种玩法一份
assets/                        全部 PNG / JPEG / WebP
```

核心五个模块始终有文件；不适用的可选模块写空数组并声明 `absent`。弈子、羁绊和装备必须 `present` 且非空。没有特殊玩法写 `mechanics: []`，支持一个或多个玩法。空数组表示明确无此玩法，不表示采集失败。

manifest 由打包器生成，字段示例如下（`files` 必须由工具填满，不能上传这个空清单）：

```json
{
  "package_format": "jcc-season-package",
  "package_schema_version": "1.0",
  "dataset_schema_version": "1.0",
  "package_id": "s18-18_18_2-r2",
  "season_id": "s18",
  "game_version": "18.18.2",
  "data_revision": 2,
  "created_at": "2026-09-10T00:00:00+00:00",
  "effective_at": "2026-09-10",
  "builder": {"name": "jcc-season-pack", "version": "1.0.0"},
  "required_capabilities": ["reference.cards.v1", "simulator.placement_rules.v1"],
  "modules": {
    "champions": {"state": "present", "file": "data/champions.json"},
    "traits": {"state": "present", "file": "data/traits.json"},
    "items": {"state": "present", "file": "data/items.json"},
    "augments": {"state": "present", "file": "data/augments.json"},
    "board_units": {"state": "present", "file": "data/board_units.json"}
  },
  "mechanics": [],
  "files": {}
}
```

文件清单列出除 manifest 自身外的每个文件：规范相对路径、`bytes`、小写十六进制 `sha256`。服务器另计算整个 ZIP 的哈希：重复上传原 ZIP 返回原任务；同包 ID 或同赛季/补丁/修订号被不同 ZIP 使用时拒绝。

游戏补丁与资料修订分开，补充条件时只增加 `data_revision`。生效时间仅作记录，未实现定时发布。SHA-256 证明完整性，不证明官方来源真实性。

服务器重算数量，使用生产序列化器逐项比对 `index.json` 与完整弈子、羁绊、强化符文文件。版本和赛季标识必须一致，羁绊、装备组件和棋盘对象激活来源引用必须存在。

## 可扩展玩法

注册项包括 `id / kind / display_name / presentation / file / targets`。网站按该版本注册表生成标签，不固定为 S18 或仙灵。ID 保持稳定，名称可变。`targets` 当前只接受 `["reference"]`；模拟器上阵能力由已有 `board_units` 表达。

| 模板 | 内容 | 用途 |
| --- | --- | --- |
| `cards.v1` | 名称、说明、分类、标签、回合和条件 | 通用资料卡片 |
| `variants.v1` | `variants` 数组：标签、效果、费用、条件 | 升级/多形态玩法 |
| `stages.v1` | `stages` 数组，同样的受控字段 | 阶段奖励 |
| `table.v1` | `columns` 和等宽 `rows`，最多 8 列/100 行 | 对照规则表 |
| `legacy.v1` | 已有 charm/wand/god/monster/none 展示 | 现有赛季兼容 |

通用玩法支持搜索和分类筛选，所有文字通过 DOM 文本节点输出。`data` 可用字段：`category / category_label / tags / rounds / requires / variants / stages / columns / rows`；变体和阶段可用字段：`label / effect / cost / requirements`。参考 [阶段奖励示例](examples/generic-season-mechanic.json)，将对象加入准备目录的 `index.json.mechanics` 后打包。

未知模板、必需能力或棋盘对象规则会被拒绝。新资料玩法可使用通用模板直接更新；全新模拟器交互或战斗逻辑需先升级网站。模拟器仍定位为阵容与棋盘编排，不运行游戏战斗。

初版仅接受 catalog 已登记赛季。新赛季的首次登记（名称、官方映射、基础资源和默认可见性）仍走代码变更；登记后可通过后台反复更新。包不会自行新增公开入口。

## 来源与补充

打包器读取已合并的本地数据；`--provenance` 可携带采集记录，玩法条目的 `extensions.provenance` 保留。每个非空 `rounds/requires` 还写入 `supplements.json.entries`：`mechanic_id / record_id / field / value / source_id / inherited_from_version / verification`。

只有已有来源明确 `verified_for_current_patch: true` 时才生成 `verified`，否则为 `inherited_unverified` 并告警。缺少来源的本地补充不能被冒充为官方核验。服务器检查补充值一致、来源存在和记录不重复；不能通过清空 supplements 隐藏非空补充。

S18 18.18.2 的现有本地资料已验证可打包：170 条仙灵回合加 55 条条件，共 225 个继承字段进入报告。上传和打包不访问 DataTFT，也不访问其他第三方。

## 校验与发布

上传后状态为 `queued`，worker 进入 `validating`，结束为 `ready / rejected / cancelled`。数据库记录任务阶段、百分比、错误、取消请求、尝试次数、租约令牌和心跳。网络进度和服务端校验进度分开显示；浏览器关闭后已入库任务继续。

独立串行 worker 每 2 秒检查队列，10 分钟无心跳的任务可接管，每次最终写入核对令牌。校验阶段限时 30 分钟，崩溃由 systemd 重启，内存由 unit 限制。重试使用新 staging 目录；崩溃后留下的完整目录必须再次检查清单与哈希才能复用。

阻断错误：不支持协议/能力、重复或越界路径、独立目录条目、符号链接、压缩炸弹、加密 ZIP、脚本/嵌套 ZIP、文件大小/哈希错误、损坏图片、缺少资源、结构或引用不一致。

初始限制：ZIP 256 MiB、解压 1 GiB、10,000 文件、单文件 64 MiB、JSON 32 MiB、manifest 4 MiB、压缩比 250、单图 2400 万像素且非动画。不接受 SVG。上传前及解包前检查磁盘余量。

报告包含作者说明、记录新增/修改/移除、修改字段、图片内容差异、玩法变化、来源及数量。继承字段、玩法移除，以及移除至少 3 条且达到原模块 25% 的内容必须确认告警；结构错误不能跳过。

发布要求 `expected_revision` 与线上状态和比较报告一致。事务一起提交当前/上一版本指向与事件，各赛季独立切换。新请求使用新版本，一次读取沿用同一 release_id；图片/JSON URL 都带 release_id，避免混版。

切换后通过 Flask 实际读路径检查 catalog、资料页、样例弈子详情、模拟器数据和健康接口。失败按修订号条件恢复旧指向，不能覆盖后来发布。中断留下的 `verifying` 事件由 worker 两分钟后恢复验证。此检查不代替部署时的外部 Nginx/浏览器验收。

回滚可选上一版本、任一历史已发布包或当前代码自带静态基准。静态基准不是独立上传快照；要在后续代码部署后准确回到最初资料，应在首次启用时先把当前静态快照作为初始包发布。

## 读取、权限与存储

`season_data_repository.py` 统一解析版本，资料库、弈子详情、模拟器、实时阵容详情跟随 catalog 的 `data_root / asset_root`。没有上传版本的赛季仍用 `static/season-data/<id>`。

预览用管理员登录和 `preview_release`，响应 `private, no-store`、`noindex, nofollow`。预览禁止写请求和访问统计，模拟器草稿使用独立 localStorage 前缀。管理员能预览隐藏赛季，包不能改变公开策略。

`/season-assets/<release_id>/<path>` 由 Flask 验证文件清单和权限。候选包只对管理员开放；历史已发布包只在赛季公开时允许访客读取。原 ZIP、来源和说明不在公共资源范围。资源重新验证访问状态，不能把目录公开映射为 Nginx alias。

四张表为 `season_release_packages / season_import_jobs / season_active_releases / season_release_events`，PostgreSQL 使用 DB 迁移 `0015_season_release_packages.sql`，SQLite 使用相同 SQL。DB 导入顺序、数量与完整性检查同步扩展。

磁盘由 `JCC_SEASON_PACKAGE_ROOT` 指定：私有 `uploads/`、`staging/`、`releases/`；报告与事件存在数据库，不另存 reports 目录。已验证目录不再修改，初版保留所有历史包，尚未提供自动清理。

后台采用独立 React 岛集成用户提供的 FileUpload 样式，保留圆角虚线框、拖放、真实进度、重试、移除和减少动画偏好，复用现有主题。源码 `frontend/`，构建输出 `static/admin/season-packages/`，服务器不需 Node。Tailwind 限定在 `#seasonPackageRoot`。

分块续传、带引用检查的自动清理、对象存储、多节点共享和新能力版本属于后续扩展，当前未实现。
