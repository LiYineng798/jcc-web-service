# 卡组投稿数据层接入

DB migrations `0029_orange_deck_submissions` / `0030_orange_deck_analytics` 已有对应 SQLite 镜像。
完整字段定义在 DB 仓库 migrations；业务语义见
[DB 数据契约](https://github.com/LiYineng798/jcc-db-service/blob/codex/deck-submissions-data/docs/deck-submission-data.md)。
不要重新创建同名表或修改已应用迁移；新增需要另加编号，并同步两种数据库。

## 已实现

- 投稿、处理历史、管理员完善卡组与供稿署名关联所需结构。
- 卡组操作、双代码复制、每日去重访问所需字段/事件表。
- 统一通知关联投稿的存储能力。
- `orange_deck_data_schema.py` 新库 schema / 旧库原子升级；通知表升级保留关联、已读状态、自增序列。
- `db.py` 在 SQLite bootstrap 写入前调用升级；PostgreSQL 只检查新表/列，不执行 DDL。

原卡组行为、页面、推荐和报表仍保持现状。这些结构尚无业务写入，不代表功能已上线。

## 后续 Web 工作

1. 用户双码投稿、自己的投稿列表/私有详情；管理员认领/转派/补充/发布接口与队列。
   身份、CSRF、码校验、版本冲突、处理权限和事务放在服务端，不能仅靠表约束。
2. 公开署名与编辑权限分离。所有者仍为 user_id；公开供稿人优先 provided_by_user_id。
   旧卡组按直接发布兼容。后台跨用户编辑仅限有来源投稿的管理卡组。
3. 同一事务保存投稿版本事件、卡组、通知和审计。当前 orange_deck_service 的部分方法自行 commit，
   需先拆出可组合写入方法。不要让同一次投稿创建多个草稿。
4. 通知收件箱 SQL/序列化/前端类型/私有跳转适配 deck_submission 后，再启用该 kind 的写入。
5. 统一动作采集与有效计数，启用时记录 deck_analytics_started_at；旧历史未知值显示“未采集”。
6. 热门卡组使用近期真实信号、衰减及冷启动补位；后台概览/日报/个人贡献接入新数据。
   任何 target_type 分支显式识别 orange_deck，不把非 lineup 一律当实时榜单。
7. 页面保持简洁、高级，适量动效；本次未调整 UI，不限制后续设计发挥。

`published_by_user_id` 记录首次发布人；终态投稿的 `resolved_at` 非空。
accepted 后即使卡组隐藏/软删除，也保留投稿的 published 历史结果。
当前基础通知服务尚不认识新 kind；不要手工插入真实投稿通知来当作界面已接入的验收。

## 验证边界

数据库与 SQLite 迁移验证不等于 PostgreSQL 生产验收。部署时先应用 DB 迁移，再部署 Web。
新投稿/API/推荐/采集实现后仍需相应聚焦测试；避免重复全量浏览器测试。
Web 测试会初始化默认 instance，应在干净副本验证，不能在带真实数据的工作区试升级。
