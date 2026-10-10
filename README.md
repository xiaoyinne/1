# 尹安伟 · 第一周 FAST-LIO 建图与评估

Hilti 2022 `exp18_corridor_lower_gallery_2` 的 ROS2 FAST-LIO 半速基线。已交付累计 PCD、同次运行 TUM/KITTI 轨迹、evo 评估、源码补丁和复现工具。

**2026-10-08 基线：平移 ATE RMSE 0.167 m，仅针对成功匹配的 619 对位姿。** 估计轨迹共 876 个位姿、跨度 108.51 秒；匹配区间跨度 85.80 秒。末尾约 22.70 秒超出所用官方真值范围，未纳入精度评估。使用 SE(3) 对齐，无尺度校正，时间匹配阈值 0.05 秒。

| 项目 | 基线结果 |
|---|---:|
| 估计位姿 / 时间跨度 | 876 / 108.5084 s |
| 成功匹配位姿对 / 匹配时间跨度 | 619 / 85.7995 s |
| 平移 ATE RMSE / 最大误差 | 0.167018 m / 0.433353 m |
| 真值结束后的估计位姿 / 尾段时长 | 189 / 22.6993 s |
| 播放倍率 | 0.5 倍，单次播放 |
| 累计地图点数 / 文件大小 | 7,042,489 / 225,359,901 bytes |

这些指标衡量匹配位姿的平移误差，不代表整段轨迹或全部地图点的精度。地图保留了零散远距离点。

**复现验证的实际限制：** 2026-10-10 按补充流程完整复跑，同为半速，得到 482 个位姿、307 对匹配，ATE RMSE **0.845612 m**。流程可以执行，但历史精度尚不能保证稳定复现。两次结果并列保留，详见 [VALIDATION.md](VALIDATION.md)；后续需诊断半速重复性及原速稳定性。

![累计地图俯视投影](week1_yin_anwei/figures/map_top.png)

图中仅为显示裁切至 XY 的 1%–99% 分位范围并抽样，原始 PCD 未被裁切。局部结构见[细节图](week1_yin_anwei/figures/map_detail.png)；显示参数见[render_info.json](week1_yin_anwei/figures/render_info.json)。

![评估范围：蓝色为匹配位姿，橙色为真值范围外的未评估尾段](week1_yin_anwei/ate_scope.png)

## 获取与复现

- [完整地图下载与 SHA256](MAP_FILE.md)：GitHub Release 附件，约 215 MiB。
- [从原始数据到评估的流程](REPRODUCE.md)：源码版本、补丁、编译、bag 转换、自动运行、轨迹转换、评估和检查。
- [实测验证记录](VALIDATION.md)：记录本次实际验证范围和新运行结果，区分历史基线与复跑。
- [文件逐项说明](week1_yin_anwei/README.md)、[第一周周报](week1_yin_anwei/第一周周报.md)、[修复记录](week1_yin_anwei/修复记录.md)。
- [来源、固定版本与许可](SOURCES.md)、[第二周任务与验收](WEEK2_PLAN.md)。

## 结果与工具

基线数据均在 `week1_yin_anwei/`。地图对应轨迹为 `trajectory_tum.txt`；`trajectory_kitti.txt` 为未对齐的同一轨迹的 3×4 `[R|t]`，`trajectory_times.txt` 为对应时间戳。数值报告见 [evaluation_scope.json](week1_yin_anwei/evaluation_scope.json)。

`tools/` 提供 bag 转换、自动采集、TUM→KITTI、evo 包装、评估范围统计、PCD/轨迹一致性检查及真实点云绘图。每次运行使用新的目录保存配置、日志、地图和轨迹。脚本拒绝覆盖已有运行目录。

补丁仅适配本次 Hilti Hesai 点云：要求 FLOAT64 绝对秒 `timestamp`、与 header 同一时间轴、UINT16 `ring`。直接修改了 Velodyne 分支；更换雷达前必须重新检查字段和时间定义。
