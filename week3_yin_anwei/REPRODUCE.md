# 第三周当前28组实验：复核与复现

## 三个层次

1. **核对交付字节。**在仓库内运行`python week3_yin_anwei/verify_package.py`，检查当前清单与原归档清单、固定查询数量、28组尝试和修正记录。该命令不重跑ICP。
2. **复核保存的结果。**查看[原核验记录](experiment_20261020/validation.json)、逐组`attempts.csv`、修正矩阵、TUM轨迹与误差CSV。保存的结果是历史实验，不把重新核对算术称为独立端到端复现。
3. **重跑点云实验。**需要原PCD、ROS2 Humble、Open3D、NumPy和评价环境，并处理本机绝对路径。原11GB传感器bag和408MB查询录制未重复打包；本包已保留53帧扫描和1091条里程计，重跑固定查询不必重新执行前端。

## 原图来源

- 原PCD发布：[week1-hilti-exp18-v1](https://github.com/xiaoyinne/1/releases/download/week1-hilti-exp18-v1/fastlio_hilti_fixed_20261008.pcd)
- 原图SHA256：`5513e08a55e7c9cc7187a5abd468157df86466151a0c1f27ace781384f49d52f`
- 详细上游与数据许可：[SOURCES.md](experiment_20261020/SOURCES.md)，定位器许可全文在[licenses](experiment_20261020/licenses)。

## 目录与环境

原机器把实验根目录放在`/home/yaw/fastlio_week3`，并使用：

- `RUN_DIR=/home/yaw/fastlio_week3/runs/clean_20261020_155929_tQ0v`
- 原图`/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd`
- 系统`/usr/bin/python3 -s`运行ROS/Open3D脚本。
- `/home/yaw/week1_validation_20261010/venv-eval/bin/python`运行evo评价脚本。

在新机器复现时，可将`experiment_20261020`复制到新的实验根目录，统一替换脚本中的绝对路径及Python环境路径，修订后保存为新版本。不要修改已归档目录然后继续宣称哈希未变。各脚本输出目录大多要求尚不存在。

主要程序顺序：

1. [generate_noisy_map.py](experiment_20261020/tools/generate_noisy_map.py)或[generate_deleted_map.py](experiment_20261020/tools/generate_deleted_map.py)生成单因素地图变体。
2. [run_fixed_matching.py](experiment_20261020/tools/run_fixed_matching.py)读取固定扫描与里程计，初值为单位矩阵，记录每次fitness与接受标志，保存修正。
3. [fuse_fixed_trajectory.py](experiment_20261020/tools/fuse_fixed_trajectory.py)为每条里程计选时间不晚于它的最近接受修正，生成TUM位姿。首次接受之前不输出，不倒填早期时间。
4. [evaluate_fixed_trajectory.py](experiment_20261020/tools/evaluate_fixed_trajectory.py)使用保存的753对时间关联，独立无尺度SE(3)对齐后计算平移ATE。覆盖不足的删块组按[batch_deletion.py](experiment_20261020/tools/batch_deletion.py)中的规则留空主ATE。
5. [batch_noise.py](experiment_20261020/tools/batch_noise.py)、[batch_deletion.py](experiment_20261020/tools/batch_deletion.py)用于批量运行，[classify_deletion.py](experiment_20261020/tools/classify_deletion.py)记录事后工作标记。

## 比较口径

- 原图1组，sigma四档×3种子，删块五档×3种子，共28组。
- 每组固定53次配准，使用同样的前端输入、参数与初始猜测。
- ATE必须覆盖全部753个固定评价时刻，约83秒；不使用95%覆盖替代条件。
- 地图修正间隔覆盖完整109.008数据秒，计入首次接受前和最后接受后的时段。
- 接受门槛为最终细阶段fitness严格大于0.9。接受不保证位姿正确。
- 本轮事后分析标记为ATE严格大于两倍clean、最长间隔严格大于10秒，以及固定评价覆盖不足。不要套用其他运行的clean、774个样本或46组旧草稿的标准。

本次GitHub整理验证原归档与新材料的字节、数量和基本数值一致性，未再次运行全部ICP或声称在新机器独立重现全部指标。
