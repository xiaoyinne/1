# 代码与数据来源

## FAST-LIO 源码

- 上游：https://github.com/Ericsii/FAST_LIO
- 本机基准提交：`2fffc570a25d0df172720bac034fbdb6a13d2162`
- `week1_yin_anwei/fastlio_changes.patch` 相对该提交生成，包含本次修改及此前对 Hesai 字段的修改；配置文件独立提供。
- 原始源码保留其原有版权和许可。应用补丁前应在该基准版本检查 `git apply --check`。

## Hilti 数据集

来源：[Hilti-Research 官方 Hilti SLAM Challenge 2022 数据集](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022)。

- [标定文件](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/calibration/calibration_files/lidar_calibration.yaml)
- [exp18 IMU 真值](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/ground_truth/exp18_corridor_lower_gallery_2_imu.txt)
- 数据集许可：CC BY-NC-SA 3.0；数据与地图的使用和再分发应遵守其非商业、署名及相同方式共享条款。
- 引用：Lintong Zhang 等，*Hilti-Oxford Dataset: A Millimeter-Accurate Benchmark for Simultaneous Localization and Mapping*，IEEE RA-L 8(1)，2023，408–415，DOI: 10.1109/LRA.2022.3226077。

`groundtruth_imu.txt` 是同序列官方真值；PCD 和估计轨迹是使用该数据集生成的运行结果。
