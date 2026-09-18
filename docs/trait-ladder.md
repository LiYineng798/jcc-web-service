# S18 羁绊天梯计算器

入口为工具箱 S18 下的 `/tools/s18-trait-ladder`。仅 Web 变更，无数据库迁移。

## 资料与规则

`trait_ladder_service.py` 通过 `season_data_repository` 读取当前 release 的弈子、羁绊、装备与图片，复用模拟器的人口及额外贡献文本规则。两个资料入口均隐藏时不向页面发送赛季数据，奖励仍可阅读。

拉克丝只保留一个可选弈子，九种形态从资料中的对应变体生成；指定形态贡献 2，不能重复登场多个形态。卡兹克的四种进化分别去重，指定形态或进化会锁定对应弈子。远古巨龙占两个人口、贡献两个峡谷野怪。日月双蚀按日/月各 3 的条件激活。

天梯计分沿用用户提供 HAR 中参考计算器的口径：排除单档和 unique 羁绊；单档日蚀骑士、日月双蚀、帝王斑蝶等可展示但不计分。这是参考工具口径，不把羁绊的显示颜色当成唯一性依据，仍需结合实际游戏确认版本差异。

转职先参与候选评分，最终通过容量匹配分配到具体弈子：原生/已进化的同名羁绊不能重复贡献，一名弈子最多三个不同纹章，无合法分配的方案会被排除。高费核心定位是本工具按当前弈子设定的筛选标签，不是官方字段，也不是装备或战力模拟。

## HAR 解析范围

本地解析到 `TraitTrackerS18View` 的预计算阵容、候选搜索、人口规则、拉克丝重复计数、螳螂进化、单档排除、纹章计数及 `/tracker/s18/solve` 请求协议。HAR 不包含该服务端求解器源码；本工具独立实现有限候选搜索，没有调用第三方接口，也没有复制整个页面脚本。

阶段奖励来自 HAR 中 `bootstrap` 脚本的 `羁绊天梯` 字面量，含 2～14 羁绊共 13 档。图标从同一 HAR 的图片响应中提取为本地资源，展示名称及数量角标（金币角标表示金币总量）。用以下命令重新生成 JSON 与图片，不手改生成文件：

```powershell
python scripts/season_library/import_trait_ladder.py <本地HAR路径>
```

导入器仅解析 JSON 兼容字面量，不执行抓包脚本；HAR 的请求头、账号数据和整个脚本不提交。生成快照保留 SHA-256 与提取日期。参考站与本站存在命名差异，奖励快照没有补丁号，不视作当前官方奖励校验。本站官方强化名称为“拼盘天梯”。

## 搜索与交互

`static/trait-ladder/engine.js` 提供纯规则校验与确定性 beam search，最多保留 600 条中间路径，按有效羁绊数、费用排序，输出至多 12 个合法方案。有限搜索不保证全局最优，未找到结果不等于无解。Web Worker 避免主线程阻塞；修改任何计算条件会终止旧 Worker 并清空旧结果，避免误读过期方案。

UI 直接继承主站 `styles.css` 的主题变量，不覆盖强调色。弈子费用边框保留游戏语义色。阶段奖励服务端渲染，计算依赖 JavaScript 和 Worker。

## 验证与预览

```powershell
python -m pytest -q
node --check static/trait-ladder/app.js
node --check static/trait-ladder/engine.js
python scripts/maintenance/check_deploy_safety.py
git diff --check
```

`tests/test_trait_ladder.py` 调用 Node 规则测试，覆盖双倍贡献、重复弈子、进化、巨龙人口、合法纹章分配、禁用/必选/高费条件、组合羁绊，以及小规模穷举对照。

预览复用现有隔离 SQLite 辅助入口，在干净 worktree 执行：

```powershell
$env:OPENINGS_PREVIEW_PORT='5128'
python tests/serve_lucky_openings_preview.py
# 打开 http://127.0.0.1:5128/tools/s18-trait-ladder
```

安装 Playwright 测试依赖并设置 `NODE_PATH` 后运行 `node tests/trait_ladder_browser.cjs`。可用 `LADDER_PREVIEW_URL` 指向其他端口。测试涵盖 Chromium/WebKit 深浅主题、手机宽度、键盘、奖励切换、取消、输入错误和资源加载；桌面 WebKit 不等于真机 Safari。
