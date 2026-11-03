# 第四周复现入口

## 环境

记录环境为WSL Ubuntu 22.04、ROS2 Humble、Gazebo Classic 11、TurtleBot3与nav2_bringup。最终记录nav2_bringup 1.1.20，tf2/tf2_ros 0.25.24。需要对应ROS包和系统Python的numpy、matplotlib、Pillow、PyYAML；版本记录保存在每次实验目录。不是Windows原生PowerShell程序。

先克隆仓库，在Ubuntu/WSL进入 `1/week4_yin_anwei/week4_learning`。如果已经克隆，直接进入对应目录。

## 查看与恢复练习场地

窗口1，在week4_learning目录运行：

```bash
bash ./restore_hilti.sh
```

这会启动仿真与低帧率RViz，不自动发送目标。此入口是原始默认配置练习场，不等于后面的调整后绕障配置。

窗口2，在同一个week4_learning目录运行：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
python3 wait_then_check.py --run --wait-seconds 0
```

最后一条提供已知出生初值并实际发送短程目标。只对仍在出生位置的新启动机器人使用，不能拿来对走远的小车反复重设初值。查看完成后，在窗口1按Ctrl+C等待退出；关闭图形窗口不代表所有后台节点都退出。

## 重做固定任务实验

先正常结束已有Gazebo/Nav2，再运行。脚本会拒绝干扰已经存在的gzserver、controller_server、amcl进程，并为每轮启动自己的仿真。

窗口2，在week4_learning目录执行：

```bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
python3 repeat_navigation.py --run --repeats 3 --timeout 120 \
  --scenario baseline --label baseline --cases short cross detour
```

这是默认起点的基线任务，默认绕障失败记录仍保留。下面的已知起点任务是另一组条件，不合并统计。

重做当前调整后绕障：

```bash
python3 repeat_navigation.py --run --repeats 3 --timeout 120 \
  --scenario historical_start --label confirmation \
  --params-file nav2_amcl_candidate.yaml \
  --initial-xy-std 0.05 --initial-yaw-std 0.08726646259971647 \
  --staged-startup
```

新结果保存在validation/repeated_*新时间目录中。比较任务状态、停稳位置距离和朝向，不只看SUCCEEDED。历史目录中的results.json、protocol.json、参数及脚本快照是原始证据，不应手动修改成新结果。不同机器和依赖不保证完全复现相同数值。

## 从PCD重新生成地图与世界

只运行现成场地不需要PCD。重新生成时，按[原文件下载与SHA256](../MAP_FILE.md)获取PCD，先关闭仿真，在week4_learning目录运行：

```bash
python3 -s project_slice.py --pcd /实际位置/fastlio_hilti_fixed_20261008.pcd \
  --z -1.5 -0.8 --min-points 5
python3 -s export_nav2_map.py
python3 -s build_world.py --height 1.0
```

上述命令会改写生成的投影、地图和世界文件，请在新的克隆目录复现，避免覆盖原归档。源PCD SHA256为5513e08a55e7c9cc7187a5abd468157df86466151a0c1f27ace781384f49d52f。

本次发布仅执行语法、地图/世界一致性、实验汇总与归档哈希检查，没有为上传重新运行ROS仿真实验。
