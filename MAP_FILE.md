# 完整地图文件信息

- 文件名：`fastlio_hilti_fixed_20261008.pcd`
- 本机位置：`D:\chromeDownload\fastlio_hilti_fixed_20261008.pcd`
- 格式：PCD v0.7，binary
- 点数：7,042,489
- 文件字节数：225,359,901
- SHA256：`5513e08a55e7c9cc7187a5abd468157df86466151a0c1f27ace781384f49d52f`
- 数据序列：Hilti 2022 `exp18_corridor_lower_gallery_2`
- 配置：[hesai.yaml](week1_yin_anwei/hesai.yaml)
- 配套位姿：876 行 KITTI 轨迹及对应时间戳，见 `week1_yin_anwei/`
- 完整地图在线下载地址：待补充。

PCD 的字段为 `x y z intensity normal_x normal_y normal_z curvature`。坐标对应 FAST-LIO 的 `camera_init` 世界坐标系，单位米。文件保存的是累计配准扫描点云，并非提供了点级准确性保证的真值地图。
