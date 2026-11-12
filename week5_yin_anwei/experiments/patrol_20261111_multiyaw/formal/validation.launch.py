from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
def generate_launch_description():
    source = Path(get_package_share_directory('nav2_bringup')) / 'launch/tb3_simulation_launch.py'
    return LaunchDescription([IncludeLaunchDescription(PythonLaunchDescriptionSource(str(source)), launch_arguments={
        'headless':'True', 'use_rviz':'False', 'use_sim_time':'True', 'use_composition':'False',
        'x_pose':'0.05', 'y_pose':'-0.05', 'yaw':'1.5707963267948966',
        'world':'/home/yaw/nav2_week5_sabcs_multiyaw_20261111/validation/patrol_20261111_145713/measurement.world', 'map':'/home/yaw/nav2_week5_sabcs_multiyaw_20261111/validation/patrol_20261111_145713/inputs/scene_learning/map.yaml', 'params_file':'/home/yaw/nav2_week5_sabcs_multiyaw_20261111/validation/patrol_20261111_145713/inputs/nav2_week5_params.yaml'}.items())])
