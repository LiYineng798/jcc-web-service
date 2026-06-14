# API 说明

本文档按模块列出现有 API。具体请求体和响应字段以对应测试和前端调用为准。

## 基础页面

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 首页 |
| GET | `/auth` | 登录/注册页 |
| GET | `/favicon.ico` | favicon |
| GET | `/lineup/new` | 新增阵容页 |
| GET | `/lineup/<id>/edit` | 编辑阵容页 |
| GET | `/lineup/<id>` | 阵容详情页 |
| GET | `/author/<username>` | 作者主页 |
| GET | `/me` | 个人中心 |
| GET | `/api/health` | 健康检查 |

## 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/me` | 获取当前登录状态、用户信息、CSRF token |
| POST | `/api/register` | 注册 |
| POST | `/api/login` | 登录 |
| POST | `/api/logout` | 退出登录 |

写操作通常需要 CSRF token。前端一般先请求 `/api/me`。

## 验证码

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/captcha` | 获取验证码题目 |
| POST | `/api/captcha/verify` | 验证验证码 |

验证码图片位于：

```text
static/captcha/correct/
```

## 阵容

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/lineups` | 获取阵容列表，支持排序、筛选、分页 |
| GET | `/api/lineups/<id>` | 获取阵容详情 |
| POST | `/api/lineups` | 新增阵容，需登录 |
| PUT | `/api/lineups/<id>` | 编辑阵容，需作者本人或管理员 |
| DELETE | `/api/lineups/<id>` | 删除阵容，需作者本人或管理员 |
| POST | `/api/lineups/<id>/hide` | 隐藏或取消隐藏阵容 |
| POST | `/api/lineups/<id>/view` | 记录浏览 |
| POST | `/api/lineups/<id>/like` | 点赞 |
| POST | `/api/lineups/<id>/copy` | 复制阵容码并记录复制次数 |
| POST | `/api/lineups/<id>/favorite` | 收藏 |
| DELETE | `/api/lineups/<id>/favorite` | 取消收藏 |
| POST | `/api/lineups/<id>/report` | 举报阵容 |

隐藏权限规则：

- 普通用户只能隐藏自己的阵容。
- 作者本人可以看到自己的隐藏阵容。
- 管理员可以看到所有隐藏阵容。
- 其他用户不能在列表、收藏、最近浏览、最近复制中看到被隐藏阵容。

## 个人中心

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/me/recent-views` | 最近浏览 |
| GET | `/api/me/recent-copies` | 最近复制 |
| POST | `/api/me/history/sync` | 同步游客历史到登录用户 |
| GET | `/api/me/dashboard` | 个人中心汇总 |
| GET | `/api/me/reports` | 我的举报记录 |

## 作者主页

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/authors/<username>` | 作者公开主页数据 |

## 增长事件

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/growth-events` | 记录增长漏斗事件 |

管理员行为不应计入增长漏斗统计。

## 实时阵容

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/live-comps/summary` | 实时阵容概要 |
| GET | `/api/live-comps` | 实时阵容列表，默认每页 6 个 |
| POST | `/api/live-comps/<live_comp_id>/copy` | 复制实时阵容并累计全局复制次数 |
| POST | `/api/live-comps/upload` | 上传实时阵容 JSON，需要上传令牌 |
| POST | `/api/live-comps/assets/upload` | 上传实时阵容图片缓存，需要上传令牌 |
| GET | `/api/live-comps/assets/<filename>` | 读取本地缓存图片 |

上传接口需要请求头：

```text
X-Upload-Token: <JCC_LIVE_COMPS_UPLOAD_TOKEN>
```

## 管理员

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/users` | 用户列表，支持搜索 |
| POST | `/api/admin/users` | 新增用户 |
| PUT | `/api/admin/users/<id>` | 修改用户 |
| DELETE | `/api/admin/users/<id>` | 删除用户 |
| GET | `/api/admin/lineups` | 阵容列表，包含隐藏阵容，支持搜索 |
| GET | `/api/admin/live-comps` | 实时阵容统计数据 |
| PUT | `/api/admin/lineups/<id>` | 管理员修改阵容 |
| POST | `/api/admin/lineups/<id>/adjust-score` | 管理员调整点赞数/复制数修正值 |
| GET | `/api/admin/stats` | 管理基础统计 |
| GET | `/api/admin/overview` | 访问概览 |
| GET | `/api/admin/growth` | 增长漏斗 |
| GET | `/api/admin/audit-logs` | 审计日志 |
| GET | `/api/admin/reports` | 未处理举报列表 |
| POST | `/api/admin/reports/<id>/resolve` | 处理举报，可标记已处理或隐藏阵容 |
