"""Independent fresh-start patrol trials; headless simulation, all evidence retained."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent


def live_group(pgid):
    members = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            text = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(text[2]) == pgid and text[0] != 'Z':
                members.append(int(entry.name))
        except (OSError, ValueError):
            pass
    return members


def stop_owned(process):
    signals = []
    for sig, seconds in [(signal.SIGINT, 15), (signal.SIGTERM, 5), (signal.SIGKILL, 3)]:
        if not live_group(process.pid):
            break
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        signals.append(signal.Signals(sig).name)
        deadline = time.monotonic() + seconds
        while live_group(process.pid) and time.monotonic() < deadline:
            time.sleep(.2)
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    return {'signals': signals, 'remaining_pids': live_group(process.pid)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--repeats', type=int, default=3)
    args = parser.parse_args()
    if not args.run or not 1 <= args.repeats <= 10:
        parser.error('--run and 1..10 repeats required')
    # Separate ROS domain and Gazebo master; do not disturb user sessions.
    with socket.socket() as port:
        port.bind(('127.0.0.1', 11361))
    folder = ROOT / 'validation' / ('patrol_' + datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S'))
    folder.mkdir(parents=True)
    env = os.environ.copy()
    env.update(ROS_DOMAIN_ID='41', GAZEBO_MASTER_URI='http://127.0.0.1:11361', LIBGL_ALWAYS_SOFTWARE='true')
    env['GAZEBO_MODEL_PATH'] = env.get('GAZEBO_MODEL_PATH', '') + ':/opt/ros/humble/share/turtlebot3_gazebo/models'
    files = ['patrol.py', 'patrol_measured.py', 'measurement_core.py', 'repeat_patrol.py', 'nav2_week5_params.yaml',
             'scene_learning/map.yaml', 'scene_learning/map.pgm', 'scene_learning/hilti_cells.world']
    snapshot = folder / 'inputs'
    hashes = {}
    for relative in files:
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
        hashes[relative] = hashlib.sha256(target.read_bytes()).hexdigest()
    tree = ET.parse(snapshot / 'scene_learning/hilti_cells.world')
    plugin = ET.SubElement(tree.getroot().find('world'), 'plugin', {'name': 'week5_measurement', 'filename': 'libgazebo_ros_state.so'})
    ros = ET.SubElement(plugin, 'ros')
    ET.SubElement(ros, 'namespace').text = '/evaluation'
    ET.SubElement(plugin, 'update_rate').text = '20.0'
    world = folder / 'measurement.world'
    tree.write(world, encoding='utf-8', xml_declaration=True)
    versions = subprocess.run(['dpkg-query', '-W', 'ros-humble-nav2-bringup', 'ros-humble-nav2-amcl',
                               'ros-humble-rclpy', 'gazebo'], capture_output=True, text=True)
    protocol = {'repeats': args.repeats, 'route': [['A', .05, .65, 90.0], ['B', .85, 3.25, 180.0], ['C', -.80, -.10, 0.0], ['S', .05, -.05, 90.0]],
                'route_yaw_unit': 'degrees', 'spawn_xy_yaw': [.05, -.05, 1.5707963267948966],
                'initial_covariance_xy': .25, 'initial_covariance_yaw': .0685,
                'headless': True, 'ros_domain_id': 41, 'gazebo_master': env['GAZEBO_MASTER_URI'],
                'fresh_simulator_per_round': True, 'warmup_sim_s': 3,
                'pre_send_wall_s': 2, 'post_goal_minimum_sim_s': 2,
                'stopped_linear_m_s': .01, 'stopped_angular_rad_s': .03,
                'action_timeout_wall_s': 120, 'input_sha256': hashes,
                'versions': versions.stdout, 'random_seed_controlled': False,
                'route_extension': 'S-A-B-C-S; C=(-0.80,-0.10), fixed goal yaw A=90deg B=180deg C=0deg S=90deg; unchanged map and target coordinates; tuned AMCL, goal tolerances and NavFn fallback, see parameters.diff.',
                'note': 'Headless validation; separate preflight and formal rounds. No controlled random seed or collision-contact measurement.'}
    (folder / 'protocol.json').write_text(json.dumps(protocol, indent=2))
    mapfile = snapshot / 'scene_learning/map.yaml'
    params = snapshot / 'nav2_week5_params.yaml'
    launch = folder / 'validation.launch.py'
    launch.write_text('''from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
def generate_launch_description():
    source = Path(get_package_share_directory('nav2_bringup')) / 'launch/tb3_simulation_launch.py'
    return LaunchDescription([IncludeLaunchDescription(PythonLaunchDescriptionSource(str(source)), launch_arguments={
        'headless':'True', 'use_rviz':'False', 'use_sim_time':'True', 'use_composition':'False',
        'x_pose':'0.05', 'y_pose':'-0.05', 'yaw':'1.5707963267948966',
        'world':''' + repr(str(world)) + ", 'map':" + repr(str(mapfile)) + ", 'params_file':" + repr(str(params)) + '''}.items())])
''')
    print('EVIDENCE:', folder, flush=True)
    for repeat in range(1, args.repeats + 1):
        trial = folder / f'round_{repeat:02d}'
        trial.mkdir()
        print(f'ROUND {repeat}/{args.repeats}: fresh simulator', flush=True)
        with (trial / 'launch.log').open('w') as stream:
            process = subprocess.Popen(['ros2', 'launch', str(launch)], cwd=ROOT, env=env,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                with (trial / 'client.log').open('w') as client_log:
                    measured = subprocess.run(['/usr/bin/python3', '-s', str(snapshot / 'patrol_measured.py'), '--run', '--output', str(trial)],
                                              cwd=ROOT, env=env, stdout=client_log, stderr=subprocess.STDOUT, timeout=600)
                result_path = trial / 'result.json'
                result = json.loads(result_path.read_text()) if result_path.exists() else {}
                print('ROUND RESULT:', repeat, measured.returncode, result.get('completed'), result.get('error'), flush=True)
            except Exception as exc:
                (trial / 'runner_error.json').write_text(json.dumps({'error': repr(exc)}))
                print('RUNNER ERROR:', repr(exc), flush=True)
            finally:
                cleanup = stop_owned(process)
                (trial / 'cleanup.json').write_text(json.dumps(cleanup, indent=2))
                if cleanup['remaining_pids']:
                    raise RuntimeError('Owned processes remain; stop further trials')
    print('COMPLETE:', folder, flush=True)


if __name__ == '__main__':
    main()
