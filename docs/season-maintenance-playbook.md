# 赛季维护

此流程面向新赛季、官方补丁和同补丁修订。服务器配置见 [运维](operations.md)，
数据能力见 [资料结构](season-library.md)，离线校验规则见 [ZIP 协议](season-package-format.md)。

## 先区分对象

| 对象 | 示例 | 谁负责 |
| --- | --- | --- |
| 资料赛季 ID | s18 | 静态 catalog 首次登记，资料库/模拟器共用 |
| 阵容分类 ID | s18-enchanted-wilds | 后台实时阵容赛季管理，普通阵容也使用它 |
| 官方 mode / client | 18 / S19 | 官方版本记录；不能由站内名字猜 |
| 游戏补丁 | 18.18.2 | 官方真实字符串 |
| data_revision | 2 | 同一补丁重新制作内容时递增 |
| active.revision | 服务端整数 | 发布/回滚并发控制，不能手工冒充资料修订 |

实时记录 `formationDetails.season_id` 指向资料 ID；两个目录同名不等于自动关联。
普通/实时游戏码只做格式提取，选错分类不会转换游戏码。

## 新赛季首次接入

1. 在外部源档案核对官方映射、增加采集适配/CLI 登记并校验完整快照。现有采集器的 choices 不能保证未来赛季直接可用。
2. 在 Web 首次登记为隐藏（示例 s19 必须已经存在于源档案，且未登记到网站）：

```powershell
python scripts/season_library/import_from_archive.py --source "D:/本地档案/数据模板" --season s19 --official-only --initial-status hidden
```

3. 检查 catalog、版本、数量、图片与对象审计；测试并部署完整 JSON/图片。只有新 schema 才需 DB migration。
4. 用下一节方法制作 r1，上传、预览、发布，保存独立初始快照。静态基准会随代码改变，不能代替永久恢复点。
5. 后台「资料赛季」分别启用资料库和模拟器、排序和默认项。
6. 在「实时阵容 → 赛季管理」单独创建隐藏分类，上传真实榜单后启用；普通阵容选项随后可用。
   实时详情使用资料 ID，格式见 [实时上传](live-comps.md)。
7. 验证首页、资料页、模拟器、普通阵容创建和实时详情。公开公告单独维护。

一个 ZIP 不会自动登记新赛季、创建分类、更新普通阵容或发布公告。

## 已登记赛季更新

1. 源档案更新到明确官方版本并校验。只访问官方来源，本地历史补充保留来源/未核验状态。
2. 在 Web 生成独立制作目录；输出会重建目标赛季子目录：

```powershell
python scripts/season_library/import_from_archive.py --source "D:/本地档案/数据模板" --season s18 --official-only --output-root "D:/jcc-prepared"
```

3. 填写 [更新说明](examples/season-release-notes.json)，按需填写 [来源](examples/season-provenance.json)。
   制作完整 ZIP，修订号与输出路径使用本次未占用的值：

```powershell
python scripts/season_library/build_upload_package.py --season s18 --source "D:/jcc-prepared/s18" --revision 2 --notes "D:/jcc-prepared/release-notes.json" --provenance "D:/jcc-prepared/provenance.json" --output "D:/jcc-packages/s18-r2.zip"
```

4. 「赛季版本更新」上传 → 独立 worker 校验 → 审阅差异/来源/告警 → 预览资料库和模拟器。
5. 审核并发布。线上 revision 已变时重新比较，不重放旧发布请求。
6. 验证后保留包 ID、真实补丁、资料修订和发布结果。出错优先回滚已发布版本。

新官方补丁保留真实版本字符串，可从 r1 开始；同一补丁的文案/图片/条件修正只递增 data_revision。
重新传输用原 ZIP，修改内容就制作新 revision；不改文件名伪造补丁。
日常数据发布无需 Git、迁移或重启。新能力、初次登记或明确更换静态基准才走代码部署。

## 每次验收

- 候选资源对游客不可读；管理员预览固定 release，不能写业务数据。
- 资料库和模拟器 catalog 的 release_id/data_root/asset_root 一致；数量、弈子/装备引用、图片可读。
- 核对玩法增删、来源告警和 board_units 的 review 清单；模拟器上阵/装备/羁绊与样例旧分享码可用。
- 两套赛季分类和各展示策略正确；模拟器 URL season_id 优先于已保存选择，分享码所属季优先级更高。
- 检查首页、详情、sitemap、Nginx 资源权限。Flask 测试通过不代表外部代理正确。
- 回滚恢复资料，不改变普通阵容、用户、展示顺序或默认配置。
- 实时榜单缩略图来自独立上传缓存，不随资料包自动更换。

完整演练见 `tests/test_season_lifecycle.py` 和 `tests/season_lifecycle.browser.cjs`：
复制 S18 为虚构 S99，使用临时数据完成初始包、补丁、修订及回滚；不代表真实未来赛季或生产验收。
启动方式见 [开发与验证](development.md)。演练资料和测试码不得发布到生产。
