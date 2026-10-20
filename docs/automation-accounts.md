# AI 自动化账号

管理员在「用户管理 → AI 自动化账号」创建、调整权限、禁用、删除和轮换令牌。
账号独立于普通用户及管理员，仅支持专用 API；无注册入口、网页登录或密码找回工作流。
生产升级前先应用 DB 仓库 `0023_automation_accounts.sql`。

## 权限边界

| 能力 | 默认状态 / 约束 |
| --- | --- |
| 运营概览、复制排行、日报 | 只读汇总；不输出邮箱、IP、访客身份、复制事件明细、审计日志和密码重置记录 |
| 普通阵容列表 | 仅公开可用赛季的正常阵容，每页 50 条 |
| 普通阵容批量导入 | 默认关闭；管理员明确选择允许的赛季；每批 1–50 行，最多 20000 字符 |
| 作者归属 | 由服务端固定为当前自动化账号，不能指定他人作者 |
| 既有内容管理 | 不能覆盖、编辑、删除、调分、审核或绕过封禁码的去重检查 |
| 其他后台能力 | 不开放账号管理、系统设置、实时榜单、赛季资料上传、公告发布和日报重算 |

普通注册接口仍只创建普通用户；普通用户不能把自己的账号升级为自动化账号。
自动化身份不计入普通用户注册、登录和访问指标，成功导入的阵容仍计入内容指标。

令牌含 256 位随机秘密，仅创建或轮换时返回一次；数据库只保存 SHA-256 摘要。
有效期默认 30 天，管理员可在创建或 API 轮换时选择 1–90 天。权限每次请求重新读取。
轮换立即撤销旧令牌；禁用同时撤销令牌，重新启用后需要轮换。删除为不可恢复的逻辑删除，
保留上传阵容的归属、导入回执和审计记录。

使用 HTTPS；令牌放入调用方的密钥存储或环境变量，不放 URL、浏览器本地存储、公开提示词或日志。
专用导入接口使用 Bearer 认证，不接受管理员 Cookie 作为替代，因此无需 CSRF token；
管理员账号生命周期接口继续要求管理员 Session + CSRF。

## 接入

所有专用接口前缀为 `/api/automation`，请求头为 `Authorization: Bearer <令牌>`。
JSON 写入需 `Content-Type: application/json` 和 `Content-Length`（通常由 HTTP 客户端自动设置）。
响应为 `private, no-store`。

| 方法和路径 | 用途 |
| --- | --- |
| GET `/me` | 查询当前权限、授权赛季、到期时间和配额 |
| GET `/overview` | 运营汇总与最近七天流量 |
| GET `/copy-rank?date=YYYY-MM-DD` | 指定日复制排行榜；省略日期为当天 |
| GET `/daily-reports` | 最近 30 份已生成日报索引 |
| GET `/daily-reports/YYYY-MM-DD` | 日报汇总、小时分布、页面/赛季/复制排行 |
| GET `/lineup-seasons` | 可用普通阵容赛季 |
| GET `/lineups?season_id=...&page=1` | 普通阵容分页读取 |
| POST `/lineups/bulk-import/preview` | 按原有阵容码规则解析、校验与去重预览 |
| POST `/lineups/bulk-import` | 批量导入；须带 `Idempotency-Key` |

示例请求体（示例码不保证可在游戏中使用）：

```json
{
  "season_id": "s18",
  "raw_text": "【阵容码】#作者-阵容名称#EXAMPLECODE001"
}
```

先预览确认，再提交同一份内容；幂等键使用每批唯一的 UUID 或 8–100 位字母、数字、下划线、连字符。
网络重试沿用同一个键和请求体，会返回已提交回执；同键不同内容返回 409。
导入内容、上传者、审计与回执在一个事务提交。重复阵容码（包括被隐藏或封禁的旧码）不会重复创建。
无效行会在结果中单独标记，其余可导入行仍可成功，调用方应逐行检查结果。

读取每账号每分钟最多 60 次；预览和导入共用每账号每小时 10 次写入请求配额。
限流会返回 429，鉴权失效为 401，权限不足为 403；失败的已鉴权请求也计入限流。
只读接口不会触发日报生成；尚无快照时返回 404。
日报是生成时快照；历史缺失上传者的普通阵容按当前账号补充，并带 `uploader_attribution=current`。
无法追溯的实时阵容上传者明确标为未记录。

## 本地验证

```powershell
python -m pytest -q tests/test_automation.py tests/test_daily_report.py tests/test_admin.py
python tests/serve_admin_experience_preview.py
# 另一终端，已安装 Playwright 及浏览器、配置 NODE_PATH 后：
node tests/admin_experience.browser.cjs
```

预览仅监听 loopback，独立数据保存在 `instance/admin-experience-preview/`；
`/__preview/login` 是测试服务器特有的快捷入口，正式应用不注册此路由。
浏览器检查覆盖 Chromium/WebKit、窄屏/桌面、中文组合输入、原节点焦点、深浅主题和错误重试；
桌面模拟不能替代真实 iPhone 软键盘验证。
