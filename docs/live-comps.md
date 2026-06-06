# 实时阵容说明

## 功能定位

实时阵容排行用于在首页展示外部数据来源获取到的热门阵容。它和用户自己上传的阵容是两套数据：

- 用户阵容存储在 SQLite 的 `lineups` 表中。
- 实时阵容存储在 `instance/live-comps.json` 中。
- 实时阵容图片缓存存储在 `instance/live-comps-assets/` 中。

## 数据流

1. 本地脚本获取 DataTFT 数据。
2. 本地脚本下载远程图片。
3. 本地脚本调用 `/api/live-comps/assets/upload` 上传图片。
4. 本地脚本重写 JSON 图片地址为 `/api/live-comps/assets/<filename>`。
5. 本地脚本调用 `/api/live-comps/upload` 上传 JSON。
6. 网站首页从 `/api/live-comps` 读取数据展示。

## 上传接口

上传 JSON：

```text
POST /api/live-comps/upload
```

上传图片：

```text
POST /api/live-comps/assets/upload
```

两个接口都需要：

```text
X-Upload-Token: <JCC_LIVE_COMPS_UPLOAD_TOKEN>
```

## 前端展示

首页默认展示“实时阵容排行”。展示规则：

- S/A/B/C/D 混合展示。
- 每页最多 6 个。
- 不直接展示阵容码内容。
- 用户点击复制按钮后直接复制阵容码。
- 主头像和等级颜色用于表达阵容强度。

## 统计逻辑

实时阵容复制不按单个阵容统计，只统计全局：

- 当日复制次数。
- 历史累计复制次数。

相关表：

```text
live_comp_global_stats
live_comp_global_daily_stats
```

## 图片本地化

实时阵容不应让前端直接加载第三方图片链接。正确流程是：

1. 本地脚本下载远程图片。
2. 上传到服务器 `instance/live-comps-assets/`。
3. JSON 中图片地址改为 `/api/live-comps/assets/<filename>`。
4. 前端从本站加载图片。

## 注意事项

- 本地上传脚本属于 `scripts/local/`。
- `scripts/local/` 不应进入服务器交付包。
- 服务器只保留接收数据、保存数据、展示数据的能力。
- `instance/live-comps.json` 和 `instance/live-comps-assets/` 是运行数据，不提交 Git。
