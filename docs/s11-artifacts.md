# S11 全神器装备推荐

工具箱的 S11 分组链接到 `/tools/s11-artifacts`。这是独立的 Web 静态攻略，不新增数据库结构。

`scripts/season_library/sources/s11-artifacts.json` 保存五张参考图逐项核对后的 31 件神器、效果文案与 124 个推荐位置。弈子费用同时与 18.11.1 档案核验。注意霞与艾瑞莉娅、拉露恩与索拉卡的头像区别；黎明核心按参考图收录，虽然档案将它归为特殊装备。

运行以下命令重建快照，参数必须指向 S11 的 18.11.1 版本目录：

```powershell
python scripts/season_library/import_s11_artifacts.py --source 'D:/档案/data/seasons/s11/versions/18.11.1'
```

生成器验证版本、费用和图片路径，把 31 张装备图与 37 张弈子头像原样复制到 `static/s11-artifacts/`。`provenance.json` 保存源文件和每张图片的 SHA-256（攻略文本统一换行为 LF 后计算，兼容 Windows/Linux 检出）；部署时只需本仓库。效果文案以参考图为准，普通资料库的版本发布、隐藏或替换不会改变攻略。

页面由 `s11_artifacts_service.py` 读取固定快照，Jinja 渲染全部文本。查询参数 `q` 匹配神器、效果、弈子及常用别名；空白分词取交集。`cost` 筛选至少包含一位指定费用弈子的神器，保留每件神器的完整推荐名单。原生 JS 提供即时查询、中文输入法支持、头像反查、重置与分享 URL；禁用 JS 后仍可用 GET 表单查询。查询结果页设置 noindex，规范链接指向主攻略页。

费用颜色在页面自己的 CSS 中定义：5 费 `(234,138,56)`、4 费 `(229,86,188)`、3 费 `(90,132,214)`、2 费 `(84,157,82)`、1 费 `(131,130,134)`。2 费按参考图取绿色。页面继承主站导航和主题状态；独立的 SVG 山景、纸纹与 CSS 烫金字不加载外部字体或现有烫金页面的样式。

验证命令：

```powershell
python -m pytest -q
node --check static/s11-artifacts/app.js
node tests/s11_artifacts_rendering.cjs
git diff --check
```

浏览器脚本需要 Playwright 与 Chromium/WebKit，并通过 `NODE_PATH` 找到依赖。先在独立 worktree 启动 `python tests/serve_s11_artifacts_preview.py`；默认预览端口为 5171，可用 `S11_ARTIFACTS_PREVIEW_PORT` 调整。
