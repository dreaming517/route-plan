# 华盛顿 OSM 路网数据处理与系统适配说明

> 适用项目：G4 路径规划引擎（route-plan）。本文件只记录华盛顿特区数据接入的新增工作，原算法结构参见《路径规划模块开发说明》，搜索动画数据契约参见《SearchTrace接口规格》。

## 1. 数据与目标

使用 Geofabrik 提供的 OpenStreetMap（OSM）华盛顿特区区域提取数据 `data/raw/district-of-columbia-261011.osm.pbf`。Geofabrik 是 OSM 数据的区域分发渠道，PBF 中的 Node、Way、Relation 并不能直接供现有 `load_graphml()` 读取；原项目读取的是包含节点坐标和有向道路属性的 GraphML。坐标统一采用 WGS84 经纬度（lon、lat）。数据许可依 OSM 的 ODbL 1.0，© OpenStreetMap contributors。

原始只读检查（`tools/inspect_osm.py`）：1,957,486 个 Node、285,365 条 Way、5,273 条 Relation；其中 95,103 条 Way 带 `highway` 标签，2,081 条 Relation 标记为转向限制。`highway` 也含 footway、cycleway 等，不能全作为机动车道路。原始道路标签中 88,722 条缺少 `maxspeed`；此数字涉及全部 highway Way，不能视为机动车道路缺失率。

## 2. 数据格式转换

处理程序依次为 `inspect_osm.py`（只读盘点）、`convert_dc_osm.py`（初版）、`convert_dc_osm_optimized.py`（正式版）、`validate_dc_network.py`（检验）。**正式运行读取 `dc_driving_optimized.graphml`，原始 PBF 保持不变。**

1. **可通行道路筛选。** 保留 motorway、trunk、primary、secondary、tertiary、residential、unclassified、living_street、service 及主要 `_link` 等指定道路等级；排除常见 `access`、`vehicle`、`motor_vehicle`、`motorcar` 禁行标签及 construction 等。此规则为教学用途的简化机动车筛选，不涵盖全部条件性限制。
2. **有向性处理。** 根据 `oneway=yes/-1/no`、环岛和 motorway 的隐含规则生成正向边、反向边或双向各一条边；方向不确定的 `reversible/alternating` 排除。保留平行道路对应的独立边，不把双向道路当作一条无向边。
3. **拓扑构建与节点精简。** OSM Way 的首尾及被多条 Way 共享的节点作为道路边的拆分点；中间形状点用于构成 WKT `LINESTRING`，并累加分段 Haversine 距离（米）。初版把所有引用的形状点也写成 GraphML 节点，生成 160,520 个节点但实际仅 41,570 个参与道路连接；优化版只写道路边端点，得到 41,570 个图节点、有向边仍为 99,193 条，减少了 118,950 个不参与连接的独立节点（约 74.1%）。形状点仍保留在边的 geometry 中，没有因精简而拉直路线。
4. **速度与字段映射。** 有可解析 `maxspeed` 时读取数值，mph 换算为 km/h；缺失或不能解析时按道路等级赋予预设速度。GraphML 节点 `x=经度`、`y=纬度`；边包含 `source`、`target`、`length`（米）、`speed_kph`（km/h）、`highway`、`geometry`、`name`、`toll` 等，符合原有加载器的关键字段要求。`osm_loader.py` 将其构造为 `Node` / `Edge` / `Graph`，采用以边为键的出邻接表执行路由；无需改写 Dijkstra/A*。

**注意：** 转换器虽将 `toll` 写入 GraphML，当前 `osm_loader.py` 没有将其加载为 `Edge.toll`；因此 `avoid_tolls` 对本数据的表现还不能当作真实收费道路规避结果。

## 3. 转换后验证（来自实际输出）

| 指标 | 优化版结果 |
|---|---:|
| GraphML 节点 / 有向边 | 41,570 / 99,193 |
| 孤立节点 | 0 |
| 弱连通分量 / 最大分量 | 347 / 39,978 节点 |
| 强连通分量 / 最大分量 | 893 / 39,507 节点 |
| 非法坐标、无效长度、无效速度、明显短于端点直线距离的边 | 均为 0 |
| 道路速度中位数 / 最大值 | 30.0 / 104.607 km/h |
| GraphML 加载时间（本次） | 2.321 s |

`data/processed/dc_validation_optimized.json` 记录了最大强连通分量内两方向 × 最短/最快共 4 次 Dijkstra–A* 对照，**4 组代价全部一致**。例如第一组“最短”Dijkstra 与 A* 均为 20,550.398 m，扩展状态数分别为 95,906 与 28,759；本次耗时分别 751.11 ms 与 339.12 ms。但第一组“最快”A* 909.26 ms，略慢于 Dijkstra 895.06 ms；这些时间仅为本次机器与样本下的记录，不应推断 A* 在所有查询中均更快。当前测试也不能替代全面的交通规则正确性验证。

## 4. 后端与网页适配（不更改算法内核）

- `api/main.py` 原本把 GraphML 路径写死为 `data/campus_552.graphml`。改为读取环境变量 `ROUTE_GRAPHML`，未设置仍使用校园路网，保留旧测试和成员基线。`/api/meta` 的版本字段对应当前文件名；`/api/nodes` 与 `/api/route` 的基本接口不变。
- 原 `web/index.html` 为全部路口建立 `L.circleMarker`。在校园 552 节点时尚可，在华盛顿 41,570 节点时密集圆点覆盖地图且大量图层增加渲染负担。新前端默认不绘制全部路口标记，点击地图后匹配最近道路节点，保留起终点选择、偏好设置、路线和搜索过程动画。
- 新前端的动画按原始搜索步数选取显示帧，并对显示的搜索节点抽样；路径搜索仍在完整图上执行。此项是**可视化适配**，不是 GraphML 格式转换；并不代表全部搜索过程细节逐帧显示。

## 5. 复现命令、文件位置与限制

以下命令均从项目根目录执行，在 Windows PowerShell 中先确保 `.venv` 已安装 `osmium`、FastAPI/uvicorn 等相应依赖：

```powershell
.\.venv\Scripts\python.exe tools\inspect_osm.py data\raw\district-of-columbia-261011.osm.pbf
.\.venv\Scripts\python.exe tools\convert_dc_osm.py data\raw\district-of-columbia-261011.osm.pbf data\processed\dc_driving.graphml
.\.venv\Scripts\python.exe tools\convert_dc_osm_optimized.py data\raw\district-of-columbia-261011.osm.pbf data\processed\dc_driving_optimized.graphml
.\.venv\Scripts\python.exe tools\validate_dc_network.py --input data/processed/dc_driving_optimized.graphml --output data/processed/dc_validation_optimized.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$env:ROUTE_GRAPHML="data/processed/dc_driving_optimized.graphml"
.\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8077
```

浏览器打开 `http://127.0.0.1:8077`。原校园数据仍保留；如需切回，取消 `ROUTE_GRAPHML` 环境变量并**重启**服务。现有 56 项测试针对原项目基线；本轮用户确认不新增自动化测试。注意旧 `tools/smoke_api.py` 中的节点数与经纬度断言固定针对校园数据，不能直接作为华盛顿数据的通过标准。

**局限与后续：** 尚未导入 OSM Relation 的禁止转向及转向惩罚；条件性通行、车道级限制与部分速度使用简化规则。区域边界和非主连通分量可能导致起终点不可达。收费偏好因加载字段缺失不能保证真实效果；本版适合课程路径规划算法实验，不应宣称可直接用于合规的实际导航。
