# G4 车辆导航可视化

基于 Leaflet 和 OpenStreetMap 数据的车辆路网导航实验页面，用于展示 Dijkstra 与 A* 的路径搜索过程。

## 运行

1. 使用 Python 运行 `start-server.bat`。
2. 浏览器访问 `http://localhost:5173/`。
3. 打开右上角菜单，加载武汉主要道路。
4. 在地图上依次点击起点和终点，再选择算法并开始规划。

也可以直接打开 `index.html` 查看页面，但部分浏览器会限制本地文件请求，建议使用本地 HTTP 服务。

## 功能

- OSM 主要道路路网加载
- 优先读取随项目提供的本地小范围 OSM 数据，缺失时回退到 Overpass API
- 起点、终点点击设置与拖动
- 端点自动吸附到最近的真实 OSM 道路节点
- Dijkstra 与 A* 路径搜索
- 已访问道路、访问节点、边界节点和最终路径动画
- 多种底图与页面皮肤

## 数据与服务说明

- 当前仓库已包含 `data/wuhan-main-roads.json`，是武汉光谷附近约 2 km × 2 km 的真实 OSM 主要道路小数据集。
- 本地数据包含 1,072 个道路节点和 182 条 OSM 道路，适合课程演示；它不是武汉全市完整路网，也不包含 POI。
- 地图底图使用 OpenStreetMap、Esri 或百度实验图层。
- 使用 OpenStreetMap 数据时请遵守其版权与使用政策。
- 本地数据会优先加载；只有本地文件缺失或损坏时，页面才请求 Overpass API。

要刷新本地路网文件，运行 `python tools/download_osm_network.py`。脚本优先访问
官方 OSM 小范围地图接口，失败时回退到 Overpass。请保留
`data/metadata.json` 和 JSON 内的来源、范围、时间及 ODbL 署名信息。

## 项目结构

```text
index.html          页面结构
app.js              地图、路网、Dijkstra/A* 与交互逻辑
styles.css          页面样式
assets/             页面资源
data/               本地 OSM 数据与元信息
tools/              OSM 数据下载脚本
start-server.bat   本地启动脚本
使用说明.txt        简要使用说明
```
