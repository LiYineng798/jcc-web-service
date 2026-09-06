# Safari 棋盘弈子图片裁剪修复

用户在 iPhone Safari 首次打开棋盘时看到弈子图片底部提前结束、露出费用边框底色；实时阵容详情和模拟器都有反馈。桌面 Chromium 和 Windows WebKit 的移动视口未复现原始真机异常，因此不能将自动化通过等同于 iPhone 真机确认。

两处原实现都将 `clip-path` 直接应用到 img，并与父层 `drop-shadow`、图片自身零位移 3D transform 组合使用。本次统一为费用边框外层 → 3px 内缩裁剪容器 → 普通满尺寸 img 和渐变遮罩。图片不再单独裁剪或强制合成，不通过向下偏移补偿。姓名、星级、装备和坐标不变。竖版导出使用相同结构，裁剪内缩保持 4px。无效特殊单位保留警告标记和边框提示，移除肖像滤镜。

## 验证

- `python -m pytest -q`：544 passed。
- `node tests/board_portraits.browser.cjs`：Chromium / WebKit，桌面与 iPhone 13 移动视口均通过。校验图片加载、图片与裁剪区域四边重合、父层无滤镜、图片无独立 clip-path/transform、拖动/撤销，以及横版和竖版 PNG 实际下载。
- Playwright 通过 `PLAYWRIGHT_MODULE` 指向本地安装，`CHROMIUM_CHANNEL=msedge` 可使用 Edge。`BOARD_PREVIEW_URL` 默认 `http://127.0.0.1:5069`；需要本地预览样例 `/live-comps/s17-star-god/portrait-preview`。`BOARD_SCREENSHOT_DIR` 可选，用于保存截图和导出文件。
- 本地预览启动脚本在协调目录 `worktrees/safari_board_preview.py`，只使用独立 SQLite 和合成的实时阵容。截图在 `worktrees/safari-board-review/`。

真机复查：iPhone Safari 首次加载、刷新、横竖屏切换，两处棋盘图片应覆盖完整内六边形，底部不得提前露出宽色块。当前分支不包含数据库迁移。
