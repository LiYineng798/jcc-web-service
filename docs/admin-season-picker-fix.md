# 管理员赛季下拉菜单修复

## 范围与仓库

- 基线：Web `main` 的 `502fbd5`。
- Worktree：`D:\1\codex\jcc-new\worktrees\admin-season-select-fix`。
- 分支：`codex/admin-season-select-fix`；等待用户验收后再合并 main，未推送或部署生产。
- 仅修改 Web 前端；数据库服务及 PostgreSQL schema 无变更，无迁移、生产环境变量或构建依赖新增。
- Web 服务同时负责 Flask 页面、管理 API、上传任务、SQLite/PostgreSQL 适配；数据库仓库负责 PostgreSQL 迁移、导入、备份恢复。本问题发生在浏览器控件初始化阶段。

## 已复现的原因

### 实时阵容 → 数据上传 → 目标赛季

旧版 `activateTab()` 在切换工作区开始和结束各调用一次 `render()`。上传工作区原本没有需要等待的加载分支，因此两次渲染会连续完成。每次渲染又执行 `setTimeout(setupLiveUploadSeasonDropdown, 0)`。

两次延迟回调并不持有各自生成的元素，而是在执行时通过 `document.getElementById` 查找最新按钮。结果是**最后一个按钮被重复绑定两个 click 监听器**：一次点击先打开菜单，再立即关闭。

选择 JSON 文件的 change 回调只调用一次 `render()`，新按钮只绑定一个监听器，于是菜单又能打开。这里甚至不需要真正向服务器上传，单纯选择文件就足以改变表现。

### 阵容管理 → 批量导入 → 导入赛季

这里同样通过 `setTimeout` 初始化。第一次读取 `/api/lineup-seasons` 时，网络等待通常分隔了两次渲染，看起来正常；30 秒缓存有效时再次进入，异步函数立即返回，第二次渲染会在定时器执行前完成，于是再次给同一个按钮重复绑定。

这解释了“有时打不开”：表现取决于渲染/缓存时序。Chromium 和触控模式的 WebKit 都稳定复现，不能归因于 Safari 不支持下拉框。通知、解析完成等路径中的连续 `render()` 也会触发相同问题。

### 相关兼容性与生命周期问题

- 旧版批量导入用一个 `label` 包住触发按钮和整个菜单。改成独立 `label for=...`，去掉额外标签激活路径。标签激活由平台行为决定，参见 [HTML label 标准](https://html.spec.whatwg.org/multipage/forms.html#the-label-element)。本次没有把标签结构单独认定为用户报告的根因；重复绑定已有直接实验依据。
- 旧版每次初始化都增加 document click/keydown 监听，重绘后不清理。新组件用 AbortController 统一销毁，防止失效节点和监听器累积。
- WebKit 触控测试中，点击菜单外的普通标题未必生成 click，原本不能可靠收起。新组件同时处理外部 pointerdown、click 和焦点离开。

### 基线与修复后的实测

| 场景 | 修复前 Chromium / WebKit | 修复后 Chromium / WebKit |
| --- | --- | --- |
| 未选文件，进入上传并点击赛季 | false → true → false，最终关闭 | false → true，保持展开 |
| 选择文件后点击赛季 | 展开 | 展开 |
| 批量导入首次加载 | 展开 | 展开 |
| 缓存有效，再次进入批量导入 | false → true → false，最终关闭 | 展开 |

基线事件采样：本 worktree 的 `instance/season-picker-checks/before-fix.json`（忽略的本地验证输出）。

## 改动与效果

1. **同步挂载、单次绑定**：在 DOM 插入后初始化两个菜单。新模块 `static/admin/season-picker.js` 复用交互逻辑；每次重绘先清理旧组件，相同元素重复挂载也会先销毁。
2. **可靠获取赛季**：进入实时上传工作区时按原缓存策略加载管理员赛季列表；不用选择文件来触发初始化。普通导入仍只显示公开赛季，实时上传保留隐藏赛季用于上线前准备。
3. **表单状态保留**：切换赛季保留文件/粘贴文本，清除旧赛季预览；选择当前赛季不再无意义清除预览。实时上传同时重置旧预览进度。
4. **手机交互**：两个控件都使用独立标签，菜单宽度受表单约束，长列表在内部滚动，移动端触发按钮和选项至少 44px。
5. **键盘与无障碍**：方向键、Home/End、Enter/空格、Escape、Tab；明确的菜单/选中状态；切换导致 DOM 更新后焦点回到新触发按钮。菜单外点击、触碰文字或焦点移出均可关闭。

## 验证

- `python -m pytest -q`：666 passed（全量测试启动时的收集结果）。
- 新增路由/初始化回归检查另随相关用例执行：`python -m pytest -q tests/test_ui_routes.py tests/test_live_comp_upload_admin.py tests/test_admin.py`：131 passed。
- `node tests/admin_season_picker_rendering.cjs`（环境中需可解析 `playwright`）：Chromium / WebKit，320 / 390 / 1440px，深浅主题。验证首次/缓存命中/反复切换、文件与文本保留、实际预览请求中的赛季、批量导入写入、预览失效、键盘、外部触碰关闭、监听器销毁以及无横向溢出。
- 额外检查延迟赛季响应期间选择文件、失败预览后重试、实际后台 worker 发布完成后菜单可用、空赛季禁用状态。
- `node --check static/admin.js`、`node --check static/admin/season-picker.js`、`git diff --check`。
- 截图：`instance/season-picker-checks/{chromium,webkit}-{upload,import}-{light,dark}-{320,390,1440}.png`。输出仅用于本地验收，不提交运行时文件。

WebKit 自动化覆盖 Safari 所用引擎的相关交互；真实 iPhone Safari 的系统工具栏、系统输入法与具体系统版本仍需用户真机验收。本次未验证生产 PostgreSQL；没有修改数据库行为。

## 启动与验收

```powershell
cd D:\1\codex\jcc-new\worktrees\admin-season-select-fix
python tests/serve_admin_season_picker_preview.py
```

默认访问 `http://127.0.0.1:5115/__preview/login`，快捷登录只注册在这个独立验收进程中。普通登录也可使用 `previewadmin / Preview1234`。`/__preview/sample.json` 下载带本地图片引用的虚构上传样本。进程为验收创建临时 SQLite、赛季清单、上传目录和图片，并启动真实上传 worker；不会连接生产数据库。

需要手机同一局域网验收时，在启动前设置 `$env:ADMIN_SEASON_PICKER_PREVIEW_HOST='0.0.0.0'`，手机访问 `http://<电脑局域网IP>:5115/__preview/login`。`ADMIN_SEASON_PICKER_PREVIEW_PORT` 可覆盖端口。临时预览含管理员快捷入口，只用于本地验收。

验收顺序：

1. 实时阵容 → 数据上传，不选文件，直接展开目标赛季；切换后选择样本文件，确认所选赛季保留。
2. 解析预览，再展开菜单；切换赛季后旧确认按钮消失，重新解析可继续发布。
3. 阵容管理 → 批量导入，粘贴 `【阵容码】#验收-测试阵容#PreviewBulk001`，选择赛季并解析。
4. 切走再回来，多次展开；手机分别点击文字、箭头、选项及菜单外空白。
5. 验收完成后由用户确认是否合并 main。
