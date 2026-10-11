# 输入完整性与复跑诊断

这项实验针对第一周半速结果波动，不替换 2026-10-08 的历史地图、轨迹或 Release。所有实验使用同一 Hilti exp18 bag、同一 Hesai 算法参数；单次播放，不循环。

## 如何复跑

先按 [REPRODUCE.md](REPRODUCE.md) 获取固定源码并应用 `fastlio_changes.patch`。以下命令在 Ubuntu Bash 执行，沿用该说明中的 `REPO`、`WORK`、`EVAL_PY` 变量。

给已应用历史修复的源码增加运行计数和可配置 QoS，然后重新编译：

```bash
git -C "$WORK/ws/src/FAST_LIO" apply --check "$REPO/week1_yin_anwei/fastlio_runtime_diagnostics.patch"
git -C "$WORK/ws/src/FAST_LIO" apply "$REPO/week1_yin_anwei/fastlio_runtime_diagnostics.patch"
source /opt/ros/humble/setup.bash
cd "$WORK/ws"
PYTHONNOUSERSITE=1 colcon build --packages-select fast_lio --symlink-install --parallel-workers 2
source "$WORK/ws/install/setup.bash"
```

补丁默认保留原点云 BEST_EFFORT、深度 5、IMU RELIABLE、深度 10，不会自动改用可靠点云。它面向本仓库 Hilti PointCloud2 分支、单线程执行器和单次回放，不是通用多雷达诊断补丁。已经应用过时不要再次应用。

下面是可靠点云、大队列、半速实验命令。每次更换 `RUN`，不要覆盖之前的结果：

```bash
export RUN="$WORK/runs/reliable_rate05_$(date +%Y%m%d_%H%M%S)"
/usr/bin/python3 -s "$REPO/tools/verify_fastlio_save.py" \
  --workspace "$WORK/ws" --bag "$WORK/ros2_bag" \
  --config "$REPO/week1_yin_anwei/hesai.yaml" --run-dir "$RUN" \
  --rate 0.5 --timeout 600 --domain-id 87 \
  --lidar-depth 100 --imu-depth 20000 --lidar-reliability reliable
"$EVAL_PY" "$REPO/tools/runtime_report.py" \
  --manifest "$RUN/run_manifest.json" --output "$RUN/runtime_report.json"
```

随后执行复现说明第 6–7 步，检查 PCD、转换轨迹并用 evo 评估。不能仅凭采集脚本的 PASS 判定精度合格。

控制组改为 `--lidar-depth 5 --imu-depth 10 --lidar-reliability best_effort`；只检验队列的组使用 `100 / 20000 / best_effort`。速度对照仅把 `--rate 0.5` 改为 `--rate 1.0`。顺序执行，避免同时运行建图引入额外资源竞争。

**兼容性条件：** RELIABLE 订阅要求发布端提供兼容的可靠性策略。本次 rosbag2 发布端实测为 RELIABLE。不要直接把这套设置套到仅支持 BEST_EFFORT 的实时驱动上。QoS 的队列深度与可靠性是两个独立维度，见 [ROS2 官方 QoS 设计说明](https://design.ros2.org/articles/qos)。

## 计数含义与限制

- `bag_topic_counts`：文件内源消息数量，不等于成功发出或收到的数量。
- `lidar_received / imu_received`：FAST-LIO 实际进入回调的数量。源数量减回调数量称为“未观测输入”，包含播放发现/传输/队列/退出时未递交等可能性，不直接称为某一种 DDS 丢包。
- `synced_frames`：通过 LiDAR/IMU 时间同步、进入处理路径的帧数。
- 四类 skipped：首帧、初始化后未得到去畸变点云、建树阶段、下采样点不足。
- `odometry_published`：节点调用里程计发布的次数；与记录器的轨迹行数对比可以单独检查输出采集。
- `pending_lidar / pending_imu`：退出时应用层缓冲剩余消息，不包含 DDS 内尚未进入回调的消息。
- `no_effective_filter_updates`：滤波更新没有有效匹配的次数，不能简单当作输入丢帧数。
- `frame_wall_mean_s / max_s`：通过同步之后的定时器处理耗时，包含各跳过分支，不包含回调内点云预处理；不等同端到端延迟。
- CPU/RSS 每约 0.25 秒读取启动进程 PID 的 `/proc`，不统计子孙进程，也可能漏过瞬时峰值；100% CPU 表示一个逻辑核。

在无时间回跳的单次实验中应核对：`收到点云 = 同步处理 + 剩余点云`；`同步处理 = 四类跳过 + 发布里程计`。`runtime_report.py` 输出这两个关系的残差，不能把缺少计数报告解释为零丢帧。

完整结果及每次输入配置、源码差异、日志、轨迹和评估归档在 [validation/20261011_qos](validation/20261011_qos/)。原始 PCD 保留在该次独立运行目录，未将新实验地图替换到历史 Release。
