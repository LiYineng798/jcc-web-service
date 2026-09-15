# Web 开发约定

本仓库负责 Flask 页面/API、业务逻辑、前端和 SQLite/PostgreSQL 适配。
先读 [README](README.md) 获取运行命令；定位模块时读 [架构](docs/architecture.md)，其余专题按需读取。

## 边界

- PostgreSQL 结构属于相邻 DB 仓库；新迁移先部署。同步 Web 的 SQLite schema/backfill，不能让生产启动代替迁移。
- 普通阵容、实时榜单、赛季资料是不同数据链路；修改前核对 [数据边界](docs/architecture.md#数据与后台任务)。
- 赛季维护先读 [操作规程](docs/season-maintenance-playbook.md)。生成 JSON/图片不手改；修正源档案再生成。资料赛季 ID、阵容分类 ID、官方客户端代号不能混用。
- `instance/`、私有赛季包、凭据、数据库、日志、其他 worktree 不提交、不当作可随意删除的缓存。

## 实现

- 路由处理身份/参数/响应，业务放现有 `*_service.py`；模板管结构，页面 JS 管交互。沿用现有模块边界，不为统一命名批量搬文件。
- 保留 Session、管理员/作者权限、CSRF、审核版本检查和事务边界。封禁与通知修改先读 [审核规则](docs/lineup-moderation.md)。
- Jinja 静态 JS/CSS 使用 `static_v()`。复用共享主题、头像、通知；重要交互兼容手机和键盘。
- React 仅用于三个独立工作区，样式限制在挂载根。修改 `frontend/` 后构建并提交对应 JS/CSS/许可证，见 [前端](frontend/README.md)。
- 公开详情保留首屏 HTML；账号、后台、候选包和隐藏内容保持访问保护与 noindex。赛季资源的 Nginx 代理也必须执行应用权限。

## 验证与交付

- 业务行为改变补充聚焦测试，运行 `python -m pytest -q`；前端源码改变运行 `npm run build --prefix frontend`。其他检查见 [开发与验证](docs/development.md)。
- 同一目录只运行一个 pytest。当前应用在 import 时初始化默认 instance；有珍贵运行数据时使用干净的独立副本验证。
- 不把本地 SQLite/浏览器验证称为生产 PostgreSQL 验收。部署按 [运维手册](docs/operations.md)，不根据历史记录推断当前线上状态。
- 分别在服务仓库提交，沿用 `feat:/fix:/docs:/test:/chore:`。交付说明变更、验证与未解决风险。
- README/AGENTS 只维护长期入口和约束。接口字段、表结构以代码为准；不要追加逐次开发记录或重复的 CLAUDE.md。
