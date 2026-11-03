"""Initialize a fresh exercise spawn, wait with the same nodes, then test one goal.

Requires --run; sends an initial pose and moves the simulated robot after waiting.
Refuses to initialize a robot which has already left the expected spawn.
"""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import subprocess
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent


def call(args, timeout=10):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(p.stdout+p.stderr)
    return p.stdout


def processes():
    found = {}
    for d in Path('/proc').glob('[0-9]*'):
        try:
            command = (d/'cmdline').read_bytes().replace(b'\0', b' ').decode()
            if any(name in command for name in (
                '/nav2_controller/controller_server ', '/nav2_amcl/amcl ',
                '/nav2_bt_navigator/bt_navigator ', 'gzserver -s ')):
                state = (d/'stat').read_text().rsplit(')', 1)[1].split()
                found[d.name] = {'command': command, 'start_ticks': state[19]}
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            pass
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--wait-seconds', type=float, default=300)
    args = parser.parse_args()
    if not args.run or not math.isfinite(args.wait_seconds) or args.wait_seconds < 0:
        parser.error('--run and a finite nonnegative wait are required')
    deadline = time.monotonic()+70
    while True:
        try:
            if 'active [3]' in call(['ros2', 'lifecycle', 'get', '/amcl'], timeout=5):
                break
        except (RuntimeError, subprocess.TimeoutExpired):
            pass
        if time.monotonic() > deadline:
            raise RuntimeError('AMCL did not become active')
        time.sleep(1)
    pose = list(map(float, call(['gz', 'model', '-m', 'turtlebot3_waffle', '-p']).split()))
    if len(pose) != 6 or math.hypot(pose[0]-.05, pose[1]+.05) > .08:
        raise RuntimeError('Robot is not at the fresh exercise spawn; refusing to initialize')
    stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S')
    folder = ROOT/'validation'/f'delayed_v0_{stamp}'
    folder.mkdir(parents=True, exist_ok=False)
    initial = {'header': {'frame_id': 'map'}, 'pose': {'pose': {
        'position': {'x': .05, 'y': -.05, 'z': 0.},
        'orientation': {'x': 0., 'y': 0., 'z': .7071068, 'w': .7071068}},
        'covariance': [.25 if i in (0, 7) else .0685 if i == 35 else 0. for i in range(36)]}}
    output = call(['ros2', 'topic', 'pub', '--times', '3', '--rate', '2',
                   '--keep-alive', '2', '/initialpose',
                   'geometry_msgs/msg/PoseWithCovarianceStamped', json.dumps(initial)], timeout=20)
    (folder/'initialization.txt').write_text(output)
    probe = subprocess.run(['timeout', '10s', 'ros2', 'run', 'tf2_ros', 'tf2_echo',
                            'map', 'base_footprint', '--ros-args', '-p', 'use_sim_time:=true'],
                           capture_output=True, text=True, timeout=15)
    probe_text = probe.stdout+probe.stderr
    (folder/'initial_tf_check.txt').write_text(probe_text)
    if 'Translation:' not in probe_text:
        raise RuntimeError('Initialization was published but map-to-robot TF is not ready; no idle test started')
    readiness = {}
    for node in ('amcl', 'bt_navigator', 'planner_server', 'controller_server'):
        readiness[node] = call(['ros2', 'lifecycle', 'get', '/'+node], timeout=12)
        if 'active [3]' not in readiness[node]:
            raise RuntimeError(f'{node} is not active; no idle test started')
    context = {'spawn_pose_world_xyz_rpy': pose, 'planned_idle_wall_s': args.wait_seconds,
               'start_unix': time.time(), 'processes_before': processes(),
               'readiness': readiness, 'map_to_robot_tf_verified_before_wait': True,
               'versions': call(['dpkg-query', '-W', 'ros-humble-tf2', 'ros-humble-tf2-ros',
                                 'ros-humble-tf2-ros-py', 'ros-humble-tf2-geometry-msgs'])}
    destination = folder/'wait_context.json'
    destination.write_text(json.dumps(context, indent=2))
    print('Delay evidence directory:', folder, flush=True)
    started = time.monotonic()
    next_heartbeat = 60
    while time.monotonic()-started < args.wait_seconds:
        elapsed = time.monotonic()-started
        time.sleep(max(0., min(10, args.wait_seconds-elapsed)))
        elapsed = time.monotonic()-started
        if elapsed >= next_heartbeat:
            print(f'Idle elapsed: {elapsed:.1f}/{args.wait_seconds:.1f} wall seconds', flush=True)
            next_heartbeat += 60
    context['actual_idle_wall_s'] = time.monotonic()-started
    context['processes_after_idle'] = processes()
    context['same_tracked_processes'] = context['processes_before'] == context['processes_after_idle']
    destination.write_text(json.dumps(context, indent=2))
    if not context['same_tracked_processes']:
        raise RuntimeError('Tracked simulation/navigation processes changed during the wait')
    print('Wait finished; testing original short goal without restarting nodes.', flush=True)
    log = folder/'checker_stdout.txt'
    with log.open('w') as stream:
        p = subprocess.run(['python3', str(ROOT/'check_current_scene.py'), '--run',
                            '--timeout', '90', '--cases', 'short_after_restart'],
                           stdout=stream, stderr=subprocess.STDOUT, text=True, timeout=180)
    text = log.read_text(errors='replace')
    print(text, flush=True)
    match = re.search(r'Evidence directory: (.+)', text)
    context['checker_returncode'] = p.returncode
    if match:
        evidence = Path(match.group(1).strip())
        context['checker_evidence'] = str(evidence)
        results = evidence/'results.json'
        if results.exists():
            context['action_results'] = json.loads(results.read_text())
    destination.write_text(json.dumps(context, indent=2))
    if p.returncode:
        raise RuntimeError('Check process failed; see checker_stdout.txt')


if __name__ == '__main__':
    main()
