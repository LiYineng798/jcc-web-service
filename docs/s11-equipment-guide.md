# S11 全弈子推荐出装

页面 `/tools/s11-items` 使用独立静态快照，不读取赛季发布指针或外部档案。
推荐清单的编辑源是 `scripts/season_library/s11_recommendations.tsv`（60 位弈子，霞/洛分别列出）。
图片、羁绊与合成配方固定取自 S11 `12.4.14`，按原字节复制，哈希记录于工具目录的 `asset-manifest.json`。

仅重新制作时需要外部档案：

```powershell
python scripts/season_library/import_s11_recommendations.py --archive "D:/1/codex/jcc-new/ccmax资料/数据模板/data/seasons/s11/versions/12.4.14"
```

提交生成的 `static/tools/s11-items/` 与清单、生成器；不手改生成 JSON 或图片。
日常运行只需 Web 仓库，资料库隐藏、更新或切换版本不影响此工具。
旧 S8 三个工具撤下桌面/手机工具箱与 sitemap 入口；原路由、模板和图片继续保留供旧链接访问。
