# 金蛋奖励

工具箱入口 `/tools/golden-egg` 使用 Jinja 首屏渲染，读取独立静态快照，无数据库迁移。
数据与图片来源为 DataTFT 的 HAR 响应正文；不提交 HAR、请求头或 Cookie。

重新生成（在 Web 仓库运行）：

```powershell
python scripts/season_library/import_golden_egg.py <HAR路径>
```

生成器仅解析 JSON 兼容字面量，不执行抓取脚本。缺失图片、表格不唯一或概率总和不为 100% 时拒绝生成。
图片随应用本地交付；重复物品合并数量，金币标题的数字转换为金币数量。
快照记录源文件 SHA-256；源数据没有明确补丁号，因此不声明适用于特定补丁。

验证：`python -m pytest -q`。浏览器检查可在隔离预览服务上运行
`node tests/golden_egg_rendering.cjs`（需 Playwright；默认端口 5138）。
