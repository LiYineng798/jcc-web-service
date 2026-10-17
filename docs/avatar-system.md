# 参数化头像

## 数据与兼容

`users.avatar_color` 保留，增加 `avatar_preset`、`avatar_expression`。公开用户返回
`avatar_config={version:1,preset,expression,color}`，阵容返回 `owner_avatar_config`；旧颜色字段保留。
只接受八个预设（strobi/freddy/citrus/nova/sunee/cloudee/sprout/bloom）、八个默认表情
（neutral/happy/wink/sleepy/curious/surprised/shy/determined）和六位 HEX。
`PUT /api/me/avatar` 接受完整 `{color,preset,expression}`，旧 `{color}` 仅改颜色。

生产按序应用 DB `0018_avatar_config.sql`、`0019_avatar_preset_expansion.sql`、`0020_avatar_expression_expansion.sql`，再部署 Web。迁移只给缺失的新参数随机赋值，
不重置约 400 名既有用户的颜色，不产生图片文件；迁移系统记录已应用版本。
0019/0020 仅扩充形象/表情 CHECK 允许值，不重分配已保存的头像。
SQLite 在 bootstrap 前补字段，并且回填幂等。已有四款 CHECK 的本地数据库在 savepoint 内复制并替换单个形象/表情列，
不重建 users 表，保留用户 ID、关联记录及索引；要求 SQLite 3.35+（支持 DROP COLUMN）。
注册、后台创建和 bootstrap 均一次随机完整配置。推荐色为陶杏、苔绿、雾蓝、烟紫、豆沙、砂岩、青瓷、石墨，
旧用户已保存的颜色仍按原值渲染，不随推荐色更新。
现有颜色足够深或浅时，渲染器自动选择白/深色眼睛，无需用户额外配置。

## 渲染与反馈

使用固定版本 `@bible-strong/avatar-core`、`@bible-strong/avatar-web` 0.1.0。
提取上游 Strobi/Freddy/Citrus/Nova/Sunee/Cloudee 的几何参数和七组表情，并加入本地设计的新芽 Sprout、花语 Bloom；不搬入编辑工作室。
各形状有独立视觉画框，按轮廓密度和视觉重心校准大小；静态 SVG 和动画 SVG 使用相同 viewBox，太阳射线、叶片和耳朵不会因切换动画被裁切。
画框配置由 `scripts/maintenance/import_avatar_presets.py` 生成；调整后检查全部保存表情与三类反馈的边界，不直接改生成的 JSON。
首页作者栏保留固定 28px 占位，以昵称行中心对齐；昵称省略规则不再作用于头像内部 span。
数据来源、提交版本和改动记录在 `frontend/avatar-presets.NOTICE.txt`。

`npm ci --prefix frontend`，然后 `npm run build --prefix frontend`，提交构建产物及 notices。
头像入口为 `frontend/avatar.ts` → `static/avatar-lab/app.js`，不需要单独 React 根。
普通状态是 SVG data URL 图片；128 项有界内存缓存按预设/颜色/表情复用，尺寸共用同一矢量图。
不运行全列表 idle 动画，不为每个头像请求服务器，不上传用户图片。

只有复制/点赞/收藏成功后创建运行库动画控制器；1700ms 后回到保存表情，过渡完成销毁控制器。
复制使用轻点头，点赞使用上扬回弹，收藏使用抬升停留；头像本体动作约 820–1100ms，
只保留头像自身的动作与临时表情，不叠加外围光圈或确认标记。占位尺寸不变，只变换绘制层，避免挤动昵称和卡片。
剪贴板成功即反馈，不依赖统计请求；点赞/收藏失败及取消收藏不播放成功反馈。列表以 lineup ID 复用正在反馈的节点，
刷新不重启动画；重复操作从当前绘制层姿态衔接，取消上一组 Web Animations 并重新计时，同一种临时表情不重复打断正在进行的形变。离开 DOM、隐藏页面会终止全部动画；
reduced-motion 只切换静态表情，不执行缩放或位移。
普通首页卡片的即时成功操作由头像和按钮状态确认，不重复弹出成功通知；失败、登录引导和登录后代执行结果仍明确提示，实时榜单及其他页面不受影响。
所有小尺寸头像及个人中心/后台/作者页使用同一配置，实时榜单的弈子图片不受影响。

## 编辑器与加载占位

编辑弹窗使用「形象 / 表情 / 配色」选项卡，支持方向键及 Home/End 切换。
桌面左预览、右设置；手机使用紧凑横向预览。预览、页签和保存栏保持可见，只有当前设置区域滚动。
依据 visualViewport 缩减弹窗高度，短屏/软键盘出现时进一步压缩预览；不在弹窗内显示源码署名链接，
首页及独立 `/avatar-source` 页面仍保留源码入口。
每个形象提供三种推荐配色缩略图，切换形象不会自动改掉当前颜色；全部八色与自定义 HEX 仍可自由选择。
编辑器的随机组合从对应形象的推荐色中选取，不改变注册随机逻辑或既有用户配置。
预览区在桌面和手机都显示 28px 头像与当前昵称；复制、点赞、收藏预览同时作用于大头像和实际尺寸样例，切换配置或关闭弹窗立即清理动画。
选中项以单层细边框、浅底色和字重区分，不叠加多层强调。
普通阵容加载骨架匹配标题、等级、28px 作者头像、时间、阵容码、复制按钮和底部互动区域；
手机复制区与工具区跟随真实卡片换行。骨架加载时以内容确定高度，显现后切换为裁切叠层，避免固定高度残留。
实时榜单骨架、缓存命中及保留旧内容的刷新逻辑不变。

## AGPL 与源码交付

用户已选择直接采用 AGPL-3.0-only 上游。运行库不是 MIT，不能只保留一个署名就视为完成授权。
`/avatar-source` 提供完整许可证链接和本版本对应源码下载入口；本次集成新增代码按 AGPL-3.0-only 提供。
不要把上游项目链接当成你部署的修改版对应源码。

生成本地源码包（需已审查的 Web/DB 工作树与固定上游源码目录）：

```powershell
python scripts/maintenance/build_avatar_source.py --db-source <DB仓库路径> --upstream <上游源码路径>
```

输出 `instance/avatar-source/source.zip`，通过 `/avatar-source/download` 提供，无需登录。
打包包含 Web/DB 源码、构建脚本、锁文件、上游 core/web 源码及许可证，排除凭据、运行资料、
用户数据库、游戏素材和生成赛季数据。**发布前必须检查包内容、第三方素材边界、上游源码与 npm
版本对应关系，以及源码是否覆盖实际部署的组合软件。** 该辅助工具不是法律合规认证。
生产更新集成代码/依赖/构建配置后必须重新生成源码包并随部署更新；不提供包时页面明确提示未准备完成。
不要把整个 `instance/`、`.env` 或私有赛季包加入源码包，也不要在未审查时公开仓库。

## 本地验证

在独立干净 worktree 中执行，不使用线上数据库。

```powershell
python -m pytest -q
npm run build --prefix frontend
python tests/serve_avatar_preview.py
# 另一个终端
python tests/avatar_lab_rendering.py
python tests/avatar_gallery_rendering.py
python tests/avatar_compact_rendering.py
python tests/avatar_lab_performance.py
# 无需启动预览服务，真实首页模板/脚本 + 拦截的测试 API：
python tests/avatar_feedback_rendering.py
python tests/avatar_lab_performance.py --offline
```

预览仅监听 `127.0.0.1:5148`，使用虚构数据。`/__preview__/login/user` 本机快捷登录，
`/me#avatar` 打开编辑器。调试路由仅在预览脚本注册，不进入正式应用。
截图与浏览器结果存放 `instance/avatar-review/`，不提交。
SQLite 和浏览器验收不能代替真实 PostgreSQL 迁移演练。
