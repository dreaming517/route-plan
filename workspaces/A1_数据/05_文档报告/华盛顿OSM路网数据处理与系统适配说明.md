# 华盛顿 OSM 路网数据处理与系统适配说明

> 适用项目：G4 路径规划引擎（route-plan）。归档位置：`workspaces/A1_数据/05_文档报告/`。本文件记录 A1 数据线负责的华盛顿特区 OSM 路网获取、转换、优化、验证及接口约定。**本次 PR 仅提交 A1 工作区的成果，不包含对公共 `api/`、`web/` 或核心路径规划模块的修改。**

## 1. 数据来源与处理目标

本次使用 Geofabrik 提供的 OpenStreetMap（OSM）华盛顿特区区域提取数据。Geofabrik 是 OSM 数据的区域分发渠道，原始 PBF 中的 Node、Way、Relation 对象不能直接供项目现有的 `load_graphml()` 接口读取；项目使用包含节点坐标及有向道路属性的 GraphML 路网。数据统一采用 WGS 84 经纬度坐标（经度 `lon`、纬度 `lat`），来源数据许可遵循 OSM 的 ODbL 1.0，© OpenStreetMap contributors。

本次 A1 数据文件与脚本相对于**项目根目录**的位置如下：

| 类型 | 文件路径 |
|---|---|
| 原始数据 | `workspaces/A1_数据/01_路网清单/raw/district-of-columbia-261011.osm.pbf` |
| 优化后的正式路网 | `workspaces/A1_数据/01_路网清单/processed/dc_driving_optimized.graphml` |
| 原始数据盘点结果 | `workspaces/A1_数据/03_数据质量/osm_inspection.json` |
| 路网验证结果 | `workspaces/A1_数据/03_数据质量/dc_validation_optimized.json` |
| 处理与验证脚本 | `workspaces/A1_数据/05_文档报告/scripts/` |
| 字段与单位说明 | `workspaces/A1_数据/02_字段与单位/华盛顿路网字段与单位说明.md` |
| 接口对接说明 | `workspaces/A1_数据/04_接口对接说明/华盛顿路网接口对接说明.md` |
| AI 使用说明 | `workspaces/A1_数据/06_AI使用说明/华盛顿路网AI使用说明.md` |

原始只读盘点（`inspect_osm.py`）得到：1,957,486 个 Node、285,365 条 Way、5,273 条 Relation；其中 95,103 条 Way 带 `highway` 标签，2,081 条 Relation 标记为转向限制。`highway` 也包含 `footway`、`cycleway` 等类别，不能全部视为机动车道路。原始道路标签中 88,722 条缺少 `maxspeed`；该数字对应全部带 `highway` 标签的 Way，**不代表机动车道路的限速缺失率**。

## 2. 路网转换与优化方法

处理链由四个 Python 文件构成：

1. **`inspect_osm.py`**：只读检查原始 PBF 的对象数、道路类型、限速及限制转向标签。
2. **`convert_dc_osm.py`**：完成机动车道路过滤和初版 GraphML 转换，作为优化前的对照程序。
3. **`convert_dc_osm_optimized.py`**：只把实际参与路由连接的拓扑点写为图节点，并将中间形状点保存在边几何中，生成正式交付 GraphML。
4. **`validate_dc_network.py`**：检查图规模、连通性、边权合法性，并对部分起终点执行 Dijkstra/A* 路径代价对照。

### 2.1 机动车道路筛选

保留 `motorway`、`trunk`、`primary`、`secondary`、`tertiary`、`residential`、`unclassified`、`living_street`、`service` 及常见 `_link` 等指定道路类型；按 `access`、`vehicle`、`motor_vehicle`、`motorcar` 等标签排除常见禁行道路，并排除 `construction` 等不适用情况。该规则适用于教学路网实验，未涵盖全部条件性通行限制。

### 2.2 道路方向和拓扑

根据 `oneway=yes/-1/no`、环岛和 motorway 的隐含单向规则生成有向边；对方向不明确的 `reversible`、`alternating` 等情况采用简化排除处理。双向道路生成两个方向的连接，平行道路保留独立边。

以 Way 端点及被多条 Way 共享的节点作为道路边拆分点。中间形状节点用于保存 WKT `LINESTRING` 道路几何；道路长度由各相邻形状点之间的 Haversine 距离累加，单位为米。

### 2.3 节点精简

初版 GraphML 写入了所有引用到的形状点，共 160,520 个节点，其中只有 41,570 个参与道路连接。优化版仅将道路边端点写成 GraphML 节点，得到 **41,570 个节点、99,193 条有向边**，减少 **118,950 个冗余独立节点（约 74.1%）**。被移除的图节点对应的形状信息仍保存在边 `geometry` 属性中，因此不会因精简而将道路折线简单拉直。

### 2.4 速度与字段

优先解析 OSM `maxspeed` 标签，并将 mph 换算为 km/h；缺失或无法解析时按照道路等级赋予预设速度。GraphML 节点使用 `x=经度`、`y=纬度`；道路边包含连接端点、`length`（m）、`speed_kph`（km/h）、`highway`、`geometry`、`name`、`toll` 等信息。现有 `osm_loader.py` 负责将其加载为项目内部的 `Node`、`Edge`、`Graph` 结构，无须调整 Dijkstra/A* 核心算法。

需要注意：转换器虽然写出 `toll`，但此前核对的公共 `osm_loader.py` 未将该字段完整映射为 `Edge.toll`；因此不能把现有 `avoid_tolls` 的输出视为已验证的真实收费道路规避结果。

## 3. 实际运行与数据质量验证

以下数字来自已完成的本地路网处理与验证。将脚本移动到 A1 后，已重新运行验证程序，终端显示 `RESULT: BASIC CHECKS PASSED`。

| 指标 | 验证结果 |
|---|---:|
| GraphML 节点数 | 41,570 |
| 有向边数 | 99,193 |
| 孤立节点数 | 0 |
| 弱连通分量数量 | 347 |
| 最大弱连通分量节点数 | 39,978 |
| 强连通分量数量 | 893 |
| 最大强连通分量节点数 | 39,507 |
| 非法节点坐标、非正或非有限道路长度与速度、明显短于直线距离的道路边 | 均为 0 |
| 道路速度最大值 | 约 104.6 km/h |
| 最短、最快路径 Dijkstra/A* 代价对照 | 共 4 组，全部一致 |

数据质量结果保存在 `03_数据质量/dc_validation_optimized.json`。例如此前一次验证中，第一组“最短”查询的 Dijkstra 和 A* 代价均为 **20,550.398 m**，扩展状态数分别为 **95,906** 和 **28,759**，耗时分别为 **751.11 ms** 与 **339.12 ms**；第一组“最快”查询的 A* 耗时 **909.26 ms**，略长于 Dijkstra 的 **895.06 ms**。这些是特定运行环境和测试起终点下的记录，不能概括为 A* 对所有查询都更快。

移动文件后重新运行的验证还确认：图可正常读取；41,570 个节点和 99,193 条有向边均被加载；四组 Dijkstra/A* 代价对照一致。此类抽样检验**不能代替**完整交通规则验证，也不代表所有节点两两可达。

## 4. 与现有路径规划项目的接口关系

**本次提交范围限定为 A1 数据成果。** 交付物是可加载的 GraphML、数据处理与质量验证脚本、字段约定和接口说明，不直接修改公共模块：

- `src/path_planning/` 中的 Dijkstra、A* 等算法和核心图结构保持主分支版本。
- `api/main.py`、`web/index.html` 不作为此次 A1 PR 的修改内容。
- 项目默认校园路网与已有接口约定不因本次数据交付而自动切换。

此前曾在**本地适配版本**中完成使用 `ROUTE_GRAPHML` 指定华盛顿路网、优化 Leaflet 大路网选点与搜索过程显示等试验，并开展原有 56 项单元测试。这些属于集成探索与本地验证记录，**不表示当前 PR 已经将相应后端或前端功能合入 `main`**。正式切换数据源和大规模路网网页渲染，需要由公共模块负责人另行审核、集成和测试。

GraphML 的具体字段和加载约定另见 `02_字段与单位/华盛顿路网字段与单位说明.md` 与 `04_接口对接说明/华盛顿路网接口对接说明.md`。

## 5. 复现命令

以下命令均在项目**根目录**的 Windows PowerShell 终端执行；使用项目虚拟环境的 Python，原始数据需存在于前述 A1 路径。`osmium` 等依赖需要事先安装。

```powershell
$a1 = "workspaces/A1_数据"
$scripts = "$a1/05_文档报告/scripts"
$pbf = "$a1/01_路网清单/raw/district-of-columbia-261011.osm.pbf"
$graph = "$a1/01_路网清单/processed/dc_driving_optimized.graphml"

# 1. 原始数据盘点（明确指定输出位置）
python "$scripts/inspect_osm.py" "$pbf" --output "$a1/03_数据质量/osm_inspection.json"

# 2. 生成优化版路网；会覆盖指定 GraphML，请先备份已有验证成果
python "$scripts/convert_dc_osm_optimized.py" "$pbf" "$graph"

# 3. 验证图结构及路径代价
python "$scripts/validate_dc_network.py" --input "$graph" --output "$a1/03_数据质量/dc_validation_optimized.json" --max-checks 2
```

其中 `convert_dc_osm.py` 为保留的初版对照脚本，亦采用“输入 PBF 路径、输出 GraphML 路径”两个位置参数。若只需复核现有交付物，**无需重跑转换**，直接执行第 3 步即可。第 2 步重新生成文件后，应重新执行验证并确认结果。

以上命令中的 `python` 指当前终端已激活的项目虚拟环境解释器；未激活时可替换为 `\.venv\Scripts\python.exe`。`validate_dc_network.py` 已按新目录结构将仓库根目录定位为 `Path(__file__).resolve().parents[4]`，并支持从项目根目录传入上述相对路径。

此前原有 56 项单元测试针对项目原有功能；旧 `tools/smoke_api.py` 中固定的校园节点规模与经纬度断言不适合作为华盛顿路网的验收条件。**此次数据 PR 的核心验收依据，是 A1 交付文件及独立路网验证程序输出。**

## 6. 已知限制与后续工作

1. 尚未把 OSM Relation 中的禁止转向、条件转向等限制完整应用到图的路由状态中。
2. 部分道路速度采用按道路等级给出的默认值，不能替代实测限速。
3. 条件性通行、车道级信息与部分车辆类型限制仍采用简化模型。
4. 道路网络存在多个强、弱连通分量，起终点可能不可达。
5. 收费标签虽可随 GraphML 输出，仍需由加载器和偏好代价模块正确使用后才能验证收费规避效果。
6. 华盛顿路网切换、前端大图可视化及相关自动化测试尚待公共模块后续集成，不属于本次 A1 PR 的代码修改范围。

本成果适合课程项目的路网数据处理与路径规划算法实验，不应直接视为满足实际导航要求的交通规则完备路网。
