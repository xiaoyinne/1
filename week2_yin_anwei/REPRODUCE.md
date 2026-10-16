# 第二周复现与检查

## 先检查归档结果（无需原始传感器数据）

在仓库根目录，使用安装 numpy、scipy 的 Python：

```bash
/usr/bin/python3 -s week2_yin_anwei/verify_evidence.py
```

核验源 manifest 的已公开文件哈希、Python 语法；从对齐轨迹重新计算 Hilti ATE；核对检索数量、23 对 ICP 结果、保存变换相对参考的误差及源脚本/描述子/参考哈希。此检查不会重跑 ROS 或原始点云配准。上传时的实际结果见 `VALIDATION.json`。

## 环境与目录

本次环境：WSL Ubuntu 22.04、ROS2 Humble；系统 Python + numpy 1.21.5、Open3D 0.14.1、scipy、tf_transformations、message_filters、sensor_msgs_py；ATE 使用第一周 `venv-eval` 的 evo。归档脚本保留原路径和原哈希，没有改为通用安装包。

- 第一周工作空间：`/home/yaw/week1_build_20261010`（没有额外 `/ws`）。
- 第二周目录：`/home/yaw/fastlio_week2`。
- Hilti 原始 ROS2 bag：`/home/yaw/week1_validation_20261010/ros2_bag`。
- 先验地图：`/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd`，SHA256 `5513e08a55e7c9cc7187a5abd468157df86466151a0c1f27ace781384f49d52f`。
- KITTI 解压目录：`/home/yaw/fastlio_week2/scancontext/data/kitti_raw/2011_09_30/`，包含 `2011_09_30_drive_0020_sync/{velodyne_points,oxts}` 和三个标定 TXT。

新环境可按原目录布置；也可复制脚本到新实验目录后统一修改路径，但此时需重新生成哈希。不要把归档 `runs` 覆盖进正在运行的实验。历史脚本多数拒绝覆盖输出，复跑应使用新的目录名，并同步修改下游输入路径。

## Hilti 节点启动顺序

每个终端先 `source /opt/ros/humble/setup.bash`，并设置 `export W=/home/yaw/fastlio_week2`。前端终端另加载第一周 `install/setup.bash`。先准备记录器，最后播放输入，避免遗漏初始化消息。以下 `$W` 指恢复后的第二周目录，辅助脚本可使用本仓库 `upstream` 中的副本。

1. 地图发布器：

```bash
python3 -s global_map_publisher.py --ros-args \
  -p map_file_path:=/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd \
  -p interval:=10 -p use_sim_time:=false
```

2. FAST-LIO：

```bash
ros2 run fast_lio fastlio_mapping --ros-args \
  --params-file "$W/config/hesai_localization_frontend.yaml"
```

3. 匹配节点：

```bash
python3 -s "$W/global_localization_synced.py" --ros-args \
  -p use_sim_time:=true -p map_voxel_size:=0.5 \
  -p scan_voxel_size:=0.5 -p freq_localization:=0.5 -p localization_th:=0.9
```

4. 融合节点：

```bash
python3 -s "$W/transform_fusion_event.py" --ros-args -p use_sim_time:=true
```

5. 用新的输出目录启动记录器：

```bash
ros2 bag record -o "$W/runs/new_run" \
  /initialpose /clock /Odometry /map_to_odom /localization
```

6. 回放：

```bash
ros2 bag play /home/yaw/week1_validation_20261010/ros2_bag \
  --rate 0.5 --clock --topics /hesai/pandar /alphasense/imu
```

收到地图及同步点云后暂停回放；在原实验的同序列起点，用单位修正初始化，再恢复播放：

```bash
ros2 topic pub --once -w 2 /initialpose geometry_msgs/msg/PoseWithCovarianceStamped \
  '{header: {frame_id: map}, pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, orientation: {x: 0.0, y: 0.0, z: 0.0, w: 1.0}}}}'
```

此定位器将初值用于地图到局部坐标的修正；不能随意等同于通常导航界面的机体绝对位姿。不同起点需重新确定坐标关系。本归档保留的是人工触发初始化的实验，不是 SC 自动初始化。

回放完成后停止记录器以写入 metadata。应使用消息 header 时间导出 TUM；该录制 bag 的存储时间是墙钟时间，不能代替传感器时间。历史导出/ATE 命令曾以终端临时脚本运行，未完整保存为端到端工具；归档提供最终 TUM、匹配/对齐轨迹、逐点误差和可重算检查脚本，不声称一条命令复现整场实验。

## KITTI 离线流程

1. 按上述目录放置用户从官网获得的点云、OXTS 和标定，不需要图片。
2. 从 [上游](https://github.com/gisbi-kim/PyICP-SLAM) 下载源码到 `$W/scancontext/vendor/PyICP-SLAM-master`，应用补丁并检查模块 SHA256。未固定上游提交，若不匹配，先核对代码而不是忽略差异。

```bash
cd "$W/scancontext/vendor/PyICP-SLAM-master"
git apply --check /path/to/repo/week2_yin_anwei/upstream/scancontext_zero_overlap.patch
git apply /path/to/repo/week2_yin_anwei/upstream/scancontext_zero_overlap.patch
sha256sum utils/ScanContextManager.py
```

3. 从 `artifacts/scancontext/` 复制脚本到 `$W/scancontext`，依次运行：

```text
prepare_kitti_reference.py
check_kitti_overlap.py
build_kitti_descriptors.py
retrieve_kitti_v1.py
verify_kitti_icp_v1.py
export_kitti_demo.py
```

调用形式为 `/usr/bin/python3 -s "$W/scancontext/<脚本名>"`。绘图脚本还需 matplotlib。先构造原始参考再插值；插值范围外的两帧不评估。ICP 使用 SC yaw、零平移初始化，参考位姿仅作事后对比。输出保存于 `scancontext/runs/kitti0020_*`。本次描述子构建约 353 秒、检索约 54 秒、23 对 ICP 约 6 秒；不是其他机器的速度保证。

## 本次公开范围

提供图文演示，没有录制视频。上述 KITTI 实验验证单次序列中的重复观测；另于2026-10-16新增 NCLT 单个日期组合的离线跨 session 检索与配准，见 [NCLT 运行顺序与归档校验](nclt/REPRODUCE.md)。尚未完成在线全局重定位或闭环优化。Hilti 定位退化结果及 SC 失败控制组一并保留。完整数据、编译依赖和大型地图请按来源另行获取。
