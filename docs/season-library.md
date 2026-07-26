# 赛季资料库（season library）

站内所有赛季资料页（`/tools/seasons/<season_id>`）、首页“资料库”菜单、sitemap 和阵容模拟器的数据，统一来自 `static/season-data/`。这个目录**由脚本生成，不要手工编辑**；数据源头是仓库外的赛季档案库 `ccmax资料/数据模版`（自包含的多赛季快照，含 schema 与校验脚本）。

## 数据流

```
ccmax资料/数据模版（档案库，源头）
   │  python scripts/season_library/import_from_archive.py
   ▼
static/season-data/
   ├── catalog.json          站点赛季索引（驱动导航/路由/sitemap）
   └── <season_id>/
       ├── index.json        紧凑载荷：列表页一次 fetch 全部渲染数据
       ├── champions.json    完整快照：弈子详情页服务端渲染
       ├── traits.json       完整快照
       ├── items.json        完整快照：模拟器构建输入
       └── assets/…          本地图片（路径与档案库一致）
   │  python scripts/season_library/build_simulator_from_library.py --season <sid>
   ▼
static/tools/lineup-simulator/data/*.json + webp/season/<sid>/… + blur/webp/season/<sid>/…
```

## 新增一个赛季（例：s19）

1. 按档案库 `数据模版/README.md` 的教程把 s19 数据加进档案库并通过 `python scripts/validate.py --all`。
2. 在 Web 仓库根目录执行：

   ```powershell
   python scripts/season_library/import_from_archive.py --season s19
   ```

   找不到档案库时用 `--source "D:\...\数据模版"` 或环境变量 `JCC_SEASON_ARCHIVE` 指定。
3. 完成。首页“资料库”菜单、`/tools/seasons/s19`、弈子详情页和 sitemap 全部自动出现，无需改任何页面代码。
4. 如需把模拟器切到该赛季：

   ```powershell
   python scripts/season_library/build_simulator_from_library.py --season s19
   ```

5. 运行 `python -m pytest -q tests/test_season_reference.py tests/test_season_library_build.py`（数据一致性与页面回归）。

## 约定与注意事项

- **顺序**：`catalog.json` 保持档案库顺序（旧→新），站点展示时反转为新→旧。想调整菜单顺序就调整档案库 catalog 顺序后重导入。
- **状态**：`active` 正常展示；`draft` 显示“前瞻”标注；`archived` 显示“往期”。三种状态都会公开展示，想下线一个赛季就把它从档案库 catalog 移除后重导入。
- **弈子 URL 用 id 不用名字**（存在同名弈子，如 s17 的多形态厄运小姐）。旧的 S18 名字 URL 会 301 到 id URL。
- **“新弈子”徽章**：档案库中弈子 `tags` 含 `"new"` 时展示，导入后自动生效（S16.5 的 14 个新增弈子已打标）。
- **机制 tab**：档案库 `mechanics/` 中注册的每种玩法在页面上是一个独立 tab。`kind=wand` 用法杖卡片（无图），其余 kind（god、monster 及未来新增）用通用机制卡片（支持图片、神明阶段/祈愿）。新增机制种类无需改代码。
- **模拟器补充数据**：档案库覆盖不到的条目（刷新道具、锻造器等特殊道具与召唤物）放在 `static/tools/lineup-simulator/extras/<season_id>.json`（`{"equips": [...], "pets": [...]}`），构建时原样追加。后续这些数据补进档案库后可删除对应 extras。
- **缓存**：列表页对 `index.json` 的请求带 `?v=<version_id>`，档案库版本号变化即自然失效。服务端 `season_reference_service` 用 `lru_cache` 缓存，重导入数据后需重启进程（测试可调 `clear_caches()`）。
- 通用页面的 CSS 类名保留历史 `s18-` 前缀（`season-reference.css`），避免大规模改名回归；新增样式请用中性命名。
