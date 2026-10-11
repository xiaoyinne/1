# 第一周文件说明

本目录保存 2026-10-08 半速完整回放的基线结果。2026-10-10 的补充工作增加了复现工具和验证记录，未替换本目录的历史轨迹及 ATE 原始结果。

| 文件 | 内容和用途 |
|---|---|
| `trajectory_tum.txt` | `/Odometry` 采集的 `timestamp tx ty tz qx qy qz qw`；`camera_init` 下 IMU/body 位姿，米、秒 |
| `trajectory_kitti.txt` | 同一轨迹，逐行展开的 3×4 `[R\|t]`；无对齐、无尺度变换、无原点重置 |
| `trajectory_times.txt` | 与 KITTI 每行对应的时间戳 |
| `groundtruth_imu.txt` | 官方 exp18 IMU 真值；已与官方文件核对完整性 |
| `ate_results.zip` | evo 原始评估结果，619 对匹配位姿 |
| `evaluation_scope.json` | 脚本重新统计的时间范围、匹配数量、误差及输入 SHA256 |
| `ate_scope.png` | 标注已匹配部分和未评估尾段的轨迹图 |
| `ate_error.png` / `ate_trajectory.png` | 原始 evo 误差图和轨迹图 |
| `map_screenshot.png` | CloudCompare 查看基线地图时的截图 |
| `figures/map_top.png` / `figures/map_detail.png` | 真实 PCD 的俯视和局部投影；显示抽样/裁切参数写在图中及 JSON |
| `hesai.yaml` | 历史运行参数；自动采集脚本复制配置并覆盖本次输出路径 |
| `fastlio_changes.patch` | 相对固定上游提交的 Hesai 时间字段及 PCD 保存修复 |
| `fastlio_runtime_diagnostics.patch` | 在历史修复之后应用的运行计数与可配置输入 QoS 补丁；2026-10-11 新实验使用 |
| `修复记录.md` | 故障原因、修复范围和已知限制 |
| `第一周周报.md` | 已整理的第一周交付汇报 |

估计轨迹共 876 位姿、108.51 秒。在 0.05 秒匹配阈值下，匹配 619 对位姿，区间跨度 85.80 秒；SE(3) 对齐、不校正尺度，平移 ATE RMSE 0.167018 m，最大误差 0.433353 m。末尾 189 个估计位姿、约 22.70 秒超出官方真值范围，未评估。

轨迹时间取 `Odometry.header.stamp`（FAST-LIO 扫描结束时刻），不使用消息接收时的电脑时间。估计位姿为 IMU/body；真值选用官方 `_imu.txt`，避免混用 LiDAR 真值与 IMU 估计。

完整执行流程见 [REPRODUCE.md](../REPRODUCE.md)，PCD 下载见 [MAP_FILE.md](../MAP_FILE.md)，验证情况见 [VALIDATION.md](../VALIDATION.md)。
