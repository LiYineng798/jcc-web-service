# 交接说明

## 项目是什么

JCC 是一个阵容码分享和实时阵容排行网站。用户可以浏览、上传、隐藏、复制、点赞、收藏、举报阵容码；管理员可以管理用户、阵容、举报和访问统计。

## 如何本地运行

```powershell
cd D:\1\codex\jcc\jcc_git
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python run_server.py
```

访问：

```text
http://127.0.0.1:5000
```

## 如何部署

生产环境推荐使用：

```bash
/usr/local/bin/jcc-update
```

部署细节见：

```text
docs/deployment.md
```

## 数据库在哪里

默认数据库：

```text
instance/lineups.sqlite3
```

数据库不能提交 Git，也不能随代码覆盖服务器。

## 管理员后台在哪里

后台地址：

```text
/admin
```

管理员账号和密码应通过环境变量配置：

```text
JCC_ADMIN_USERNAME
JCC_ADMIN_PASSWORD
```

## 实时阵容如何工作

实时阵容数据由本地脚本获取和上传。服务器接收：

```text
POST /api/live-comps/assets/upload
POST /api/live-comps/upload
```

用户访问首页时，前端读取：

```text
GET /api/live-comps
```

详细说明见：

```text
docs/live-comps.md
```

## 哪些文件不能动

生产环境尤其不要删除或覆盖：

```text
instance/lineups.sqlite3
instance/live-comps.json
instance/live-comps.previous.json
instance/live-comps-assets/
```

不要提交或泄露：

```text
*.pem
*.key
.env
ssl-export/
```

## 常见问题

### 登录或收藏异常

优先检查 CDN 是否缓存了 `/api/*`。API 必须 BYPASS。

### 实时阵容没有数据

检查：

- `instance/live-comps.json` 是否存在。
- 上传令牌是否正确。
- `/api/live-comps/summary` 是否正常。

### 静态资源没有走 CDN

检查 CDN 是否对 `/static/*` 设置了强制缓存，并确认响应头是否出现 `X-VIA`、`X-Cache-Status`。

### 数据库更新后异常

先停止服务，再从 `/opt/jcc/backups` 恢复最近一次备份。恢复前确认会丢失备份时间点之后的数据。
