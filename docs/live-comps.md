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
   Web 内线程缓存图片并保存版本，默认预上线；`start` 请求显式传 `{"publish": true}` 才直接上线。
   任务/进度继续在 DB，输入、图片与版本保存在 instance。图片缓存失败不替换旧榜单。

## 版本库与补码

后台「实时阵容 → 数据上传」同时提供上传区和版本库。推荐先解析差异，保存为预上线版本，
在右侧预览中按名称/ID 搜索或筛选缺码阵容，完成补码后点击「上线此版本」。允许缺码上线，
但需要显式确认；「处理完成后直接上线」用于无需等待补码的文件，默认不选中。

- 同一赛季只有一个线上版本。预上线、历史版本的预览和补码不影响公开 API。
- 历史版本可再次上线以回滚；切换前完整保存当前线上 JSON 和该版本补码。
- 当前线上版本不能删除。其他版本删除前确认，删除后不能通过版本 API 再恢复。
- 原有「阵容码维护」仍维护当前线上版本。版本预览允许修改已补录的码；原始 JSON 自带的码不覆盖。
- 新后台上传的版本不自动继承同 ID 的旧补码，防止不同阵容复用 ID 时误带码；重复 ID 上传会被拒绝。
- CLI/token 上传保持直接发布、沿用当前版本匹配 ID 补码的兼容行为，也会进入版本库。
- 上线和补码使用内容指纹检查并发修改；上传直接上线还会核对解析时的线上指纹。
  若期间线上发生变化，上传结果保留为预上线版本，提示重新预览后上线。
- 管理接口沿用管理员 Session、写操作 CSRF、审计记录，预览响应禁用公共缓存。

版本管理接口位于 `/api/admin/live-comps/versions/<season_id>`；单个版本预览在其后追加
`/<version_id>`，操作追加 `/publish`、`/code`、`/delete` 并使用 POST。
操作携带预览返回的 `revision`，上线还携带 `active_revision`；缺码上线需 `allow_missing: true`。

存储沿用单机共享磁盘：线上 JSON 顶层 `_release` 保存版本标识、发布时间与独立补码；
它是当前版本的权威记录，文件使用原子替换。旧 JSON 首次在版本库中显示为「原线上版本」，
切换时自动连同旧 overlay 归档，不需要手工迁移。快照位于各线上 JSON 相邻的
`<文件名去掉.json>.versions/`，例如 `instance/live-comps.versions/` 与
`instance/live-comps-seasons/s16-legends.versions/`。跨进程文件锁串行化写入。

备份/恢复必须一起保留线上 JSON、这些 `.versions` 目录、图片和上传任务输入；不能只备份数据库。
删除版本不删除共享图片或审计/上传任务历史。降级到不识别 `_release` 的旧 Web 前，需先导出
线上版本补码到旧 overlay 格式，否则旧程序无法展示版本内补码。

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
