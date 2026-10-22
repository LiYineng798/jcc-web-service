# 大橘大利创作者工具

入口 `/tools/orange-fortune-creator`，工具箱与通知目标目录统一在 `toolbox_service.py` 登记。
输出固定为竖向 3:4、1200 × 1600 PNG，包含三张时间卡片、卡片完整效果、阵容站位、装备、基础羁绊、卡组名字和可选的署名、传送门、计划目标、能量与运营手记。

## 数据与规则

`orange_creator_service.py:creator_config()` 是只读适配层；页面初始数据与 `/api/tools/orange-fortune-creator` 共用它，`schema_version=1`。当前使用随代码交付的卡片档案，不在请求过程中访问官方 CDN，不新增数据库表。

- 卡片来自现有 `orange_fortune_service.catalog()`，卡图复用本地文件和五档 SVG 金属包边。缺图保留明确占位，不替换成其他卡片。
- [官方卡片 CDN](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/card.js) 的快照与本地 200 条记录一致。该文件仅含 `id/iRarityTier/sName/sIcon/sTags/sArgs/sDesc`，没有卡片能量字段。
- 同目录的 [模式总配置](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/config.js)、[弈子](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/chess.js) 和 [装备](https://game.gtimg.cn/images/lol/act/jkzlk/js/16/18.18.1-S400001/equip.js) 可公开读取；在这些已核对的文件里没有找到可关联卡片 ID 的能量字段。不能据此断言其他官方接口也不存在。
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

背景使用可编辑 SVG 几何与 CSS 遮罩，不使用图像生成模型或 AI 位图。四种材质分别为曜石鎏金（雕刻星盘）、翡翠棱镜（六边形玉石切面）、星轨紫晶（轨道与星点）、象牙烫金（放射金箔与纸纹）。矢量源文件为 `static/tools/orange-fortune/creator/material-{gilded,jade,astral,ivory}.svg`；没有内嵌位图或外部资源，可直接修改色值、路径与渐变。

背景的中部保持低对比度，装饰集中在页角和边缘。卡面、弈子、装备和羁绊仍复用现有资料库素材；背景不冒充官方插画。原有背景 ID 保持不变，已有草稿可自动使用新的材质。
