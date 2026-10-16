# 第二周来源与版本说明

## 定位器

- 上游：[myeongw002/FAST_LIO_LOCALIZATION_ROS2](https://github.com/myeongw002/FAST_LIO_LOCALIZATION_ROS2)。本地来自 `main` ZIP，未记录 Git commit，不能声称按提交固定。
- 归档 `global_localization_debug.py`、`global_localization_guarded.py`、`global_localization_synced.py`、`transform_fusion_checked.py`、`transform_fusion_event.py` 为本次调试修改版。修改内容：日志、原始点云时间戳保留、时间差保护、精确时间配对、事件触发输出与历史修正选择。
- `upstream/global_map_publisher.py` 和 `upstream/publish_initial_pose.py` 为本机下载的上游辅助脚本。
- 上游 GPL-2.0 许可全文见 [FAST_LIO_LOCALIZATION_LICENSE](upstream/FAST_LIO_LOCALIZATION_LICENSE)，以上衍生源码沿用其许可；不把上游代码声明为本项目原创。
- FAST-LIO 及 Hesai/QoS 修改来源沿用根目录 [SOURCES.md](../SOURCES.md)。

## Scan Context

- 上游：[gisbi-kim/PyICP-SLAM](https://github.com/gisbi-kim/PyICP-SLAM)，本地来自 `master` ZIP，未记录 commit。
- 不重复分发 `ScanContextManager.py` 正文或原始备份；下载上游后应用 [零重叠保护补丁](upstream/scancontext_zero_overlap.patch)。上游 README 副本仅作来源说明，不代表获得额外许可。
- 本次使用的补丁后模块 SHA256：`956938ea658270e7908a9e047e69bb0010d0a0f8efa70cb50e46ec44e1f24c72`。原始文件 SHA256 见源归档 manifest。更换上游版本前必须重新检查，不能默认行为相同。
- 补丁仅将共同有效扇区数为零时的相似度设为零，避免除零；不改变其余余弦匹配规则。

## 数据与参考位姿

- NCLT 跨日期实验的数据来源、署名、许可及文件范围见 [NCLT 来源说明](nclt/SOURCES.md)。主数据集工作使用 NCLT + Hilti，KITTI 为补充验证。

- Hilti 数据、真值及地图来源和许可见根目录 [SOURCES.md](../SOURCES.md) 和 [MAP_FILE.md](../MAP_FILE.md)。本次同序列先验地图定位不构成独立跨 session 验证。
- KITTI raw：[官网](https://www.cvlibs.net/datasets/kitti/raw_data.php)，`2011_09_30_drive_0020_sync.zip`、`2011_09_30_calib.zip`。遵守原数据集的使用和署名条款；不上传原始图像、Velodyne 文件或大型下载包。
- OXTS 投影与姿态转换参照 [pykitti utils.py](https://github.com/utiasSTARS/pykitti/blob/master/pykitti/utils.py)。参考位姿来自原始 OXTS，并非另行下载的 KITTI Odometry benchmark poses；两者不可混称。
- Python/Open3D/scipy/evo 版本与运行方式见复现说明。记录的文件哈希固定本次产物内容，不等同于完整环境可复现保证。
