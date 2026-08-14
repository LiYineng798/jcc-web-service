# 赛季资料库（season library）

站内所有赛季资料页（`/tools/seasons/<season_id>`）、首页“资料库”菜单、sitemap 和阵容模拟器的数据，统一来自 `static/season-data/`。这个目录**由脚本生成，不要手工编辑**；数据源头是仓库外的赛季档案库 `ccmax资料/数据模板`（自包含的多赛季快照，含 schema 与校验脚本）。

## 数据流

```
ccmax资料/数据模板（档案库，源头）
   │  python scripts/season_library/import_from_archive.py
   ▼
static/season-data/
   ├── catalog.json          站点赛季索引（驱动导航/路由/sitemap）
   └── <season_id>/
       ├── index.json        紧凑载荷：列表页一次 fetch 全部渲染数据
       ├── champions.json    完整快照：弈子详情页服务端渲染
       ├── traits.json       完整快照
       ├── items.json        完整快照：模拟器运行时装备数据
       ├── board_units.json  羁绊生成的棋盘对象，仅供模拟器使用
       └── assets/…          本地图片（路径与档案库一致）
```

阵容模拟器在运行时读取 `catalog.json`，再按当前赛季加载 `champions.json`、`traits.json`、`items.json` 和 `board_units.json`。默认赛季按公开状态、生效日期和游戏版本动态选择最新项；赛季切换和图片缓存使用 `version_id`。羁绊下拉选项位于弈子搜索框旁，按资料分类生成并直接展示羁绊图标和弈子数量，未命中的弈子保持可见但变暗；阵容羁绊按独特、彩色、金色、银色、铜色、未激活灰色排序，档位的 `style=unique` 用于识别独特羁绊。纹章装备通过 `extensions.trait_id`（官方导入数据兼容 `extensions.fetter_id`）关联羁绊，装备后其持有弈子为该羁绊贡献一次计数。棋盘六边形尺寸由棋盘容器宽度驱动，在桌面双栏、中等宽度和移动端布局下均须完整显示 7 列。阵容图片使用专用宽屏 DOM 画布，可由用户决定是否在左侧渲染羁绊列表、是否输出透明背景，列表最多展示棋盘高度内可完整容纳的 8 项，并复用页面上的相同排序；宽图和 3:4 海报导出均显示分阶段进度遮罩。导出依赖的弈子头像和羁绊等级框必须使用真实图片节点，不能改回伪元素背景。模拟器不再依赖独立的构建产物。

## 描述富文本与属性标记

赛季原文中的 `【AP】`、`【HP】`、`【AS】`、`【DR】` 以及 `【法术加成】`、`【生命上限】`、`【攻击速度】`、`【伤害减免】` 等别名，在导入时由 `season_rich_text.py` 统一解析。脚本保留原始 `description`/`effect`，并在相邻的 `description_tokens`/`effect_tokens` 中写入规范化属性 id、展示类型、无障碍标签、图标或文字回退。资料列表、弈子详情和模拟器悬停面板只渲染经过转义的 token，不信任上游 HTML。

现有位图资源位于 `static/season-stats/`，包括 AD、AP、伤害增幅、攻速、生命值、护甲、魔抗、暴击、法力和射程。属性图标直接以内联图片展示，不添加芯片背景或边框；没有独立图片的减伤、全能吸血等属性才使用紧凑文字回退。S17 技能正文会保留“木灵加成”标签，并把其数值后空括号（如 `0()`、`0%()`）解析为 `0(amp图标)`、`0%(amp图标)`，而不是用图标替换标签文字。新增赛季只要沿用已注册标记即可自动展示；出现新标记时，应在 `season_rich_text.py` 的规范化映射中增加一次。

## 官方补全与棋盘对象

导入器会读取每个版本已经归档的官方 `source-snapshots/chess.json`，补全被常规商店筛选遗漏、但被公开羁绊文本引用的解锁弈子。S16.5 的加里奥属于此类：它进入 `champions.json`、资料库和模拟器 5 费弈子池，使用统一的“解锁”标记并保留官方解锁条件。

羁绊文本引用的非阵容对象，例如 S16.5 提伯斯、厄塔汗、冰封塔楼和岩石，以及 S17 圣物和迷你黑洞，会进入独立的 `board_units.json`。对象记录包含关联羁绊、`placement_rules`（激活人数与最大上场数量）、`can_equip`、属性、技能和本地图标；`extensions.library_visible=false` 保证资料库不展示，`extensions.simulator_visible=true` 允许模拟器按当前羁绊计数解锁和限量上场。棋盘对象不贡献羁绊、没有费用并默认不能携带装备；只有官方羁绊文本明确说明可携带装备的对象（如提伯斯）才设置 `can_equip=true`。推导规则以官方对象名称是否出现在羁绊描述/档位效果中为准，避免把未被玩法规则引用的训练假人或内部召唤物带入模拟器。

`import_from_archive.py` 本身不会请求 DataTFT。它只读本地归档快照；当官方快照引用的棋盘对象图片尚未落地时，允许从腾讯官方 CDN 补一张并立即生成版本化 WebP。测试只使用生成后的本地文件，不执行任何远程拉取。未来赛季应先更新档案库快照再重导入，站点会动态发现新弈子和被羁绊引用的棋盘对象，通常无需修改 Web 代码。

## 阵容码格式

模拟器导出 `JCC2-` 前缀的固定长度阵容码。码体为 237 字节二进制数据的 Base64URL 表示，总长度固定为 321 字符：1 字节功能标志、4 字节赛季哈希、4 字节单位/装备字典哈希、28 个固定 8 字节棋格（弈子索引和 3 个装备索引），最后是 4 字节 FNV-1a 校验和。赛季哈希用于在打开分享链接时先加载正确赛季，字典哈希防止资料版本不匹配时静默导入错误单位，校验和用于识别截断或篡改。旧版 Base64 JSON 阵容码仍可导入，但新导出和分享链接只生成 `JCC2-` 格式。

## 新增一个赛季（例：s19）

1. 按档案库 `数据模板/README.md` 的教程把 s19 数据加进档案库并通过 `python scripts/validate.py --all`。
2. 在 Web 仓库根目录执行：

   ```powershell
   python scripts/season_library/import_from_archive.py --season s19
   ```

   找不到档案库时用 `--source "D:\...\数据模板"` 或环境变量 `JCC_SEASON_ARCHIVE` 指定。
3. 完成。首页“资料库”菜单、`/tools/seasons/s19`、弈子详情页、阵容模拟器和 sitemap 全部自动出现，无需改任何页面代码。
4. 运行 `python -m pytest -q tests/test_season_reference.py tests/test_lineup_simulator_rebuild.py`（数据一致性与页面回归）。

## 更新已有赛季版本

资料库是源头，`static/season-data/` 是可重新生成的站点副本。更新已有赛季时不要覆盖旧版本目录：

1. 在档案库建立新的完整版本快照，通过单赛季和全库校验，并完成人工抽查。
2. 保持旧 `default_version_id` 不变，先提交并备份新版本源数据。
3. 在档案库切换 `season.json.default_version_id` 和 `catalog.json.latest_version_id`。
4. 在 Web 仓库重新导入该赛季：

   ```powershell
   python scripts/season_library/import_from_archive.py --season s16_5
   ```

5. 确认控制台没有缺图警告，检查 `static/season-data/s16_5/index.json` 中的 `version_id`、数量和图片路径。
6. 运行测试，重启 Web 进程以清除服务端缓存，再做资料页和模拟器冒烟检查。

导入脚本目前只复制档案库的 `default_version_id`，并会先删除再生成对应的 `static/season-data/<season_id>/`。因此不要在该输出目录保存人工维护文件。单赛季导入会保留 catalog 中其他赛季；全量导入会按档案库 catalog 重建站点 catalog。

### S18 PBE 合并 JSON

S18 PBE 的源文件是 `ccmax资料/data-cn-CJkaeodq.S18.json`。更新时先在档案库执行：

```powershell
cd D:\1\codex\jcc-new\ccmax资料\数据模板
python scripts/import_existing_seasons.py --season s18 --s18-json "..\data-cn-CJkaeodq.S18.json"
python scripts/validate.py data/seasons/s18
```

该命令保留旧 S18 快照并重建默认 `PBE` 快照，自动下载弈子头像、立绘、技能图、装备和仙灵图片。技能图按 `https://static.datatft.com/images/skill/<chessId>.jpg` 获取；仙灵图片下载失败会终止生成；没有独立图片的临时消耗品使用已记录来源的本地回退图。随后在 Web 仓库运行 `python scripts/season_library/import_from_archive.py --season s18`，资料页和模拟器会同时切换到新数据，并为技能图生成版本化 WebP。

## 图片与 WebP

档案库保存原始图片，Web 导入脚本复制原图，并使用 Pillow 生成两类 WebP：

```text
static/season-data/<season_id>/assets/champions/card/<champion_id>.webp
static/season-data/<season_id>/assets/optimized/<version_id>/{champions,skills,items,traits}/<id>.webp
```

卡片图宽度不超过 500px、质量 75；模拟器小图限制在 96px、质量 82，并通过 `optimized_local_path` 优先加载。弈子悬浮卡片背景继续使用原始大图。优化路径包含 `version_id`，新补丁不会命中旧图缓存。Pillow 已列入 `requirements.txt`；导入前先执行 `python -m pip install -r requirements.txt`。若控制台出现“需要 Pillow”或 WebP 缺图警告，应修复运行环境后重新导入。不得手工逐张转换或把 WebP 写回档案库覆盖原图。

当前站点输出目录按赛季隔离，但同一赛季只发布一个默认版本。若以后需要让多个补丁同时在线，必须先把输出升级为 `static/season-data/<season_id>/<version_id>/...`，并同步修改 catalog、路由、前端加载地址和缓存键；在这套改造完成前，不要声称站点能够同时托管同赛季多个版本。

旧的 `build_simulator_from_library.py` 属于旧模拟器构建流程；重建后的模拟器直接读取 `static/season-data/`，日常更新不需要运行它，也不要继续向旧的全局 `static/tools/lineup-simulator/data/` 写新赛季数据。

弈子列表使用生成后的 WebP 小图以控制加载量；详情页和羁绊成员悬停卡使用 `splash` 大图。来源没有独立装备图标时，导入数据必须提供可用的本地回退图片，并在 `extensions.image_fallback_*` 中记录依据。

## 发布检查与回滚

发布前至少完成：

```powershell
python -m pytest -q tests/test_season_reference.py tests/test_lineup_simulator_rebuild.py
```

并人工确认：新赛季/版本出现在资料库菜单；弈子、羁绊、装备数量合理；列表小图和悬浮大图可加载；模拟器能切换赛季、上场弈子、计算羁绊并装备物品；浏览器没有 404。

生产发布时应将 JSON 和图片作为同一批静态资源上传，然后重启 `jcc.service`，最后检查 `/api/health` 和关键页面。不要只上传 catalog 或 `index.json`，否则客户端会提前引用尚未部署的资源。需要回滚时，先在档案库把默认版本指回上一个已验证快照，重新导入 Web 输出并重新部署；不要直接在生产服务器上修改生成文件。

## 约定与注意事项

- **顺序**：`catalog.json` 保持档案库顺序（旧→新），站点展示时反转为新→旧。想调整菜单顺序就调整档案库 catalog 顺序后重导入。
- **状态**：`active` 正常展示；`draft` 显示“前瞻”标注；`archived` 显示“往期”。三种状态都会公开展示，想下线一个赛季就把它从档案库 catalog 移除后重导入。
- **弈子 URL 用 id 不用名字**（存在同名弈子，如 s17 的多形态厄运小姐）。旧的 S18 名字 URL 会 301 到 id URL。
- **“新弈子”徽章**：档案库中弈子 `tags` 含 `"new"` 时展示，导入后自动生效（S16.5 的 14 个新增弈子已打标）。
- **机制 tab**：档案库 `mechanics/` 中注册的每种玩法在页面上是一个独立 tab。`kind=charm` 使用仙灵卡片，支持搜索、分类、本地图标和可切换的升级/棱彩效果；`kind=wand` 仅保留给历史快照；god、monster 等使用通用机制卡片。
- **模拟器特殊能力**：模拟器按 schema 做能力检测。弈子的 `availability.type=unlock` 会自动展示解锁标记和条件；装备的 `recipe.component_ids` 会自动进入散件需求统计；`category=emblem` 的装备会按 `extensions.trait_id` 或 `extensions.fetter_id` 为持有弈子提供对应羁绊；`board_units.json` 的 `placement_rules` 控制羁绊棋盘对象的解锁与数量。未来赛季应优先扩展公共 schema，不要在模拟器中按赛季 id 写死分支。
- **缓存**：列表页对 `index.json` 的请求带 `?v=<version_id>`，档案库版本号变化即自然失效。服务端 `season_reference_service` 用 `lru_cache` 缓存，重导入数据后需重启进程（测试可调 `clear_caches()`）。
- 通用页面的 CSS 类名保留历史 `s18-` 前缀（`season-reference.css`），避免大规模改名回归；新增样式请用中性命名。
