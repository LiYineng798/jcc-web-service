# 实时榜单与上传

普通阵容存 DB，实时榜单主体存 Web 本地 JSON；赛季资料是第三套数据。
`live_comps_helpers.py` 负责分类清单/读取/缓存，`live_comp_manual_codes.py` 负责人工补码。

## 数据与分类

- `instance/live-comps-seasons.json` 管分类、公开状态、顺序和默认项；普通阵容也使用这些分类。
- 公开列表只含 active/archived；hidden/disabled 留在后台。新建界面默认隐藏，API 调用显式传 status。
- 每个分类有自己的 JSON/补码文件；旧 S17 路径映射集中在 season_data_path()。
  新默认分类没有 JSON 时返回空数据，不能借用前一默认季内容。
- 图片存 `instance/live-comps-assets/`；榜单缩略图与资料库棋盘图片来源不同。
- 首页读取 `/api/live-comps/seasons`、`/api/live-comps/summary` 和分页列表（默认 6 条）。
  复制调用 copy API；全部成功行为保留，五分钟 claim 去重后才增加有效全局统计。

## 两种上传方式

1. 本地 CLI/采集工具：`POST /api/live-comps/upload?season=<分类ID>` 和
   `POST /api/live-comps/assets/upload` 使用 `X-Upload-Token`。先上传图片再提交引用本站图片的 JSON。
   使用 `scripts/upload_live_comps.py --help` 查看支持赛季参数的入口；旧 local 版本仍保留兼容。
2. 后台管理员：Session + CSRF 上传到 `/api/admin/live-comps/uploads/preview`，
   核对差异后调用 `/api/admin/live-comps/uploads/<job_id>/start`，轮询 `/api/admin/live-comps/uploads/<job_id>`。
   Web 内线程缓存图片、备份旧版本并原子替换；任务/进度在 DB，输入、图片与版本备份在 instance。
   失败不替换旧榜单。

这不是赛季 ZIP 上传，二者 worker、数据和接口不同。JSON 原始第三方采集工具属于本地工具，
不作为 Web 请求路径运行；正式数据更新优先在后台审阅差异。

## JSON 示例

上传按 tiers 分组；可选的隐藏 TFT 码与站位详情如下，具体规范化以 live_comps_helpers.py 为准。

```json
{
  "meta": {
    "source": "collector-name",
    "fetchedAt": "2026-08-20T11:47:41Z"
  },
  "tiers": {
    "S": [
      {
        "id": "16232",
        "title": "重装神谕豹女",
        "tier": "S",
        "jccCode": "【阵容码】##...",
        "tftCode": "024284304203fa43741841b3ec40e000TFTSet18",
        "mainAvatar": "https://example.com/main.jpg",
        "heroImages": ["https://example.com/hero.jpg"],
        "formationDetails": {
          "version": 1,
          "season_id": "s18",
          "units": [
            {
              "champion_id": "4507",
              "source_champion_id": "918076",
              "position": 21,
              "items": ["1234", "5678"],
              "source_item_ids": ["har-equip-id-1", "har-equip-id-2"],
              "star": 2
            }
          ]
        }
      }
    ],
    "A": [],
    "B": [],
    "C": [],
    "D": []
  }
}
```

- `tftCode` 仅保存用于后续扩展，公开列表和详情 API 都不会返回。
- `formationDetails.season_id` 对应 `static/season-data/<season_id>` 的资料库 ID。
- `champion_id` 是资料库弈子 ID。HAR 只有站点原始英雄 ID 时可改传
  `source_champion_id`，详情页会通过随赛季发布的 codebook 映射；两者都有时优先使用
  `champion_id`。
- `position` 为 `0..27`，按四行七列从左到右编号。
- `items` 使用该赛季 `items.json` 的装备 ID，最多三件。采集器只有 HAR 原始装备 ID
  时可改传 `source_item_ids`；详情页会同时匹配装备的 `official_id`、`tft_equip_id`
  和 `map_id`。两者都有时优先使用 `items`。
- `star` 建议使用 `1..3`。没有 `formationDetails.units` 时，首页不显示详情入口。
- 首页头像和弈子条继续使用上传并缓存后的 `mainAvatar`、`heroImages`；详情棋盘使用资料库本地资源。
