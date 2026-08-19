# 阵容模拟器数据更新说明

阵容模拟器运行时直接读取赛季资料库：

```text
static/season-data/catalog.json
static/season-data/<season_id>/champions.json
static/season-data/<season_id>/traits.json
static/season-data/<season_id>/items.json
static/season-data/<season_id>/board_units.json
static/season-data/<season_id>/augments.json   # 已上线赛季
```

不要手工修改 `static/tools/lineup-simulator/data/`，也不要再运行旧的 `scripts/build_simulator_data.py` 或把 `local-data.js` 当作数据源。上述目录是旧模拟器的兼容存档，不参与当前页面加载。

## 更新流程（新版本 / 新赛季上线）

1. **确认官方版本**：抓 `https://game.gtimg.cn/images/lol/act/jkzlk/js/config/versiondataconfig.js`，看目标 mode 的 `is_newest_version` 与版本条目。官方数据源总览、命名对应表与踩坑清单见档案库 **`ccmax资料/数据模板/docs/官方数据源与版本更新指南.md`**。
2. **档案库导入**（在 `ccmax资料/数据模板` 执行）：`python scripts/import_existing_seasons.py --season s18 [--version X.Y.Z]`（S18 默认走官方接口；带 `--s18-json` 才重建 PBE 快照）。
3. **档案库校验**：`python scripts/validate.py --all` → 0 错误。
4. **Web 仓库导入单个赛季**：

   ```powershell
   python scripts/season_library/import_from_archive.py --season s18
   ```

   找不到档案库时，通过 `--source "D:\...\ccmax资料\数据模板"` 或 `JCC_SEASON_ARCHIVE` 指定。资料库与模拟器共用 `static/season-data/`，一次导入两边生效。

5. **核对清单**：
   - `catalog.json` 与 `index.json` 的 `version_id` / `game_version` / `status` 正确。
   - 控制台没有缺图警告，`optimized_local_path` WebP 全部生成。
   - `board_units.json`：期望的羁绊棋盘对象（如 S18 的威朗普/石皮树/生命花/深林守卫）都在 `included`；`discovery_audit` 无意外的新增 `review` 项。
   - 多形态弈子（如 S18 拉克丝 9 皮肤形态）按形态逐条出现在 `champions.json`，各自带正确 `trait_ids`。
   - 装备分类是数据驱动的：某分类（如消耗品）本赛季没有装备就不显示，属正常。
6. **测试**：

   ```powershell
   python -m pytest -q tests/test_season_reference.py tests/test_lineup_simulator_rebuild.py
   ```

7. **部署**：JSON 与图片作为同一批静态资源上传，重启 Web 进程（清 `lru_cache`），冒烟检查资料页与模拟器。

完整的数据结构、图片规则、缓存、部署和回滚说明见 `docs/season-library.md`。

装备分类标签由当前赛季 `items.json` 动态生成：某分类至少有一件装备时才显示。新增赛季只需填写标准 `category`，不要在前端增加赛季 ID 判断或固定标签开关。

## 旧构建器

`scripts/season_library/build_simulator_from_library.py` 及其 `static/tools/lineup-simulator/data/`、`webp/`、`blur/` 输出仅为历史兼容文件。当前模拟器不会请求这些文件，日常赛季更新无需同步它们。若确认没有其他外部使用者，可在单独的清理变更中删除旧构建器和旧产物。
