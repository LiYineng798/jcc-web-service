# 实时阵容上传 JSON

上传入口仍为 `POST /api/live-comps/upload?season=<实时阵容赛季ID>`，并使用
`X-Upload-Token`。旧数据继续兼容；新数据可为每个条目增加隐藏的云顶阵容码和站位详情。

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
