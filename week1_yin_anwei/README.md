# 尹安伟第一周交付材料

目标：完成 Hilti bag → FAST-LIO 建图 → evo ATE 评估，统一为 PCD + KITTI 位姿 TXT。

## 已完成

- WSL2、Ubuntu 22.04、ROS2 Humble 环境。
- FAST-LIO 编译运行，Hilti exp18 点云和 IMU 输入适配。
- 完整序列半速播放，保存 PCD，CloudCompare 查看。
- 同次运行轨迹导出为 TUM 和 KITTI（附独立时间戳文件）。
- 使用官方 exp18 IMU 真值计算 evo ATE 并保存结果、误差图和轨迹图。

## 文件

| 文件 | 含义 |
|---|---|
| `trajectory_kitti.txt` | 每行 12 个数，行优先排列的 3×4 矩阵 `[R|t]`，`camera_init` 下 IMU/body 的位姿 |
| `trajectory_times.txt` | 与 KITTI 行一一对应的 ROS 时间戳（秒） |
| `trajectory_tum.txt` | `timestamp tx ty tz qx qy qz qw`，用于时间匹配评估 |
| `groundtruth_imu.txt` | 官方同序列 IMU 真值 |
| `ate_results.zip` | evo 数值结果 |
| `ate_error.png` | 平移误差曲线 |
| `ate_trajectory.png` | SE(3) 对齐后的估计轨迹与真值对比 |
| `map_screenshot.png` | CloudCompare 地图展示 |
| `hesai.yaml` | 本次运行配置 |
| `fastlio_changes.patch` | 相对本地 FAST-LIO Git HEAD 的代码修改；包括此前 Hesai 点类型修改 |
| `修复记录.md` | 原因、修改、运行与验证记录 |
| `第一周周报.md` | 半页周报草稿 |

完整地图另存于 `D:\chromeDownload\fastlio_hilti_fixed_20261008.pcd`，包含 7,042,489 点，225,359,901 字节。上传 Git 时按组内大文件约定处理；不要把 10.8 GiB 原始 bag 放入普通 Git。

## ATE 结果和范围

序列 `exp18_corridor_lower_gallery_2`；876 个估计位姿。平移 ATE 使用 SE(3) Umeyama 对齐、无尺度校正、0.05 秒时间匹配阈值。RMSE **0.167018 m**，均值 **0.143999 m**，最大值 **0.433353 m**。

该数值针对匹配的位姿，不等于全部地图点误差。原速运行仍不稳定，此次基线使用 `--rate 0.5`；地图中仍有远距离零散点。

## 复现

终端 1：

```bash
source /opt/ros/humble/setup.bash
source /home/yaw/ros2_ws/install/setup.bash
ros2 launch fast_lio mapping.launch.py config_path:=/home/yaw/ros2_ws/src/FAST_LIO/config config_file:=hesai.yaml use_sim_time:=true rviz:=false
```

终端 2：

```bash
source /opt/ros/humble/setup.bash
ros2 bag play /home/yaw/ros2_bag --clock --rate 0.5 --topics /hesai/pandar /alphasense/imu
```

播放一次结束后，FAST-LIO 终端按一次 Ctrl+C，等待保存完成。默认保存路径为 `hesai.yaml` 的 `map_file_path`；新运行会写该路径，需要事先保留既有结果。不要加 `--loop`。

## 还需要完成

1. 学生检查周报中的事实、确认是否有需要补充的内容。
2. 将配置、代码修改、轨迹、ATE 图表、截图、周报提交到组仓库，按组内约定共享 PCD，并记录 commit ID 和地图位置。
3. 确认组内格式规范（坐标系、单位、KITTI 行列顺序、时间戳配套）。

官方真值与标定来源：

- https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/ground_truth/exp18_corridor_lower_gallery_2_imu.txt
- https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/calibration/calibration_files/lidar_calibration.yaml
