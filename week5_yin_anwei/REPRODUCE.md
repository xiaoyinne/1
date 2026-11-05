# 第五周复现

环境为 WSL Ubuntu 22.04、ROS2 Humble、Gazebo Classic 11、Nav2、TurtleBot3。原始安装版本见 [protocol.json](experiments/patrol_20261104/protocol.json)。需要已安装导航与仿真依赖；本周归档不含ROS安装包。

## 1. 准备独立运行目录

在Ubuntu终端进入克隆后的仓库根目录，把代码复制到一个新目录，避免覆盖原来的学习目录：

```bash
mkdir ~/nav2_week5_archive
cp -a week5_yin_anwei/code/. ~/nav2_week5_archive/
cd ~/nav2_week5_archive
source /opt/ros/humble/setup.bash
export LIBGL_ALWAYS_SOFTWARE=true
export GAZEBO_MODEL_PATH="${GAZEBO_MODEL_PATH:-}:/opt/ros/humble/share/turtlebot3_gazebo/models"
```

## 2. 图形演示

窗口1运行 `bash ~/nav2_week5_archive/start_week5.sh`。它加载本目录地图、世界、A*参数和带标记的RViz配置；自身不发送导航任务。检查没有其他同域的仿真/导航同时运行。

窗口2执行：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
timeout 10s ros2 lifecycle get /amcl
timeout 10s ros2 param get /planner_server GridBased.use_astar
timeout 10s ros2 param get /controller_server FollowPath.plugin
```

预期分别为 `active`、`True`、`dwb_core::DWBLocalPlanner`。在RViz用2D Pose Estimate设置已知出生位姿：地图坐标约(0.05,-0.05)，朝向+Y；等激光与地图对齐、定位就绪后运行：

```bash
set -o pipefail
/usr/bin/python3 -u ~/nav2_week5_archive/patrol.py 2>&1 | tee ~/nav2_week5_archive/logs/patrol_local.log
```

`patrol.py`只负责顺序导航与计时，不做正式外部位姿采样；需要测量时使用下一节。退出演示时先等待当前任务结束，再在启动终端Ctrl+C并等待进程退出。客户端退出本身不保证服务端目标被取消。

## 3. 三轮统一条件测量

在独立终端、已加载Humble环境且本机11355端口空闲时运行：

```bash
source /opt/ros/humble/setup.bash
cd ~/nav2_week5_archive
/usr/bin/python3 -s repeat_patrol.py --run --repeats 3
```

这会真正启动无图形窗口仿真并移动模拟机器人。脚本使用通信域35、Gazebo端口11355，每轮新建仿真，自动提供定位初值，最后清理自己启动的进程。结果目录显示在 `EVIDENCE:` 后，位于 `validation/patrol_时间戳/`。每点任务成功后，至少等2个仿真秒，确认平移速度<0.01米/秒、角速度<0.03弧度/秒，再读取停稳位姿。

不要直接启动归档证据里的 `validation.launch.py`：它是历史生成文件，保留当时的绝对路径。应运行 `repeat_patrol.py`，让它为本机新目录重新生成启动文件。

## 4. 汇总新结果或重算历史结果

新运行完成后，把下列路径替换为刚才 `EVIDENCE:` 显示的实际目录：

```bash
/usr/bin/python3 -s ~/nav2_week5_archive/summarize_patrol.py ~/nav2_week5_archive/validation/patrol_实际时间戳
```

重算历史结果时，先复制证据目录，避免修改原始归档。在仓库根目录执行：

```bash
cp -a week5_yin_anwei/experiments/patrol_20261104 /tmp/week5_recheck
/usr/bin/python3 week5_yin_anwei/code/summarize_patrol.py /tmp/week5_recheck
```

`measurements.csv`的九行对应三轮的A1、B、A2；位置误差使用实际停车点到原始目标的欧氏距离，朝向误差使用最短角差，联合判定还要求停稳。统计应得到9次Action成功、位置通过8次、朝向通过6次、联合通过5次。新实验可能变化，不要求逐字节复现相同结果。

## 5. 归档完整性

`ARCHIVE_MANIFEST.json`记录本次归档的SHA256。原始 `protocol.json` 还记录正式运行输入的SHA256，`experiments/patrol_20261104/manifest.json` 是原始实验导出清单。原始实验清单中三项 `__pycache__` 编译缓存按归档规则未上传，已在 `VALIDATION.json` 单独列出；其余28项逐一校验一致。历史证据中的本机路径用于溯源，不代表新的克隆目录。
