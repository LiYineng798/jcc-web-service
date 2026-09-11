# 赛季资料包操作与部署手册

新赛季创建、官方版本更新、同补丁资料修订以及两套赛季 ID 的关联，统一按 [赛季维护操作规程](season-maintenance-playbook.md) 执行。该规程包含 AI 交付要求与可重复的完整离线演练。

协议见 [设计与实现](season-upload-package-design.md)。以下部署步骤是首次启用本功能所需；日常资料发布不执行部署命令。本次开发仅在 worktree 中完成，未更改服务器。

## 本地制作与后台发布

1. 本地完成官方资料采集、转换、图片处理和需要沿用的补充合并，并人工核对采集结果。服务端不会补齐缺失资料。
2. 从本地归档导入时，可以把结果放在 Git 工作区之外：

```powershell
python scripts/season_library/import_from_archive.py --source "D:/本地档案/数据模板" --season s18 --official-only --output-root "D:/jcc-prepared"
```

导入会重建目标根目录下选定的赛季子目录，使用专用制作目录。`--official-only` 跳过第三方回合观察网络请求，现有本地仙灵继承说明保留。

3. 复制并填写 [更新说明](examples/season-release-notes.json)，可选填写 [来源记录](examples/season-provenance.json)。生成 ZIP：

```powershell
python scripts/season_library/build_upload_package.py --season s18 --source "D:/jcc-prepared/s18" --revision 2 --notes "D:/jcc-prepared/release-notes.json" --provenance "D:/jcc-prepared/provenance.json" --output "D:/jcc-packages/jcc-s18-18.18.2-r2.zip"
```

游戏版本从资料读取；省略 `--source` 则读取仓库 `static/season-data/<season>`。程序先离线校验再生成完整 ZIP，不覆盖已有输出。修改内容或重新制包时提高 revision；重传用原 ZIP。打包器只归档已合并的回合/条件及来源，不联网补全。

4. 管理员登录 → **赛季版本更新** → 拖入/选择 ZIP → 等待服务端校验。上传中断需重传，未实现断点续传；上传已入库后关闭浏览器不会取消任务。
5. 阅读「资料差异 / 更新说明 / 玩法与来源」，预览资料库和模拟器。大范围删减应先核实是否漏采，继承字段需确认告警。
6. 点击「审核并发布」。线上版本已变时先「重新比较」。发布后无需推 GitHub、迁移或重启。
7. 出错时回滚上一版本或任一历史已发布包。资料回滚不恢复业务数据库，不改变独立编辑的公共更新公告。

首次启用建议先把**当前线上静态快照**打包为 r1 并发布，再上传新数据 r2。这样最初资料也有独立历史快照；没有做此步骤时，「基准版本」表示当前代码自带数据，可能随后续代码部署改变。

新赛季首次登记仍走代码部署；首次导入可使用 `--season <id> --initial-status hidden --official-only` 使资料库/模拟器在没有运行时覆盖配置时保持隐藏，已有赛季不允许重复使用 `--initial-status`。已登记赛季的无玩法/多玩法、新资料展示可由数据包表达。新模拟器行为需先增加对应网站能力，详见协议文档。

## 本地运行与构建

Web 与独立 worker 必须使用同一数据库和资料目录。在两个终端运行：

```powershell
python run_server.py
```

```powershell
python season_package_worker.py
```

`python season_package_worker.py --once` 检查待恢复发布事件并至多处理一个队列任务。Flask 最低版本 3.1。worker 不在 Gunicorn 线程中运行，不需要 Redis。

修改 React 源码后构建静态产物并一起提交：

```powershell
npm ci --prefix frontend
npm run build --prefix frontend
```

构建使用支持 Vite 7 的 Node（建议 22.12+）；生产只需 Python 和仓库内已构建静态文件，不运行 npm。第三方许可证随构建产物生成。

## 首次生产部署

必须依次执行 **DB 迁移 → Web 代码/依赖 → worker → 验收**。按原运维手册先备份 PostgreSQL 和 Web runtime；生产数据库、`.env` 和资料包不得加入 Git。

1. 部署 DB 分支。运行 `scripts/apply_migrations.py --database-url "$DATABASE_URL"`，确认 `0015_season_release_packages.sql` 已记录，再运行 `scripts/verify_integrity.py --database-url "$DATABASE_URL"`。仅新增表和索引，不改用户业务行。
2. 部署 Web 分支并安装 `requirements.txt`。新代码启动会检查四张新表，不能先部署 Web。
3. Web 与 worker 的现有 EnvironmentFile 增加：

```text
JCC_SEASON_PACKAGE_ROOT=/opt/jcc/season-library
```

4. 以实际 Web/worker 账号创建持久目录，例如：

```bash
install -d -o jcc -g jcc -m 0750 /opt/jcc/season-library
```

`jcc` 是示例，需匹配现有服务。两者用同一受限账号，资料目录在 Git 和 Nginx 静态根之外。多个 Gunicorn worker 可共用本机目录，多台 Web 主机必须先实现共享存储。

5. 按 [worker unit 示例](../deploy/jcc-season-worker.service.example) 设置 `/etc/systemd/system/jcc-season-worker.service`。核对 `User/Group/WorkingDirectory/EnvironmentFile/ExecStart/ReadWritePaths`；示例 `/etc/jcc.env` 不是对当前服务器实际配置的断言。然后：

```bash
systemctl daemon-reload
systemctl restart jcc.service
systemctl enable --now jcc-season-worker.service
systemctl status jcc-season-worker.service --no-pager
```

6. Nginx 对上传地址保留现有代理、HTTPS 和请求头配置，将 `client_max_body_size` 设为 `257m`（256 MiB ZIP 加 multipart 开销）；`client_body_timeout` 可设 120 秒。确认 Nginx 请求体临时目录空间充足。发布/比较请求的 `proxy_read_timeout` 建议 120 秒，Gunicorn timeout 按实测同步调整。
7. `/season-assets/` 必须代理到 Flask，不能映射为公共 alias，不在 CDN/代理缓存该前缀。候选包权限和赛季隐藏状态都由应用判断。
8. 若 Nginx 直接服务 `/static/`，需要为 `/static/season-data/` 单独保留 Flask 代理才能执行静态基准赛季的隐藏控制。通过代理验证隐藏季 JSON/图片返回 404，不能仅检查页面隐藏。

## 部署验收

- `/api/health` 成功，静态基准赛季资料库/详情/模拟器正常。
- 管理員可以进入工作台，访客不能访问管理接口。
- 上传后 worker 完成校验，候选包还未对访客生效；管理员预览正常，无痕浏览器不能读取候选资源。
- 发布后 catalog 的 `release_id/data_root/asset_root` 指向新包，资料库、详情、模拟器、实时阵容详情和样例图片正常。
- 回滚返回保留版本，刷新后生效；数据库完整性检查为 0。
- 验证两次发布的并发修订号冲突不会覆盖后来更新。

自动冒烟是新的 Flask 请求读取真实路径，不经过外部网络；仍需从浏览器检查 Nginx 上传大小、会话和代理配置。

## 排查、备份与保留

等待校验长期不变化：检查 `systemctl status jcc-season-worker`、`journalctl -u jcc-season-worker --since '10 minutes ago'`，确认数据库、目录一致，有权限和空间。

失败保留原包与错误。数据错误返回本地修正并增加修订号，系统临时错误可「重试校验」。取消由 worker 收尾；超过 10 分钟无心跳的运行任务可重领，发布后中断的验证也由 worker 恢复。不要手工把失败任务改成 ready。

备份必须覆盖 PostgreSQL 四张表、`uploads/`、`releases/`、赛季可见性配置、代码与静态基准。取得一致恢复点时先暂停管理写入、停止 Web/worker，再按已有 DB 手册备份数据库并归档资料目录，随后启动服务。保留异机副本；只有数据库不能恢复图片。

恢复先还原数据文件与数据库，再启动同版本 Web/worker，核对所有 active/previous 引用。日常资料回滚不需要恢复整个业务数据库。

初版保留所有已校验历史包，没有在线删除/自动清理；磁盘不足会拒绝上传或解包。不可直接删除数据库仍引用的 uploads/releases。需要清理时，先做可恢复备份，再使用有引用检查的维护工具；当前不提供此工具。

## API

除资源读取外均需管理员登录，POST 需 `X-CSRF-Token`。

| 方法和地址 | 用途 |
| --- | --- |
| `GET /api/admin/season-packages?page=1` | 每页 20 条、线上状态、最近 30 条事件 |
| `POST /api/admin/season-packages` | multipart `file`，202 创建/200 重用 |
| `GET /api/admin/season-packages/<id>` | 详情、任务及报告 |
| `POST /api/admin/season-packages/<id>/cancel` | 请求取消 |
| `POST /api/admin/season-packages/<id>/retry` | 失败/取消后重试 |
| `POST /api/admin/season-packages/<id>/compare` | 重新比较线上版本 |
| `POST /api/admin/season-packages/<id>/publish` | `expected_revision`、`acknowledge_warnings` |
| `POST /api/admin/seasons/<season>/rollback` | `expected_revision`，可选 `release_id`，null 为基准 |
| `GET /api/admin/season-packages/<id>/download` | 原包下载 |
| `GET /season-assets/<id>/<path>` | 清单内资料和图片，候选包仅管理员 |

来源 URL 只按文字显示。预览只读、固定 release_id，不提供任意目录访问。

## 自动测试

Web 与 DB 仓库各自运行 `python -m pytest -q`。本机 DB 测试验证迁移约束、依赖顺序及完整性 SQL，不代替部署环境的真实 PostgreSQL 验收。

浏览器检查先在 Web 仓库运行：

```powershell
python tests/serve_season_package_preview.py
```

第二个终端把输出的 `PACKAGE_PATH` 填入环境变量，并配置含 Playwright 的 `NODE_PATH`：

```powershell
$env:SEASON_PACKAGE_FILE='上个命令输出的完整 ZIP 路径'
node tests/season_packages.browser.cjs
```

服务器只监听 127.0.0.1:5096，使用固定本地测试账号及临时数据库，与生产无关。测试覆盖 Chromium/WebKit 的错误上传、真实上传和 worker、预览、新玩法、模拟器上阵、告警确认、发布回滚、工作台切换，以及 320/390/768/1440 宽度和明暗主题。截图在不提交的 `instance/season-package-checks/`。
