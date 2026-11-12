#!/usr/bin/env bash
set -e -o pipefail
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
export LIBGL_ALWAYS_SOFTWARE=true
export GAZEBO_MODEL_PATH="${GAZEBO_MODEL_PATH:-}:/opt/ros/humble/share/turtlebot3_gazebo/models"
WEEK5_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# 防止同时启动两套仿真和导航。
for process_name in gzserver amcl controller_server; do
    if pgrep -x "$process_name" >/dev/null; then
        printf '检测到已有 %s，请先在原启动终端按 Ctrl+C，等待退出后再启动。\n' "$process_name" >&2
        exit 1
    fi
done

mkdir -p "$WEEK5_ROOT/logs"
printf '第五周参数文件：%s\n' "$WEEK5_ROOT/nav2_week5_params.yaml"
ros2 launch "$WEEK5_ROOT/start_week5.launch.py" 2>&1 | tee "$WEEK5_ROOT/logs/startup_$(TZ=Asia/Shanghai date +%Y%m%d_%H%M%S).log"
