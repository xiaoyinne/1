#!/usr/bin/env bash
source /opt/ros/humble/setup.bash
export ROS_DOMAIN_ID=0
export LIBGL_ALWAYS_SOFTWARE=true
export GAZEBO_MODEL_PATH="${GAZEBO_MODEL_PATH}:/opt/ros/humble/share/turtlebot3_gazebo/models"
WEEK4_RESTORE_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$WEEK4_RESTORE_ROOT/validation"
ros2 launch "$WEEK4_RESTORE_ROOT/restore_hilti.launch.py" 2>&1 | tee "$WEEK4_RESTORE_ROOT/validation/recovery_$(date +%Y%m%d_%H%M%S).log"
exec bash -i
