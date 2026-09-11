# 2026-09-11 赛季版本管理生产部署记录

目标为 `114.134.186.41`，站点 `https://jcc.np5.top`。本记录是正式服务器验证，区别于此前临时 SQLite 演练。后续日常维护仍按 [操作规程](season-maintenance-playbook.md)，代码升级按 [服务器手册](server-update-guide.md)。

## 已部署内容

- GitHub 上确认 Web `8033c2d`、DB `ecb9342` 后部署；Web 后续加入 `3d74503` 修复。该修复已提交本地 main，通过 Git bundle 同步服务器，未代用户推送 GitHub。
- PostgreSQL 15 与 Web 同机，连接目标 `127.0.0.1:5432/jcc`；实际监听 `127.0.0.1` 和 `::1`。迁移 `0015_season_release_packages` 已执行。
- `jcc.service` 和独立 `jcc-season-worker.service` 均使用 `jcc:jcc`、`/etc/jcc.env`。新增 `JCC_SEASON_PACKAGE_ROOT=/opt/jcc/season-library`，目录权限 0750，位于 Git 和 Nginx 公共目录之外。
- worker 已启用开机启动，采用仓库 unit 的资源限制和文件系统权限。Web 保留 2 个 gthread worker、每个 4 线程；通过 `/etc/systemd/system/jcc.service.d/season-upload.conf` 将 Gunicorn timeout 调整为 120 秒，端口仍为 5054。
- Nginx 的 `/api/admin/season-packages` 允许 257 MiB 请求体，上传和代理超时 120 秒；`/season-assets/`、`/static/season-data/` 经过 Flask 权限校验且关闭代理缓存。其余静态文件仍直接托管，Certbot TLS 配置保留。

## 正式验收与初始快照

在本地从 main 的完整 S18 资料制作 ZIP，再通过生产 HTTPS 后台上传约 25.5 MiB 文件，由正式 worker 完成离线校验。包身份：

| 项目 | 值 |
| --- | --- |
| 资料赛季 | `s18` |
| 阵容分类 | `s18-enchanted-wilds`，沿用现有分类 |
| 游戏版本 / 资料修订 | `18.18.2` / `1` |
| package_id | `s18-18_18_2-r1` |
| release_id | `0ae00c95730443369f479645269a5c9c` |
| 验收结束时发布修订 | `3`，因为执行了发布 → 回滚至原静态资料 → 重新发布 |
| 原包 SHA-256 | `ab9f4cc9652dabd23d77aef405071be517bb17319e649437125d26c114ffa8cd` |

74 弈子、36 羁绊、157 装备、257 强化符文、4 棋盘对象、170 仙灵条目和 1482 张图片与原静态资料一致。唯一结构差异是为旧仙灵玩法补齐 `presentation: legacy.v1`；逐项比较确认其条目和数值未改变。225 个历史回合/条件补充字段保留来源和未核验告警，未请求第三方网络数据。

已验证候选资源对访客返回 404、管理员两个预览正常、模拟器上阵正常；真实发布、PostgreSQL 回滚和重新发布成功；公开资料库与模拟器 catalog 指向同一 release。首页、资料页、弈子详情、模拟器、样例图片及实际分类的阵容列表返回 200。隐藏 S17 的 JSON 和图片经过 Nginx 返回 404，sitemap 不包含它。实时和普通阵容分类及其既有默认选择未改变。

验收中复现了快速打开上传页导致空 CSRF token 被 React 捕获的问题。`3d74503` 等待管理员会话就绪再挂载；延迟 `/api/me` 的 Chromium/WebKit 回归检查通过，生产也确认非法探测包由 ZIP 校验返回 400，随后有效完整包成功上传。Web 全量 `python -m pytest -q` 再次 600 passed；正式数据库完整性检查所有异常计数为 0。完成检查时 Web/worker 正常，worker 无异常重启。

维护验收未创建测试用户、虚拟赛季或测试阵容，未修改管理员密码。服务器环境中的初始管理员密码与现有账户不一致，因此没有修改账户；验收使用临时管理员维护会话，结束清除临时会话文件。

## 恢复点与后续操作

- 部署前备份：`/opt/jcc/deploy-backups/season-upload-20260911-131918/`，含 PostgreSQL dump、Web runtime、旧环境/服务/Nginx 配置和原 Git 提交号。
- 部署后备份：上述目录的 `after/`，另含完整资料包持久目录、worker unit 和 Web drop-in。备份时短暂停止 Web/worker；dump 已通过 `pg_restore --list` 检查，并保存 SHA-256。
- 这些备份在同一服务器，不等于异机备份。恢复包版本时优先使用后台回滚；灾难恢复须同时还原 DB 与资料文件，不能只恢复数据库。
- S18 同一 `18.18.2` 内容修订下次从 r2 开始；新官方补丁按真实版本号制作，可从 r1 开始。不要把当前发布修订 3 当作资料修订 3。
- 其他赛季继续使用已有静态基准，尚未逐一创建初始历史包。不要声称所有赛季已迁入上传包管理。
- 本次修复和运维文档在本地 main 提交后通过 bundle 同步服务器；GitHub 推送仍由用户执行。后续应正常推送 main，再恢复日常从 GitHub 拉取的流程。
