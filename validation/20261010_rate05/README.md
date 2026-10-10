# 完整复跑记录（2026-10-10）

新编译源码、新转换 bag、半速单次回放。此次 RMSE 为 0.845612 m，**未复现历史基线精度**。保留这次运行，用于后续定位差异；不替换 `week1_yin_anwei/` 下的历史交付。

- `run_manifest.json`：实际命令、时间、环境、配置/二进制/源码差异哈希、退出状态、输出数量。
- `input_config.yaml` / `config.yaml`：原配置和本次生效配置。
- `source.patch`：新构建工作区相对固定上游提交的修改。
- `conversion_manifest.json`：原始 bag 转换工具版本和命令。
- `mapping.log` / `bag.log`：完整进程日志。
- `trajectory_tum.txt`、`trajectory_kitti.txt`、`trajectory_times.txt`：同次运行的 482 个位姿。
- `artifact_checks.json`：PCD 与轨迹结构检查。
- `evaluation/`：本次独立 ATE、范围报告和图。

PCD 留在本机 `/home/yaw/week1_validation_20261010/runs/exp18_rate05/map.pcd`，哈希见清单。GitHub Release 地图是 2026-10-08 基线地图，与本目录新轨迹不配套；不能混用。

`run_manifest.json` 的 `completed_needs_accuracy_evaluation` 表示采集阶段完成；后续评估已经执行，结果在 `evaluation/`。采集成功不等于精度通过。
