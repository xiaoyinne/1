# 从原始 bag 到地图、轨迹和 ATE

目标环境：Ubuntu 22.04（可在 WSL2）、ROS2 Humble、Python 3.10。所有以下命令在 **Ubuntu Bash** 执行；输入命令时不包含终端提示符。路径含空格时保留双引号。2026-10-11 推荐流程增加输入 QoS 补丁，显式使用可靠点云和大队列；两次半速测试均收到完整输入，ATE 为 0.196888 m。它不等于精确重演历史 0.167 m，仍须评估每次新运行。实测范围及尾帧限制见 [VALIDATION.md](VALIDATION.md) 和 [运行对照](validation/20261011_qos/)。

## 1. 环境与交付仓库

先按 [ROS2 Humble 官方 Ubuntu 安装说明](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debs.html) 安装 ROS2。已安装的机器不用重复安装 ROS。编译及运行依赖：

```bash
sudo apt update
sudo apt install build-essential cmake git curl libeigen3-dev libpcl-dev libapr1-dev \
  python3-dev python3-pip python3-venv python3-numpy python3-yaml \
  python3-colcon-common-extensions python3-rosdep \
  ros-humble-desktop ros-humble-pcl-ros ros-humble-pcl-conversions \
  ros-humble-ament-cmake-auto ros-humble-rosidl-default-generators \
  ros-humble-rosbag2-storage-default-plugins
git clone https://github.com/xiaoyinne/1.git week1-delivery
cd week1-delivery
export REPO="$PWD"
export WORK="$HOME/fastlio_week1_repro"
mkdir "$WORK"
```

`WORK` 必须是新目录，保存源码、构建结果、Python 环境、转换数据和运行结果。新开终端时重新设置 `REPO`、`WORK`；后续命令都依赖这两个变量。

## 2. 固定源码、依赖与补丁

输入：固定版本源码、交付补丁。输出：`$WORK/ws/install/fast_lio/`。

```bash
git clone https://github.com/Livox-SDK/Livox-SDK2.git "$WORK/Livox-SDK2"
git -C "$WORK/Livox-SDK2" checkout --detach c0796f04c143143899c87a773d9f6b7136453c0b
cmake -S "$WORK/Livox-SDK2" -B "$WORK/sdk-build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$WORK/sdk-build" -j2
sudo cmake --install "$WORK/sdk-build"
sudo ldconfig

mkdir -p "$WORK/ws/src"
git clone https://github.com/Livox-SDK/livox_ros_driver2.git "$WORK/ws/src/livox_ros_driver2"
git -C "$WORK/ws/src/livox_ros_driver2" checkout --detach 21445540f0d100dc86a7e6df312dd70bbdb4afdf
cp "$WORK/ws/src/livox_ros_driver2/package_ROS2.xml" "$WORK/ws/src/livox_ros_driver2/package.xml"
cp -r "$WORK/ws/src/livox_ros_driver2/launch_ROS2" "$WORK/ws/src/livox_ros_driver2/launch"

git clone https://github.com/Ericsii/FAST_LIO.git "$WORK/ws/src/FAST_LIO"
git -C "$WORK/ws/src/FAST_LIO" checkout --detach 2fffc570a25d0df172720bac034fbdb6a13d2162
git -C "$WORK/ws/src/FAST_LIO" submodule update --init --recursive
git -C "$WORK/ws/src/FAST_LIO" apply --check "$REPO/week1_yin_anwei/fastlio_changes.patch"
git -C "$WORK/ws/src/FAST_LIO" apply "$REPO/week1_yin_anwei/fastlio_changes.patch"
git -C "$WORK/ws/src/FAST_LIO" apply --check "$REPO/week1_yin_anwei/fastlio_runtime_diagnostics.patch"
git -C "$WORK/ws/src/FAST_LIO" apply "$REPO/week1_yin_anwei/fastlio_runtime_diagnostics.patch"

source /opt/ros/humble/setup.bash
cd "$WORK/ws"
PYTHONNOUSERSITE=1 colcon build --symlink-install --parallel-workers 2 \
  --cmake-args -DROS_EDITION=ROS2 -DDISTRO_ROS=humble -DCMAKE_BUILD_TYPE=Release
source "$WORK/ws/install/setup.bash"
ros2 pkg executables fast_lio
```

期望最后显示 `fast_lio fastlio_mapping`。FAST-LIO 虽读取 Hesai，编译仍依赖 Livox 消息类型。上面直接准备 ROS2 package/launch 文件后运行 colcon，不调用上游会清理工作区的 `build.sh`。已安装同版本 SDK 时可复用；此次验证明确记录了这一前提。

## 3. 分离 Python 环境

ROS 节点工具使用 `/usr/bin/python3 -s`，避开用户目录中可能与 ROS 不兼容的 NumPy。转换和评估使用独立 venv，不激活到 ROS 构建终端中。

```bash
python3 -m venv "$WORK/venv-bag"
"$WORK/venv-bag/bin/python" -m pip install -r "$REPO/requirements-bag.lock.txt"
python3 -m venv "$WORK/venv-eval"
"$WORK/venv-eval/bin/python" -m pip install -r "$REPO/requirements-eval.lock.txt"
export EVAL_PY="$WORK/venv-eval/bin/python"
```

`requirements-*.txt` 列出直接依赖，`requirements-*.lock.txt` 固定本次验证的完整依赖版本。evo 1.37.1、NumPy 2.2.6、SciPy 1.15.3、Matplotlib 3.10.7；rosbags 0.11.5。原机器缺少 ensurepip 时，本次验证使用 `venv --without-pip`，向新 venv 的 site-packages 安装 pip 24.3.1 后安装依赖；按第 1 步安装 `python3-venv` 后通常无需该替代操作。

## 4. 原始数据与 bag 转换

从 [Hilti 官方数据文件](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/rosbags/exp18_corridor_lower_gallery_2.bag) 获取 `exp18_corridor_lower_gallery_2.bag`。遵循数据集署名和非商业许可。本机原始文件示例：`/mnt/d/chromeDownload/exp18_corridor_lower_gallery_2.bag`。根据实际下载位置设置 `RAW_BAG`。尚未下载时可执行：

```bash
curl -fL --retry 3 -C - \
  https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/resolve/main/rosbags/exp18_corridor_lower_gallery_2.bag \
  -o "$WORK/exp18_corridor_lower_gallery_2.bag"
```

使用此命令下载后，把下一段 `RAW_BAG` 改为 `$WORK/exp18_corridor_lower_gallery_2.bag`。

输入：ROS1 `.bag`；输出：ROS2 sqlite3 bag 目录及转换记录。

```bash
export RAW_BAG=/mnt/d/chromeDownload/exp18_corridor_lower_gallery_2.bag
"$WORK/venv-bag/bin/python" "$REPO/tools/convert_bag.py" \
  --src "$RAW_BAG" --dst "$WORK/ros2_bag"
source /opt/ros/humble/setup.bash
ros2 bag info "$WORK/ros2_bag"
```

该序列约 109.4049 秒，源点云 `/hesai/pandar` 1,094 帧，IMU `/alphasense/imu` 43,656 条，总消息 66,633 条。脚本保留转换后原始 metadata，并把 `offered_qos_profiles` 的列表规范为 Humble 读取的字符串（空列表改为空字符串）。已存在的输出目录会被拒绝，不能用同一路径重复转换。

若已经有正确转换的 bag，可跳过转换，把后续 `--bag` 指向已有目录。第一次复现建议走完整转换路径。

## 5. 一次运行同时保存地图、轨迹和日志

输入：Hesai 配置、ROS2 bag、编译好的 FAST-LIO。输出：独立运行目录。保持单次播放；不要加 `--loop`。默认半速，约需 220 秒播放，加上初始化及保存时间。

```bash
source /opt/ros/humble/setup.bash
source "$WORK/ws/install/setup.bash"
export RUN="$WORK/runs/exp18_rate05_$(date +%Y%m%d_%H%M%S)"
/usr/bin/python3 -s "$REPO/tools/verify_fastlio_save.py" \
  --workspace "$WORK/ws" --bag "$WORK/ros2_bag" \
  --config "$REPO/week1_yin_anwei/hesai.yaml" --run-dir "$RUN" \
  --rate 0.5 --timeout 600 --domain-id 87 \
  --lidar-depth 100 --imu-depth 20000 --lidar-reliability reliable
```

脚本在指定 ROS domain 内启动 FAST-LIO，确认初始化和订阅发现后播放 bag，录制 `/Odometry`。回放结束、输出短暂静默后发一次 SIGINT，让 FAST-LIO 退出保存地图。只结束它自己启动的进程组。超时、子进程异常、空轨迹、缺少地图或 `No Effective Points` 都会标记失败并保留诊断文件。不要让其他节点在同一 domain 发布 `/Odometry`。

本数据 rosbag2 发布端实测为 RELIABLE；如果更换成仅支持 BEST_EFFORT 的驱动，不能直接沿用可靠订阅。查看节点输入计数及实验对照的方法见 [RUNTIME_DIAGNOSTICS.md](RUNTIME_DIAGNOSTICS.md)。历史小队列/BEST_EFFORT 配置仍可显式选择用于对照，不推荐作为本机默认流程。

```text
exp18_rate05_.../
  input_config.yaml       原始交付配置
  config.yaml             本次实际配置（含输出路径和 use_sim_time）
  source.patch            本次源码相对 HEAD 的差异
  run_manifest.json       源码/二进制/配置哈希、输入计数、运行命令和结果
  mapping.log / bag.log   两个进程的日志
  map.pcd                 退出时保存的累计点云
  trajectory_tum.txt      本次 /Odometry 采集结果
```

`pcd_save.pcd_save_en=true`、`interval=-1` 保证累计为一个文件。修复的是退出保存；`map_save` 服务未验证。原配置中的本机 `map_file_path` 由脚本覆盖为 `$RUN/map.pcd`。

运行清单包含源 bag、节点实际接收/处理/跳过/发布计数以及进程资源采样。执行下面命令生成对账报告；可靠组实测末尾仍有 1 帧已收到但未处理，不能把完整接收等同于逐帧完整处理：

```bash
"$EVAL_PY" "$REPO/tools/runtime_report.py" \
  --manifest "$RUN/run_manifest.json" --output "$RUN/runtime_report.json"
```

位姿含义：`camera_init` 下 IMU/body 的 `[R|t]`，`p_world = R × p_body + t`；平移米，四元数顺序 xyzw。时间取 `Odometry.header.stamp`，源码设为扫描结束时间，不是电脑墙钟。配套真值选官方 `_imu.txt`。

## 6. TUM 转 KITTI 并检查文件

```bash
"$EVAL_PY" "$REPO/tools/export_trajectory.py" \
  --tum "$RUN/trajectory_tum.txt" --output-dir "$RUN"
"$EVAL_PY" "$REPO/tools/check_results.py" \
  --pcd "$RUN/map.pcd" --tum "$RUN/trajectory_tum.txt" \
  --kitti "$RUN/trajectory_kitti.txt" --times "$RUN/trajectory_times.txt" \
  --mapping-log "$RUN/mapping.log" --output "$RUN/artifact_checks.json"
```

输出 KITTI 每行 12 数，按行展开 `[R|t]`，时间戳单独存储。转换只改变格式；不做对齐、缩放或首帧归零。检查包括四元数归一化、时间严格递增、PCD 点数/字节数一致、XYZ 有限及 KITTI/TUM 对应。通过这些检查只证明文件结构有效，不证明地图精度合格。

## 7. evo 评估与范围说明

输入：同次运行 TUM 轨迹、官方 IMU 真值；输出：ATE 压缩包、曲线、范围 JSON 和标注轨迹图。

```bash
mkdir "$RUN/evaluation"
curl -fL --retry 3 \
  https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/resolve/main/ground_truth/exp18_corridor_lower_gallery_2_imu.txt \
  -o "$RUN/evaluation/groundtruth_imu.txt"
sha256sum "$RUN/evaluation/groundtruth_imu.txt"
MPLBACKEND=Agg "$EVAL_PY" "$REPO/tools/run_evo.py" tum \
  "$RUN/evaluation/groundtruth_imu.txt" "$RUN/trajectory_tum.txt" \
  --align --t_max_diff 0.05 --pose_relation trans_part \
  --save_results "$RUN/evaluation/ate_results.zip" \
  --save_plot "$RUN/evaluation/ate.png" --plot_mode xy
"$EVAL_PY" "$REPO/tools/evaluation_scope.py" \
  --groundtruth "$RUN/evaluation/groundtruth_imu.txt" --estimate "$RUN/trajectory_tum.txt" \
  --max-diff 0.05 --output "$RUN/evaluation/evaluation_scope.json" \
  --plot "$RUN/evaluation/ate_scope.png"
```

官方真值 SHA256（2026-10-10 核对）：`138def6a40884a87372a4f18938cce5180d6aa7ad4e705349abf47ac4ec9fa32`。若下载内容或序列变化，应先核对，不直接沿用评估数字。evo 将图保存为 `ate_raw.png` 和 `ate_map.png` 等带后缀文件。

`--align` 为 SE(3) Umeyama 对齐；不添加 `--correct_scale`。要重算仓库历史 0.167018 m，使用 `week1_yin_anwei/trajectory_tum.txt` 作为 estimate，结果写到新的目录。新回放可能因调度、接收和初始化产生不同轨迹，不能直接套用历史 RMSE。

## 8. 地图查看与交付

用 CloudCompare 打开 `$RUN/map.pcd`，检查整体结构、走廊/墙面及离群点。也可生成基于真实坐标的静态图：

```bash
"$EVAL_PY" "$REPO/tools/render_map.py" --pcd "$RUN/map.pcd" --output-dir "$RUN/figures"
```

保存该次运行的配置、地图、轨迹、日志、校验报告和评估结果。PCD 通过 Release/约定的大文件存储共享，记录下载地址和 SHA256；轨迹与文本材料可入 Git。第一周基线下载见 [MAP_FILE.md](MAP_FILE.md)。

## 常见问题

- `Publisher count: 1` 只说明发布端存在，不代表持续有消息；先查看采集脚本日志和返回状态。
- `No Effective Points!` 连续出现时，不以“能保存 PCD”作为成功。检查时间字段、外参、输入格式及运行负载。
- `timestamp` 是本数据绝对秒；必须减 header 后转毫秒。`T_imu_pandar` 将 LiDAR 点变到 IMU：`p_imu = R × p_lidar + T`。
- 不要只凭播放倍率猜原因：本机 BEST_EFFORT 半速实验也少了数百帧输入；改为 RELIABLE 后输入完整性明显改善。实验和适用限制见 [运行对照](validation/20261011_qos/)。
