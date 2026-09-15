# 赛季 ZIP 协议与发布边界

以 `season_package_format.py`、`season_package_validation.py` 的校验为准。
制作/发布步骤见 [赛季维护](season-maintenance-playbook.md)。

## 完整不可变快照

一个包对应一个已登记赛季的一个游戏补丁与 data_revision。
含 JSON、全部引用图片、更新说明与来源；不支持增量、断点续传、包内脚本/SQL或在线编辑。
服务器不抓取来源 URL、不执行 Git/pip/部署。

```text
manifest.json
release-notes.json
provenance.json
supplements.json
data/
  season.json
  index.json
  champions.json
  traits.json
  items.json
  augments.json
  board_units.json
  tft-codebook.json             # 可选
  mechanics/<id>.json
assets/
```

manifest 由打包器生成，不手写：协议标识/版本、包与赛季 ID、game_version、data_revision、
模块状态、必需能力、玩法、逐文件 bytes/sha256。files 不包含 manifest 自身。
整个 ZIP 哈希相同则重用已有任务；同包 ID 或同季/补丁/revision 对应不同 ZIP 时拒绝。

弈子、羁绊、装备必须 present 且非空；不适用的模块明确 absent，无玩法明确 `mechanics: []`。
服务端重新核对数量、ID 引用、图片、赛季/版本及完整文件与紧凑 index 的一致性。
SHA-256 只证明完整性，不证明来源真实；effective_at 是记录值，非定时发布。

## 玩法与来源

已支持 cards.v1、variants.v1、stages.v1、table.v1，以及兼容旧机制的 legacy.v1。
通用玩法只面向 reference；模拟器特殊单位通过 board_units 能力表达。
未知模板、能力或规则拒绝，新增战斗/交互规则需要先升级代码。
参考 [通用玩法示例](examples/generic-season-mechanic.json)。

非空 rounds/requires 需在 supplements 中列出 record/field/value/source/继承版本/verification，
与正文一致。仅来源明确当前补丁 verified 时才标已核验，否则 inherited_unverified 并告警。
不能清空 supplements 来隐藏已存在的补充值。S18 基准的历史补充见 [来源约束](season-library.md)。

## 校验与恢复

任务 queued → validating → ready/rejected/cancelled；独立 worker 记录阶段、进度、心跳和租约。
浏览器关闭不取消已入库任务。失败/取消后可重试，坏数据需本地修正为新包。
超过 10 分钟无心跳的任务可接管；失去租约的旧 worker 不能提交。未完成的发布验证由 worker 恢复。

阻断错误包括越界/重复路径、目录条目、链接、加密/嵌套 ZIP、脚本、压缩炸弹、哈希错误、
非有限数值、损坏图片及结构/引用不一致。初始上限为 ZIP 256 MiB、展开 1 GiB、10,000 文件、
单文件 64 MiB、JSON 32 MiB、manifest 4 MiB；图片不接受 SVG/动画。完整限制读取代码。

报告给出资料/图片/玩法差异；继承字段、玩法移除、大量内容删除需确认告警。
结构错误不能跳过。

发布需要与当前线上指针及比较报告一致的 expected_revision。
DB 事务共同更新当前/上一版本和事件；一次读取固定一个 release_id。
发布后的 Flask 冒烟失败按 revision 条件恢复旧指针，不能覆盖随后成功的发布。
这不替代 Nginx/浏览器外部验收。

回滚可选历史已发布包或静态基准。基准随代码变化；初次启用宜先把现有基准做成 r1 发布。

## 读取与保留

`season_data_repository.py` 统一选择版本。管理员 preview_release 只读、noindex、private/no-store，
不记访问统计，模拟器使用独立草稿。候选资源只对管理员开放。
`/season-assets/<release_id>/<path>` 核验清单与公开状态；历史已发布包仍受当前赛季可见性限制。

DB 四表保存包元数据、任务、指针和事件，文件存在 `JCC_SEASON_PACKAGE_ROOT` 的 uploads/staging/releases。
无在线删除或自动清理工具；保留所有被引用版本，包括回滚目标。
恢复必须匹配 DB、文件、静态基准和可见性配置，见 [运维](operations.md)。
