# 阵容模拟器数据更新说明

阵容模拟器运行时直接读取赛季资料库：

```text
static/season-data/catalog.json
static/season-data/<season_id>/champions.json
static/season-data/<season_id>/traits.json
static/season-data/<season_id>/items.json
```

不要手工修改 `static/tools/lineup-simulator/data/`，也不要再运行旧的 `scripts/build_simulator_data.py` 或把 `local-data.js` 当作数据源。上述目录是旧模拟器的兼容存档，不参与当前页面加载。

## 更新流程

1. 在外部档案库 `ccmax资料/数据模版` 抓取或维护新的完整版本。
2. 在档案库执行 `python scripts/validate.py --all`。
3. 在 Web 仓库根目录导入单个赛季：

   ```powershell
   python scripts/season_library/import_from_archive.py --season s17
   ```

   找不到档案库时，通过 `--source "D:\...\ccmax资料\数据模版"` 或 `JCC_SEASON_ARCHIVE` 指定。
4. 检查 `static/season-data/catalog.json` 和对应赛季 `index.json` 的 `version_id`，确认 WebP 生成没有警告。
5. 运行：

   ```powershell
   python -m pytest -q tests/test_season_reference.py tests/test_lineup_simulator_rebuild.py
   ```

完整的数据结构、图片规则、缓存、部署和回滚说明见 `docs/season-library.md`。

## 旧构建器

`scripts/season_library/build_simulator_from_library.py` 及其 `static/tools/lineup-simulator/data/`、`webp/`、`blur/` 输出仅为历史兼容文件。当前模拟器不会请求这些文件，日常赛季更新无需同步它们。若确认没有其他外部使用者，可在单独的清理变更中删除旧构建器和旧产物。
