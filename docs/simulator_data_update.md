# 阵容模拟器数据更新说明

阵容模拟器运行时读取 `static/tools/lineup-simulator/data/` 下的 JSON 文件，不再直接依赖 `local-data.js`。

## 数据文件

- `version.json`：数据版本信息
- `tabs.json`：费用筛选、装备分类筛选
- `heroes.json`：棋子数据，包括费用、羁绊、头像路径
- `equips.json`：装备数据
- `traits.json`：羁绊数据
- `pets.json`：召唤物/特殊单位数据

## 自动生成命令

在 `claude_project` 目录运行：

```powershell
python .\scripts\build_simulator_data.py
```

默认会从：

```text
static/tools/lineup-simulator/local-data.js
```

生成到：

```text
static/tools/lineup-simulator/data/
```

## 从合并 JSON 生成

如果以后你拿到的是一个合并后的 JSON 文件，格式包含：

```json
{
  "version": {},
  "heroCostTabs": [],
  "equipTabs": [],
  "heroes": [],
  "equips": [],
  "traits": [],
  "pets": []
}
```

可以运行：

```powershell
python .\scripts\build_simulator_data.py --source D:\path\to\simulator-source.json
```

## 修改棋子费用

例如莫甘娜从 5 费变 4 费，修改源数据里的对应棋子：

```json
{
  "name": "莫甘娜",
  "cost": 4,
  "costLabel": "4费"
}
```

然后重新运行生成脚本。前端会自动读取新的 `heroes.json`，并使用四费边框颜色。

## 验证命令

```powershell
python .\scripts\build_simulator_data.py
pytest tests/test_simulator_data_builder.py tests/test_ui_routes.py -q
```
