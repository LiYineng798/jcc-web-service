# 金铲铲阵容库

多人在线 Flask + SQLite 单页网站，用于保存、搜索、复制、点赞、收藏和管理金铲铲阵容码。

当前版本还包含：

- 作者主页：`/author/<username>`
- 增长事件埋点：`POST /api/growth-events`
- 后台增长漏斗：`GET /api/admin/growth`
- 内容发现排序：`sort=rising`、`sort=recommended`
- 增长事件表：`growth_events`

## 本地运行

```bash
pip install -r requirements.txt
set JCC_SECRET_KEY=change-me
set JCC_ADMIN_USERNAME=adminxlx
set JCC_ADMIN_PASSWORD=your-secure-password
python migrate.py
python run_server.py
```

默认访问：`http://127.0.0.1:5000`

## 实时阵容上传

新增了独立上传接口：`POST /api/live-comps/upload`

本地上传命令：

```bash
python upload_live_comps.py --file team_codes_by_tier.verify.json --url https://jcc.np5.top/api/live-comps/upload --token YOUR_UPLOAD_TOKEN
```

## 账号与权限

- 未登录用户：浏览、搜索、复制阵容码；复制会按 IP 在 10 分钟内计分一次。
- 登录用户：新增阵容、编辑/删除自己的阵容、点赞、收藏、举报。
- 管理员：访问 `/admin`，管理用户、阵容、举报、分数、增长漏斗和审计日志。

## 生产部署提醒

- 不要使用 Flask debug server 对公网提供服务。
- 建议使用 Nginx + Gunicorn/uWSGI，并启用 HTTPS。
- `JCC_SECRET_KEY` 和管理员密码必须使用环境变量配置。
- SQLite 数据库位于 `instance/lineups.sqlite3`，请定期备份。
