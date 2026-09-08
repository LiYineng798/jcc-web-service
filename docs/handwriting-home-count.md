# 首页手写阵容总数

首页 `#lineupCount` 继续读取 `/api/home-stats` 的 `total_public_lineups`，仅改变显示方式，不改变统计口径、当前列表数量或数据库。没有后台调参入口，以下参数在源码中修改。

字形来自本地 Shadows Into Light 字体的 SVG 轮廓。动画沿字形轮廓描边，再渐显填色，不是真实手写笔顺。同一数字重复渲染不重播，数字变化时重播。减少动画模式直接显示最终字形；数字脚本缺失时保留文字。屏幕阅读器读取隐藏的数字文本，SVG 本身不重复朗读。

## 外观参数

在 `static/handwriting-count.css` 中修改：

| 参数 | 当前值 | 效果 |
| --- | --- | --- |
| `#lineupCount` 的 `font-size` | `3.5rem` | 整体大小；增大更醒目，但占用更多卡片空间 |
| `#lineupCount` 的 `color` | 继承主题 | 添加此属性可同时改变描边和填色；固定颜色需要分别考虑深浅主题 |
| `.handwriting-count-fill` 动画时长 | `.45s` | 增大让填色更缓慢、更柔和 |
| `.handwriting-count-fill` 动画延迟 | `1.13s` | 增大让轮廓保持更久才填色 |
| `ease-out` | 描边及填色均使用 | 起步快、收尾慢；`linear` 改为匀速变化 |

在 `static/handwriting-count.js` 中修改：

| 参数 | 当前值 | 效果 |
| --- | --- | --- |
| SVG `stroke-width` | `1.6` | 增大使轮廓更粗，最终也更厚；过大会挤小 0、6、8、9 的内部空隙 |
| `glyph.advance + 3` 中的 `3` | `3` | 数字之间的额外间距；增大更疏朗，整体更宽 |
| `animationDelay` 的首项 | `.05` 秒 | 整体起笔等待时间 |
| 两处动画公式中的 `1.5` | `1.5` 秒 | 控制轮廓依次出现的节奏，应一起调整；增大整体更慢，也应配合调整 CSS 填色延迟 |
| `animationDuration` 中的 `2.4` | `2.4` | 每条轮廓持续时间的倍数；增大让更多相邻轮廓同时描绘 |

注意：CSS 中描边的 `1s` 被 JS 设置的行内 `animationDuration` 覆盖，单独修改它不会改变正常渲染速度。SVG 数字间距由 JS 的位移计算决定，CSS `letter-spacing` 不控制 SVG 字距。

`viewBox`、JS 宽度公式和 CSS SVG 高度共同决定画布比例与留白，通常只调 `font-size` 即可，不建议单独修改其中一个比例常量。换 TTF 或 `font-family` 只改变文字降级时的字体；要替换实际 SVG 手写字形，需要重新生成 `handwriting-digits.js` 中的 `path` 和 `advance`，并保留相应字体许可。

## 验收与复现

- `python -m pytest -q`：Web 服务全套测试；`tests/test_handwriting_count.py` 验证首页脚本顺序及静态资源可访问性。
- 在隔离 Flask 预览运行后执行 `node tests/handwriting_count_rendering.cjs`，可通过 `PREVIEW_URL` 指定地址，默认 `http://127.0.0.1:5093`；需在 `NODE_PATH` 配置 Playwright。
- 浏览器测试覆盖 Chromium/WebKit、320/390/768/1280 宽度、深浅主题、数字不变不重播、全部十个字形、零值、减少动画、非数字与资源失败降级、布局溢出及 JS 异常。
- 浏览器测试仅拦截首页统计响应为固定验收数字，不修改业务数据库。截图写入忽略的 `instance/handwriting-acceptance/`。已人工检查手机浅色与桌面深色截图。WebKit 自动化不等同于真实 iPhone Safari 设备验收。
- 本功能无需数据库迁移或新环境变量。部署按现有约定保证新静态资源可读，且保留字体的 `OFL.txt`。
