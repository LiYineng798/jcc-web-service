# S18 魔女奖励快照

页面 `/tools/s18-witch-rewards` 使用独立静态活动数据，不读写数据库，不依赖赛季资料库可见性。
`?stacks=365` 可分享选中档位；无 JavaScript 时使用服务端导航。

来源为用户提供的 DataTFT HAR 中公开前端奖励表和图片响应。
共 9 档、35 种组合、31 张图片；未附明确补丁号，不将其标记为官方实时数据。
概率和预计价值保留来源数值，六项 16.7% 合计 100.2% 是来源舍入结果。
缺省数量为 1，具名弈子缺省星级为 1；装备无星级。

更新时使用新的源 HAR 重新生成，勿手改生成 JSON 或图片：

```powershell
python scripts/season_library/import_witch_rewards.py "C:/path/to/www.datatft.com.har"
```

生成器只解析受限数据字面量，不执行抓取的 JavaScript；只导出所需图片。
HAR 可能包含 Cookie 和请求凭据，不提交原文件。JSON 保存源文件 SHA-256 以追溯。
更新后重启 Web 以刷新进程内数据缓存。

验证：`python -m pytest -q`；浏览器检查脚本 `tests/witch_rewards_rendering.cjs`，
通过 `WITCH_PREVIEW_URL` 指向预览服务，`NODE_PATH` 提供 Playwright。
