# 开发流程

## 标准流程

1. 在 `jcc_git` 修改代码。
2. 运行相关测试。
3. 运行全量测试或必要子集。
4. 检查敏感文件没有进入 Git。
5. 提交到 Git。
6. 推送到 GitHub。
7. 服务器运行更新脚本。

## 本地运行

Windows PowerShell：

```powershell
cd D:\1\codex\jcc\jcc_git
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python migrate.py
python run_server.py
```

默认访问：

```text
http://127.0.0.1:5000
```

## 测试

运行全量测试：

```powershell
pytest
```

运行单个测试文件：

```powershell
pytest tests/test_live_comps.py
```

运行单个测试用例：

```powershell
pytest tests/test_live_comps.py::test_live_comps_summary_returns_tiers -v
```

## 提交前检查

提交前至少检查：

```powershell
git status --short
git diff --stat
```

确认没有以下内容进入 Git：

```text
instance/
*.sqlite3
*.db
*.log
*.pem
*.key
ssl-export/
__pycache__/
.pytest_cache/
```

## 不允许手工同步

不要再手工从 `claude_project` 拷贝文件到 `jcc_git`。如果确实需要同步，必须先说明原因，并使用脚本或明确文件清单。

`webApplication` 应视为生成物，不应作为主开发目录。未来应通过维护脚本从 `jcc_git` 自动导出。

## 服务器更新原则

服务器更新应遵循：

1. 更新前备份数据库。
2. 从 GitHub 拉取代码。
3. 安装依赖。
4. 执行 `python migrate.py`。
5. 重启服务。
6. 调用 `/api/health` 做健康检查。

数据库、证书、上传令牌和管理员密码不能写入 Git。
