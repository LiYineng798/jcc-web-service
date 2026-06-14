# 安全说明

## 禁止提交的敏感文件

以下文件和目录禁止进入 Git：

```text
instance/
*.sqlite3
*.sqlite3-wal
*.sqlite3-shm
*.db
*.log
ssl-export/
*.pem
*.key
*.crt
.env
.venv/
__pycache__/
.pytest_cache/
```

提交前建议运行：

```powershell
python scripts\maintenance\check_deploy_safety.py
git status --short
```

## 环境变量

生产环境必须通过环境变量配置敏感信息：

| 环境变量 | 作用 |
|---|---|
| `JCC_SECRET_KEY` | Flask Session 加密密钥 |
| `JCC_ADMIN_USERNAME` | 默认管理员用户名 |
| `JCC_ADMIN_PASSWORD` | 默认管理员密码 |
| `JCC_LIVE_COMPS_UPLOAD_TOKEN` | 实时阵容上传令牌 |

`.env.example` 只提供示例，不包含真实值。

## 上传令牌

以下接口需要上传令牌：

```text
POST /api/live-comps/upload
POST /api/live-comps/assets/upload
```

调用时必须带请求头：

```text
X-Upload-Token: <JCC_LIVE_COMPS_UPLOAD_TOKEN>
```

令牌泄露后应立即更换服务器环境变量并重启服务。

## 管理员账号

默认管理员账号只适合本地开发。生产环境必须设置：

```text
JCC_ADMIN_USERNAME
JCC_ADMIN_PASSWORD
```

管理员后台入口：

```text
/admin
```

## 数据库保护

数据库位置：

```text
instance/lineups.sqlite3
```

规则：

- 不提交数据库。
- 不把数据库放进交付包。
- 部署更新前必须备份。
- 修改 `db.py` 或 `migrate.py` 后必须运行测试和 `python migrate.py`。

## CDN 缓存安全

CDN 不能缓存登录态、后台、个人中心和 API 写操作。

必须不缓存：

```text
/api/*
/admin*
/auth*
/me*
/lineup/*
```

可以缓存：

```text
/static/*
/api/live-comps/assets/*
/favicon.ico
```

如果误缓存 `/api/*`，可能导致登录状态、点赞、收藏、管理员数据异常。
