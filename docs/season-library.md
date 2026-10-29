# 赛季资料与模拟器

操作流程见 [赛季维护](season-maintenance-playbook.md)，上传约束见 [ZIP 协议](season-package-format.md)。
新玩法的模板、元数据和兼容边界见 [玩法接入约定](season-mechanic-contract.md)。

## 数据来源与读取

外部 `ccmax资料/数据模板` 保存版本化源档案；`scripts/season_library/import_from_archive.py`
转换为网站 JSON 与本地图片。默认输出 `static/season-data/`，也可指定独立制作目录。
生成目录会被重建，不在其中保存手工维护文件。

`static/season-data/catalog.json` 负责初次登记。`season_data_repository.py` 为已发布赛季选择
私有目录中的 release；未发布时回退到代码自带静态基准。资料页、弈子详情、模拟器及实时站位详情
通过此读取层解析路径，不能绕开它硬写静态 URL。公开客户端目录是 `/api/season-catalog`。

| 文件 | 用途 |
| --- | --- |
| `index.json` | 列表用紧凑载荷，与完整文件保持一致 |
| `champions.json / traits.json / items.json` | 弈子详情、羁绊和装备完整数据 |
| `board_units.json` | 特殊可布阵对象、放置规则和发现审计 |
| `augments.json` | 强化符文；可信时机缺失时明确留空 |
| `tft-codebook.json` | 可选的外部 TFT 英雄/装备 ID 映射 |
| `assets/` | 本地原图与版本化优化图片 |

资料库、模拟器与海报创作者（`creator`）共享同一 release，公开状态、排序独立，由 `season_visibility.py` 管理；
模拟器和创作者各有默认赛季，创作者工具只使用自己的默认赛季。catalog 条目可用 `surface_status` 为各入口指定初始状态，
未指定时创作者入口为隐藏，普通赛季不会意外出现在海报工具中。
只有 active/archived 公开，hidden/disabled 返回受保护结果，不能按旧 draft 规则推断可见性。
公开资源在所有展示入口都不可用时拒绝访问。实时站位详情要求资料库公开。

## 独立模式赛季（官方分支档案）

没有外部源档案的模式（如大橘大利 `orange_s400001`）由官方分支直接生成档案：
`scripts/collect_orange_fortune.py` 归档版本目录选中的分支，`scripts/season_library/official_archive.py`
把 chess/race/job/equip/mission/hex 转为 `数据模板` 布局（商店/任务解锁弈子、羁绊档位、装备属性与配方、图片和
`source-snapshots`），再交给 `import_from_archive.py`。转换规则以 `s16_5` 的来源分支 17.17.8b-S18 回放验证：
弈子与装备逐字段一致；`new` 标签取决于 `--previous-season` 基准，旧赛季的基准未在仓库保存。
官方 job.js 已下线时无法回放职业羁绊，以 race 的同一规则为准。

```powershell
python -I scripts/collect_orange_fortune.py --output instance/orange-fortune-archive/<时间戳>
python -I scripts/season_library/official_archive.py --official instance/orange-fortune-archive/<时间戳> --output instance/season-archive --season-id orange_s400001 --display-name "英雄联盟传奇 · 大橘大利" --set-number 16 --theme "英雄联盟传奇 · 大橘大利" --previous-season static/season-data/s16_5 --surface creator=active
python scripts/season_library/import_from_archive.py --source instance/season-archive --season orange_s400001 --official-only --initial-status hidden
```

单赛季导入只替换或追加目标条目，不移除 catalog 中源档案未列出的赛季。首次登记后，同一流程配合 `--output-root`
与 `build_upload_package.py` 制作 ZIP，通过「赛季版本更新」发布。弈子、羁绊、装备和强化符文图标都预先下载进档案，
重跑转换只补下载缺失文件；导入器直接使用档案中已有的强化符文图标。图片下载失败会写入 `asset-report.json`，
对应图片字段留空，不用其他图片替代。

## 来源不能混淆

先在源档案阅读 `docs/官方数据源与版本更新指南.md`，核对官方 mode、版本、客户端代号和映射。
不以站内赛季数字推断官方编号，不把未上线资料当作正式规则。

- 正式弈子、装备、羁绊、仙灵及强化符文来自归档官方快照。Web 导入可补取缺少的官方资料/图片；打包和服务器校验离线执行。
- 维护使用 `--official-only` 跳过第三方强化符文回合观察请求，不访问 DataTFT。
- 官方缺少逐条出现时机时保留空列表与 unavailable 标记，不能推断全阶段；站点规则分类要保留规则来源。
- 代码自带 S18 基准为 `18.18.2`，官方 mode 18 / client S19。仙灵来自 adventure，
  170 个回合与 55 个条件字段沿用本地 18.18.1c 第三方档案，保留
  `extensions.provenance`、继承版本和 `verified_for_current_patch=false`。
  这些不是当前官方核验规则，覆盖源档案前须保留补充；不联网恢复第三方字段。
- 多形态弈子按 ID 区分，不按名称合并。详情 URL 也使用 ID。
- 上游文本先由 `season_rich_text.py` 解析为安全 token，保留原文，不执行上游 HTML。

## 特殊单位与能力

导入器根据官方羁绊文本、明确可放置/备战席技能和快照字段发现布阵对象；
名称差异优先补 `official_supplements.CURATED_ALIASES`，不写赛季专用前端分支。
每次更新查看 `board_units.discovery_audit` 的 review 项，区分可布阵单位和战斗召唤物。

- `trait_ids` 表示解锁/筛选关联；只有 `contribution_trait_ids` 决定对象贡献的羁绊，二者不可混用。
- `placement_rules` 可按 trait_id 或 champion_id 解锁和限量；装备默认禁止，仅 can_equip=true 可装备。
- `availability.type=unlock` 表示解锁弈子；装备 recipe 与 emblem 的 trait_id/fetter_id 驱动合成需求和羁绊贡献。
- 新玩法展示优先用已支持模板；新模拟器行为仍需代码适配，不承诺任意未来赛季直接可用。

## 图片与分享兼容

导入器通过 Pillow 生成弈子卡图及 `assets/optimized/<version_id>/` 小图。
小图优先 optimized_local_path，详情和悬停用 splash；缺独立原图时保留可用回退与 provenance。
JSON 和图片必须完整交付。缓存/代理设置见 [运维](operations.md)。

当前模拟器直接读取上述资料，不使用旧 `static/tools/lineup-simulator/data/` 构建产物。
棋盘为 4×7；羁绊、人口、特殊对象和装备约束由资料能力驱动。

新分享码 `JCC2-` 固定 321 字符，含赛季/字典哈希与校验和；旧 Base64 JSON 只用于导入兼容。
资料字典变化可能使旧码失效，必须检查样例。最多六个强化符文保存在本地、撤销/重做和海报中，
不写入固定 JCC2 结构。JCC2 不是游戏内可直接使用的金铲铲阵容码。

页面及图片导出兼容约束见 [前端维护](ui.md)。旧构建器仍保留供兼容核查，不用于日常更新。
