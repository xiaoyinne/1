# 第五周运行与复现

依赖：WSL Ubuntu 22.04、ROS 2 Humble、Nav2、Gazebo Classic 11、TurtleBot3 仿真包。实测安装版本记录在 [正式实验协议](experiments/patrol_20261111_multiyaw/formal/protocol.json)。本次归档未重新运行仿真，下面的命令用于之后复现。

## 1. 准备最终版本

在 Ubuntu 终端、克隆后的仓库根目录执行。建议使用一个新的可写目录，避免混用早期 A-B-A 代码。

```bash
mkdir -p ~/nav2_week5_final
cp -a week5_yin_anwei/code/. ~/nav2_week5_final/
cd ~/nav2_week5_final
source /opt/ros/humble/setup.bash
```

核对 `patrol.py` 的清单应为 A、B、C、S，目标朝向依次为 90°、180°、0°、90°。出生位姿为 S=(0.05,-0.05,90°)。每个目标都是地图坐标中的位姿。

## 2. 图形演示

窗口 1：

```bash
bash ~/nav2_week5_final/start_week5.sh
```

它加载本目录地图、仿真场地、参数、目标标记及 RViz，本身不会发送巡检任务。图形启动使用 `ROS_DOMAIN_ID=0`，避免同时开启其他同域导航。脚本发现已有 gzserver、amcl 或 controller_server 时会拒绝重复启动。

窗口 2：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
timeout 10s ros2 lifecycle get /amcl
timeout 10s ros2 param get /planner_server GridBased.use_astar
timeout 10s ros2 param get /controller_server FollowPath.plugin
```

预期分别是 `active`、`True`、`dwb_core::DWBLocalPlanner`。在 RViz 使用 2D Pose Estimate 提供已知出生位姿 S，箭头朝 +Y。定位就绪、激光与地图对齐后，运行：

```bash
mkdir -p ~/nav2_week5_final/logs
set -o pipefail
/usr/bin/python3 -u ~/nav2_week5_final/patrol.py 2>&1 | tee ~/nav2_week5_final/logs/patrol_local.log
```

`patrol.py` 负责顺序下发和导航结果处理，不执行独立的 Gazebo 实际位姿测量。它的通信等待也不等于正式程序的停稳检查。图形世界没有自动注入测量插件，不能直接假设 `/evaluation/get_entity_state` 可用。

## 3. 三轮正式测量

先退出图形演示，并确保端口 11361 无其他服务占用。在已加载 ROS 环境的 Ubuntu 终端执行：

```bash
source /opt/ros/humble/setup.bash
cd ~/nav2_week5_final
/usr/bin/python3 -s repeat_patrol.py --run --repeats 3
```

这条命令会实际启动仿真并移动模拟机器人。程序在 `ROS_DOMAIN_ID=41`、Gazebo 端口 11361 下无图形运行，每轮重新启动仿真并设置已知初值。结果写入 `validation/patrol_时间戳/`，终端以 `EVIDENCE:` 打印目录。

每点终态后至少等待 2 个仿真秒，再检查采样平移速度<0.01 米/秒、角速度<0.03 弧度/秒，读取实际位姿并计算误差。Action 成功且确认停稳才继续；失败、超时或未确认停稳则停止后续点。误差超出外部标准会记录，当前程序不会自动重试，也不因此阻断下一点。

不要直接启动归档中的 `formal/validation.launch.py`。它保留历史机器的绝对路径，应运行 `repeat_patrol.py` 为当前目录重新生成启动文件。程序只清理自己启动的进程组，清理结果写入各轮 `cleanup.json`。

## 4. 汇总新结果

将目录名替换为实际运行输出：

```bash
/usr/bin/python3 -s ~/nav2_week5_final/summarize_patrol.py ~/nav2_week5_final/validation/patrol_实际时间戳
```

这会生成 `measurements.csv` 与 `summary.json`。每轮四段，三轮十二条。位置误差使用实际停车点到原始目标的欧氏距离，朝向使用最短角差。外部标准是位置≤0.25 米、朝向≤0.25 弧度，联合达标还要求停稳。

## 5. 重算本次归档

在仓库根目录执行，先复制到临时目录，保留原始证据不变：

```bash
review_dir=$(mktemp -d /tmp/week5-review-XXXXXX)
cp -a week5_yin_anwei/experiments/patrol_20261111_multiyaw/formal/. "$review_dir/"
/usr/bin/python3 -s week5_yin_anwei/code/summarize_patrol.py "$review_dir"
```

应得到路线完成 3/3、Action 成功 12/12、位置通过 11/12、朝向通过 12/12、联合通过 11/12。新运行存在随机性，不要求得到完全相同的数字。不要用当前四段汇总脚本处理旧 A-B-A 的三段结果，旧版本代码在 `history/code_20261104/`。

## 6. 完整性与限制

[ARCHIVE_MANIFEST.json](ARCHIVE_MANIFEST.json) 记录当前第五周文件的字节数与 SHA256，各次 `protocol.json` 另记录正式输入哈希。历史证据中的本机路径用于溯源。所有正式轮次、超标点和独立预运行均保留，预运行不计入正式统计。第五周 PPT 不上传。
