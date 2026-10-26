# 来源与许可记录

本文件保留组仓库提交 f3aa975ead356cbe8b72c3568739ac9c3bb62974 的来源记录。
本教程的地图、查询和评价均为Hilti同一采集序列的处理结果，不构成新增独立跨日期验证。

## 组仓库来源记录

# 代码与数据来源

## FAST-LIO 源码

- 上游：https://github.com/Ericsii/FAST_LIO
- 本机基准提交：`2fffc570a25d0df172720bac034fbdb6a13d2162`
- `week1_yin_anwei/fastlio_changes.patch` 相对该提交生成，包含本次修改及此前对 Hesai 字段的修改；配置文件独立提供。
- `week1_yin_anwei/fastlio_runtime_diagnostics.patch` 在上一个补丁之后应用，增加本次 PointCloud2 回放的接收/处理计数、可配置输入 QoS 和耗时摘要；不改几何、外参或时间计算。原默认 QoS 保留，新推荐命令显式选择 RELIABLE。
- 原始源码保留其原有版权和许可。应用补丁前应在该基准版本检查 `git apply --check`。

固定构建依赖：

| 仓库 | 提交 |
|---|---|
| [Livox-SDK2](https://github.com/Livox-SDK/Livox-SDK2) | `c0796f04c143143899c87a773d9f6b7136453c0b` |
| [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2) | `21445540f0d100dc86a7e6df312dd70bbdb4afdf` |
| [ikd-Tree](https://github.com/hku-mars/ikd-Tree)（FAST-LIO 子模块） | `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4` |

Python 直接依赖及验证后的完整版本分别见根目录 `requirements-*.txt` 和 `requirements-*.lock.txt`。evo 来源：[MichaelGrupp/evo](https://github.com/MichaelGrupp/evo)；rosbags 来源：[官方文档](https://ternaris.gitlab.io/rosbags/)。

## Hilti 数据集

来源：[Hilti-Research 官方 Hilti SLAM Challenge 2022 数据集](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022)。

- [标定文件](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/calibration/calibration_files/lidar_calibration.yaml)
- [exp18 IMU 真值](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/ground_truth/exp18_corridor_lower_gallery_2_imu.txt)
- [exp18 原始 ROS1 bag](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/rosbags/exp18_corridor_lower_gallery_2.bag)
- 数据集许可：CC BY-NC-SA 3.0；数据与地图的使用和再分发应遵守其非商业、署名及相同方式共享条款。
- 引用：Lintong Zhang 等，*Hilti-Oxford Dataset: A Millimeter-Accurate Benchmark for Simultaneous Localization and Mapping*，IEEE RA-L 8(1)，2023，408–415，DOI: 10.1109/LRA.2022.3226077。

`groundtruth_imu.txt` 是同序列官方真值；PCD 和估计轨迹是使用该数据集生成的运行结果。

2026-10-10 从上述官方真值地址重新下载，文件与归档逐字节 SHA256 一致：`138def6a40884a87372a4f18938cce5180d6aa7ad4e705349abf47ac4ec9fa32`，88,743 字节、789 位姿。时间范围 1649856227.723471–1649856314.319139 秒。尾段未评估由所用官方真值覆盖范围决定，并非本地文件截断。


## ROS2定位器来源记录

# 第二周来源与版本说明

## 定位器

- 上游：[myeongw002/FAST_LIO_LOCALIZATION_ROS2](https://github.com/myeongw002/FAST_LIO_LOCALIZATION_ROS2)。本地来自 `main` ZIP，未记录 Git commit，不能声称按提交固定。
- 归档 `global_localization_debug.py`、`global_localization_guarded.py`、`global_localization_synced.py`、`transform_fusion_checked.py`、`transform_fusion_event.py` 为本次调试修改版。修改内容：日志、原始点云时间戳保留、时间差保护、精确时间配对、事件触发输出与历史修正选择。
- `upstream/global_map_publisher.py` 和 `upstream/publish_initial_pose.py` 为本机下载的上游辅助脚本。
- 上游 GPL-2.0 许可全文见 [FAST_LIO_LOCALIZATION_LICENSE](upstream/FAST_LIO_LOCALIZATION_LICENSE)，以上衍生源码沿用其许可；不把上游代码声明为本项目原创。
- FAST-LIO 及 Hesai/QoS 修改来源沿用根目录 [SOURCES.md](../SOURCES.md)。


本包不含Scan Context、NCLT或KITTI实验输入。GPL-2.0原许可文本见 licenses/FAST_LIO_LOCALIZATION_LICENSE。固定查询点云、地图派生结果和参考位姿的数据来源及许可沿用上述Hilti记录。

原始组仓库：https://github.com/xiaoyinne/1
原PCD下载：https://github.com/xiaoyinne/1/releases/download/week1-hilti-exp18-v1/fastlio_hilti_fixed_20261008.pcd
原PCD SHA256：5513e08a55e7c9cc7187a5abd468157df86466151a0c1f27ace781384f49d52f

本包新增教程脚本与冻结上游定位器分别保存。归档不声称冻结了原先未记录的上游Git提交。
