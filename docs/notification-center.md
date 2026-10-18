# 通知中心与反馈处理

`notification_center.py` 注册私密接口，`notification_service.py` 汇总互动与已有审核通知，
`feedback_service.py` 管理反馈进度及管理员回复。首页铃铛和个人中心共用同一收件箱。
原审核详情、提案、权限与 revision 机制保留；旧审核接口仍可使用。

## 用户体验与口径

- 分类为全部消息、互动、反馈、审核；分类内可筛选全部/未读/已读并分页。
- 登录用户提交留言或失效反馈后，立即得到一条反馈通知；同一反馈的后续回复更新这条通知。
- 进度为已收到、核实中、已解决、未采纳/无法复现。管理员回复按时间顺序保留，结案必须填写说明。
- 游客留言仅保留原提交、管理员阅读/归档功能，不创建反馈线程、回复通知或查询凭据。
- 管理员对留言的已读/归档状态与用户看到的处理进度独立，不能把管理员看过留言解释为问题已解决。
- 点赞、收藏、复制按作者 + 阵容记录 + 互动类型聚合，每种类型一条。不同作者/不同阵容记录不因代码文本相同而合并。
- 互动仅从启用后发生的操作开始累计，不回放历史互动；排除作者自己的操作。
  点赞沿用每天一次的现有规则；收藏按用户与阵容终身去重，取消后重收藏不再次通知；
  复制沿用用户/匿名 IP + 阵容 + 五分钟桶去重，不等同于复制操作总次数或游戏导入成功。
- 收藏通知表示曾收到的收藏，不随取消收藏回减，因此与个人中心当前收藏总数可能不同。
- 未读数表示通知条数，不是互动次数。已读后新互动/回复增加 revision 并重新标记未读。
  已读写入只接受实际展示的 revision，旧页面遇到新事件返回 409，不能吞掉新提醒。
- 详情显示累计次数与相对上次阅读的新增次数；手动标记未读不会生成新的互动。
- 已删除阵容仍保留历史互动，但不提供无效的详情链接。

## 接口与权限

- `GET /api/me/notifications`：`category=all/interaction/feedback/moderation`，`status=all/unread/read`，分页。
- `PUT /api/me/notifications/<key>`：`status` 与整数 `revision`；key 为 `notice:<id>` 或 `moderation:<lineup_id>`。
- `GET /api/me/feedback/<id>`：仅提交者或管理员，返回进度、原反馈及回复时间线，不暴露 IP、邮箱、管理员账号 ID。
- `/me/feedback/<id>`：受权限保护的独立详情页；个人中心使用页内浮窗阅读。
- `GET /api/admin/feedback/<guestbook|report>/<source_id>`：管理员加载处理记录。
- `POST /api/admin/feedback/<id>/reply`：`revision/status/body`；失效反馈结案时可附 `hide_lineup=true`，不会解除封禁。

所有接口与详情页 private/no-store，修改保留 CSRF 与活跃账号检查。
反馈变更、时间线、通知、源报告状态与审计在同一事务；互动与作者通知也在同一事务。
回复以文本渲染。管理员旧失效反馈处理接口也同步反馈通知，避免出现旧操作入口不通知的情况。
删除留言会删除对应反馈时间线与通知；归档不删除用户的进度记录。

## 部署与验证

先应用 DB 仓库 `0021_feedback_notifications.sql`，再部署 Web。SQLite 使用等价 schema/backfill。
迁移将已有登录用户留言/失效反馈纳入历史记录并标记已读，不推送大量历史未读提醒；
游客留言不纳入。旧留言已读/归档不提供可靠的处理结果，历史反馈进度初始为已收到。
旧报告沿用其已保存的处理状态，不虚构历史管理员回复。
导入顺序、identity 恢复和完整性检查同步包含新表。

在独立干净 worktree 中执行：

```powershell
python -m pytest -q
npm run build --prefix frontend
python tests/serve_notification_preview.py
# 第二个终端，预览使用虚构数据且仅监听 loopback
python tests/notification_center_rendering.py
```

预览默认端口 5160，`/__preview__/login/user` 和 `/__preview__/login/admin` 分别快捷登录虚构用户与管理员。
测试入口不加入正式应用路由。SQLite 和浏览器测试不能代替真实 PostgreSQL 迁移验收。
