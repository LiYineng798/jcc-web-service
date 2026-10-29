# 大橘大利创作者工具

入口 `/tools/orange-fortune-creator`，工具箱与通知目标目录统一在 `toolbox_service.py` 登记。
输出固定为竖向 3:4、1200 × 1600 PNG，包含三张时间卡片、卡片完整效果、阵容站位、装备、基础羁绊、卡组名字和可选的署名、传送门、计划目标、能量与运营手记。

## 数据与规则

`orange_creator_service.py:creator_config()` 是只读适配层；页面初始数据与 `/api/tools/orange-fortune-creator` 共用它，`schema_version=1`。当前使用随代码交付的卡片档案，不在请求过程中访问官方 CDN，不新增数据库表。

- 卡片来自现有 `orange_fortune_service.catalog()`，卡图复用本地文件和五档 SVG 金属包边。缺图保留明确占位，不替换成其他卡片。
- [官方卡片 CDN](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/card.js) 2026-10-28 快照共 201 条，仍只含 `id/iRarityTier/sName/sIcon/sTags/sArgs/sDesc`，没有卡片能量字段。
- 版本目录为该分支列出的 16 个接口（含[模式总配置](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/config.js)、[弈子](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/chess.js)、[装备](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/equip.js)）2026-10-29 均可读取；其中没有引用卡片 ID 的字段，也没有卡片能量字段。不能据此断言未列出的官方接口也不存在。
- 官方 `chess.js` 可展示的 1–5 费弈子有 120 个名字，复用的 `s16_5` 资料为 114 个；伊泽瑞尔、努努和威朗普、斯莫德、艾瑞利娅、迦娜、阿木木尚不能在编辑器中放置，需经赛季资料流程接入。
- [官方开发者说明](https://www.bilibili.com/opus/1257412011649662993)确认三张卡的局前构筑、稳定传送门能量上限 8，以及由前七逐步挑战前五、前三和登顶的局内目标。页面的“计划目标”表达创作者意向，不是开局硬性门槛。
- 卡片星级不能当成能量。当前 `cards[].energy=null`，可手填总能量并明确标注；稳定传送门手填超过 8 时阻止导出。不标注能量不代表游戏内合法性认证。
- 高级队列名称和上限不猜测。用户可以选“其他传送门”自填名字。
- 阵容编辑复用既有英雄联盟传奇 `s16_5` 公开模拟器资料，卡片专属变身、额外羁绊及经济效果不会自动改写基础阵容计算，可写入手记。模式专属资料须经赛季资料生成与发布流程接入，不把官方 `S400001` 直接当成站内赛季 ID。

## 模拟器边界与草稿

`/tools/lineup-simulator?creator=orange-fortune` 由服务端识别并绑定 `CREATOR_SEASON`，保留模拟器开关与赛季展示权限；该赛季隐藏后不回退到其他赛季。配置接口不暴露隐藏赛季素材。

创作者通过同源 iframe 复用弈子、装备、拖动、撤销/重做、阵容码导入等交互。编辑器仅向同源父页面发送 `jcc:orange-formation`（版本 1）的只读显示快照。父页面同时验证 origin、source、版本及赛季；错误通过独立消息显示重试。

- 卡组文字和选卡存于 `jcc-orange-creator-v1`。
- 阵容存于 `jcc-orange-formation-v1:<season_id>`。
- 普通模拟器仍使用 `jcc-simulator-v2:`；两个工具不覆盖彼此草稿。
- 不向服务端写入用户创作内容。浏览器存储失败时仍可继续编辑导出，但会显示无法保存。

## 后续更新

卡片更新沿用 [卡片导入流程](orange-fortune.md#更新)，不能手改生成的 JSON。规则、模式绑定和背景选项集中在适配层。获得有来源的能量资料后，按卡片 ID 填充 `cards[].energy`；前端对三张已知能量自动求和并切换为自动标注。保留未知值为 null，不默认补零。

包边模板仍使用资料库的 `fortune_card_bezel.html` 与 `fortune_frame_materials.html`。导出克隆包含渐变定义；图片使用同步解码，并为 WebKit 按嵌入图片数重绘 SVG，避免连续导出时漏图（参见 [html-to-image 问题记录](https://github.com/bubkoo/html-to-image/issues/420) 和 [modern-screenshot 的绘制策略](https://github.com/qq15725/modern-screenshot/blob/main/src/image-to-canvas.ts)）；导出时将根定位恢复为 static，防止浏览器计算出的逻辑 inset 把 SVG 内容移出画布。

聚焦验证：`python -m pytest -q tests/test_orange_creator.py`；浏览器验证：启动隔离预览后设置 `CREATOR_PREVIEW_URL`，运行 `node tests/orange_creator.browser.cjs`。浏览器依赖与截图隔离约定见 [开发与验证](development.md)。

## 竖版排版与背景素材

导出提供攻略版（启动节奏、装备优先、运营手记）和纯构筑版（扩大卡面与效果区，不生成运营区）。切换版式保留已填写文字，兼容旧版草稿。棋盘为规则尖顶六边形：宽 100、高 200/√3，列间距 106，行距 106√3/2，偶数行横向偏移 53。羁绊快照携带模拟器计算的 `frame`，复用 `ui/{1,2,3,4,unique}.svg`，不重新推断羁绊档位。

六种材质分别为曜石鎏金（雕刻星盘）、翡翠棱镜（六边形玉石切面）、星轨紫晶（轨道与星点）、象牙烫金（放射金箔与纸纹）、人文手札（奶油纸色、蓝墨方格与手绘圈线）和蓝绒藏典（蓝色织物书封与古铜雕饰）。全部使用本地 SVG 与 CSS，无生成式位图、内嵌图片或外部资源。矢量文件为 `static/tools/orange-fortune/creator/material-{gilded,jade,astral,ivory,editorial,folio}.svg`。蓝绒藏典由 `python scripts/build_folio_material.py` 重建：手绘路径描述卷叶护角，两组贝塞尔曲线构成边角交错暗纹，重复经纬线与固定种子的 SVG 噪声表现织物；修改时先改脚本再重建 SVG。`orange-creator-finish.css` 叠加配色、边框和卡面质感，不改变海报内容几何。装饰为静态效果，预览与导出保持一致，不阻止手机滚动。

## 图片保存

生成 PNG Blob 后通过 `static/poster-save.js` 展示保存面板。桌面保留自动请求下载；触屏设备通过新的点击调用文件分享，避免图片生成期间丢失浏览器的临时用户激活。只有 `navigator.canShare({files})` 确认支持才显示分享按钮。取消或拒绝分享保留图片、下载链接与原图入口；不把分享调用成功等同于写入相册。无文件分享能力的浏览器可以长按图片保存。

当前结果的 Blob URL 在关闭面板后保留，替换结果后延迟释放旧 URL，避免中断下载。文件名与内容在开始生成时取快照。`tests/poster_save.browser.cjs` 验证点击激活、取消、拒绝和下载；真实手机相册与内置浏览器的保存行为仍需真机验证。

背景的中部保持低对比度，装饰集中在页角和边缘。卡面、弈子、装备和羁绊仍复用现有资料库素材；背景不冒充官方插画。原有背景 ID 保持不变，已有草稿可自动使用新的材质。

人文手札的刻度、纸面胶带和箭头保存在 `material-editorial.svg`；研究室页眉、圆印与侧边批注由 `.fp-editorial-marks` 叠加在页边空隙中，不参与正文排版。装饰标记对辅助阅读隐藏，布局检查同时验证其与标题、元信息及正文不重叠。

海报标题与卡名使用由模拟器本地思源宋体生成的固定 600 字重字体 JCC Editorial Serif，规避 WebKit 导出可变字体时字重回落的问题。可用 `python scripts/build_creator_font.py` 离线重建（需 fonttools[woff]）；源文件不变，衍生字体重命名并随附 OFL 授权于 `static/tools/orange-fortune/creator/fonts/LICENSE.txt`，正文与棋盘使用无衬线字体。导出嵌入字体数据并在当前页面缓存，避免下载图片回退到系统字体。羁绊使用固定图标列、等宽数量列与名称列，图标和文字垂直居中；单、双位数量不改变名称起点。字体与羁绊对齐可运行 `node tests/orange_creator_typography.browser.cjs` 验证。

## 工作台布局

桌面使用两列设置区与右侧预览；卡片选择和阵容入口在同一区域，导出状态、按钮与草稿状态集中在底部工具栏。常见桌面窗口中全部设置同时可见，无需滚动页面。

预览使用容器实际高度计算缩放，不依赖整页高度估算；较矮桌面使用紧凑间距，选满卡片和攻略表单均需保持在底栏分隔线以上。工作台检查覆盖已选三张卡片的攻略版与纯构筑版。

宽度不超过 980px 时，用页内按钮切换档案、卡片与阵容、海报内容和背景材质，表单内容保留。窄屏的“查看海报”使用原生对话框，关闭或按 Escape 后回到编辑入口；导出不依赖预览是否打开。极短窗口与软键盘场景允许页面增长，避免裁切输入项。

棋盘的空状态提示层为透明背景，保留六边形格子。工作台尺寸不改变海报本身的 1200 × 1600 导出布局。可运行 `node tests/orange_creator_workspace.browser.cjs` 验证多个窗口尺寸、错误提示、透明棋盘及预览键盘流程。

无传送门、计划目标与能量信息时，海报隐藏空信息行并放大标题；中长标题分档缩小，右侧品牌标识在页头垂直居中。羁绊从棋盘右侧区域的左上角排列，保留八行容量。`node tests/orange_creator_layout.browser.cjs` 使用模拟器实际配置十名弈子，验证八项激活羁绊及两种版式，并将示例 PNG 输出到忽略的 `instance/creator-review/`；示例用于排版检查。
