"""Restore the existing teaching scene with simulated time from startup.

No navigation goal is sent. Supply the known initial pose after AMCL is active.
"""
from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.actions import Node


def generate_launch_description():
    root = Path(__file__).resolve().parent
    scene = root / 'scene_learning'
    simulation = Path(get_package_share_directory('nav2_bringup')) / 'launch/tb3_simulation_launch.py'
    return LaunchDescription([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(str(simulation)),
            launch_arguments={
                'headless': 'False',
                'use_sim_time': 'True',
                'use_composition': 'False',
                # 明确加载第五周的 A* 参数文件。
                'params_file': str(root / 'nav2_week5_params.yaml'),
                'use_rviz': 'False',
                'world': str(scene / 'hilti_cells.world'),
                'map': str(scene / 'map.yaml'),
                'x_pose': '0.05',
                'y_pose': '-0.05',
                'yaw': '1.57079632679',
            }.items(),
        ),
        Node(
            executable='/usr/bin/python3',
            arguments=[str(root / 'show_patrol_points.py')],
            name='patrol_waypoint_markers', output='screen',
            parameters=[{'use_sim_time': True}],
        ),
        Node(
            package='rviz2', executable='rviz2', name='rviz', output='screen',
            arguments=['-d', str(root / 'rviz_demo.rviz')],
            parameters=[{'use_sim_time': True}],
        ),
    ])
