# 生产恢复点索引

合并自仓库已有上线记录，仅保存定位恢复资料所需信息，不是当前线上状态声明。
本次文档整理未连接服务器，也未复验备份是否仍在。完整历史描述可从 Git 读取。

## 2026-09-15 · 个人中心

- Web：bd82fdd97136020a0226364aff84f93a8c4771b4 → 2c82ed3557870b9dc131bfa343ce5bfcd31ce954。
- DB：52cc22cf900b1d1207fb80e9cb326c95f41dd6bd，迁移保持 0016。
- 备份：/opt/jcc/deploy-backups/profile-workspace-20260915-100252/。
- 包含 database-before.dump、runtime-before.tar.gz（instance + season-library）、
  web-before.tar.gz、db-before.tar.gz、config-before.tar.gz；release.json 保存哈希/指纹/版本，
  https-smoke.json 保存 35 项 HTTPS 检查。
- 当时停写前后 9 张业务表指纹一致，14 项 DB 完整性检查通过；两个服务恢复正常。
- 代码可退到 bd82fdd（仍有封禁保护）；恢复数据库会覆盖备份后的写入，须另建当前恢复点。

## 2026-09-14 · 阵容审核

- Web：004fee0582acc21298a84b79fcd5adfce833a73c → bd82fdd97136020a0226364aff84f93a8c4771b4。
- DB：92cac96f2a6f2435dc4de6df94e6e670d483c817 → 52cc22cf900b1d1207fb80e9cb326c95f41dd6bd。
- 0016_lineup_moderation 于北京时间 15:07:33 应用。
- 备份：/opt/jcc/deploy-backups/lineup-moderation-20260914-150418/，
  包含同名 database/runtime/web/db/config-before 文件、release.json、postgres-smoke-ok.json、https-smoke.json。
- 当时独立 PostgreSQL 完整迁移/重审链路、生产完整性与 19 项 HTTPS 检查通过。
- 有真实封禁/提案/审核事件后，不能只回退旧 Web 绕过保护。

## 2026-09-11 · 赛季发布

- 初始 Web 8033c2d、DB ecb9342；Web 随后加入 3d74503（等待 CSRF 再挂载上传组件）。
- DB 应用 0015；启用独立 worker、/opt/jcc/season-library 和受保护 Nginx 代理。
- 初始包：s18-18_18_2-r1；release_id=0ae00c95730443369f479645269a5c9c；
  ZIP SHA-256=ab9f4cc9652dabd23d77aef405071be517bb17319e649437125d26c114ffa8cd。
- 发布 → 回滚 → 重发后 active.revision=3；阵容分类 s18-enchanted-wilds。
- 备份：/opt/jcc/deploy-backups/season-upload-20260911-131918/，其 after/ 包含发布后 DB/资料包、worker unit 和 Web drop-in。
- 当时验证正式 PostgreSQL 发布/回滚与隐藏季资源 404；S18 历史补充保持未核验来源告警。

以上备份均记录为同机、root 专属，不等于异机备份。恢复按 [运维](operations.md) 协调 DB 与文件，
先核实备份、校验和及现有业务状态，不能照抄历史版本号直接覆盖线上。
