"""Play once, capture /Odometry and save the map, logs and per-run provenance.

Run with /usr/bin/python3 -s after sourcing ROS Humble and the built workspace.
This script only stops the two process groups it starts.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import threading
import time
import yaml


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--bag', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--rate', type=float, default=0.5)
    parser.add_argument('--timeout', type=float, default=600, help='Wall seconds; reaching this limit is a failed, partial run')
    parser.add_argument('--domain-id', type=int, default=87)
    args = parser.parse_args()
    if args.rate <= 0 or args.timeout <= 0 or not 0 <= args.domain_id <= 232:
        parser.error('Invalid rate, timeout or ROS domain')
    workspace, bag_path, config, run_dir = (p.resolve() for p in (args.workspace, args.bag, args.config, args.run_dir))
    executable = workspace / 'install/fast_lio/lib/fast_lio/fastlio_mapping'
    for required in (executable, bag_path / 'metadata.yaml', config):
        if not required.is_file():
            parser.error(f'Missing input: {required}')
    if run_dir.exists():
        parser.error('Run directory exists; use a new name to preserve prior results')
    config_data = yaml.safe_load(config.read_text())
    parameters = config_data['/**']['ros__parameters']
    if not parameters['pcd_save']['pcd_save_en'] or parameters['pcd_save']['interval'] != -1:
        parser.error('Expected pcd_save enabled and interval=-1 for one cumulative map')
    parameters['map_file_path'] = str(run_dir / 'map.pcd')
    parameters['use_sim_time'] = True
    metadata = yaml.safe_load((bag_path / 'metadata.yaml').read_text())['rosbag2_bagfile_information']
    run_dir.mkdir(parents=True)
    (run_dir / 'input_config.yaml').write_bytes(config.read_bytes())
    (run_dir / 'config.yaml').write_text(yaml.safe_dump(config_data, sort_keys=False))
    source = workspace / 'src/FAST_LIO'
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    source_diff = subprocess.check_output(['git', '-C', str(source), 'diff', 'HEAD'], text=True)
    (run_dir / 'source.patch').write_text(source_diff)
    manifest = {'status': 'running', 'started_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                'playback_rate': args.rate, 'ros_domain_id': args.domain_id, 'ros_distro': os.getenv('ROS_DISTRO'),
                'platform': platform.platform(), 'workspace': str(workspace), 'source_commit': revision,
                'source_patch_sha256': digest(run_dir / 'source.patch'),
                'executable_sha256': digest(executable), 'config_sha256': digest(run_dir / 'config.yaml'),
                'bag_metadata_sha256': digest(bag_path / 'metadata.yaml'),
                'bag_duration_s': metadata['duration']['nanoseconds'] / 1e9,
                'bag_topic_counts': {x['topic_metadata']['name']: x['message_count'] for x in metadata['topics_with_message_count']},
                'trajectory': {'topic': '/Odometry', 'pose': 'IMU/body in camera_init', 'quaternion': 'xyzw',
                               'timestamp': 'Odometry.header.stamp (scan end), seconds', 'position_unit': 'm'},
                'limitation': 'Bag topic counts are source counts, not FAST-LIO receive/process counters.'}

    def save_manifest():
        (run_dir / 'run_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

    save_manifest()
    os.environ['ROS_DOMAIN_ID'] = str(args.domain_id)
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import ExternalShutdownException
    from nav_msgs.msg import Odometry
    rclpy.init()
    observer = Node('week1_trajectory_recorder')
    trajectory = []
    frames = set()
    last_received = [time.monotonic()]
    spin_errors = []

    def observe(msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        trajectory.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                           p.x, p.y, p.z, q.x, q.y, q.z, q.w))
        frames.add((msg.header.frame_id, msg.child_frame_id))
        last_received[0] = time.monotonic()

    observer.create_subscription(Odometry, '/Odometry', observe, 1000)

    def spin():
        try:
            rclpy.spin(observer)
        except ExternalShutdownException:
            pass
        except Exception as exc:
            spin_errors.append(str(exc))

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    children = []
    forced_stops = []

    def stop(proc):
        if proc.poll() is not None:
            return
        os.killpg(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=45)
        except subprocess.TimeoutExpired:
            forced_stops.append(proc.pid)
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)

    failure = None
    try:
        if observer.get_publishers_info_by_topic('/Odometry'):
            raise RuntimeError('Another odometry publisher is already in this ROS domain; choose a free domain')
        with (run_dir / 'mapping.log').open('w') as mapper_log, (run_dir / 'bag.log').open('w') as bag_log:
            mapping_command = [str(executable), '--ros-args', '--params-file', str(run_dir / 'config.yaml')]
            bag_command = ['ros2', 'bag', 'play', str(bag_path), '--clock', '--rate', str(args.rate),
                           '--topics', '/hesai/pandar', '/alphasense/imu']
            manifest['commands'] = {'mapping': mapping_command, 'bag': bag_command}
            save_manifest()
            mapper = subprocess.Popen(mapping_command, cwd=run_dir, stdout=mapper_log, stderr=subprocess.STDOUT, start_new_session=True)
            children.append(mapper)
            for _ in range(200):
                if mapper.poll() is not None:
                    raise RuntimeError('FAST-LIO exited before playback; see mapping.log')
                if ('Node init finished' in (run_dir / 'mapping.log').read_text(errors='replace')
                        and observer.get_subscriptions_info_by_topic('/hesai/pandar')
                        and observer.get_subscriptions_info_by_topic('/alphasense/imu')
                        and observer.get_publishers_info_by_topic('/Odometry')):
                    break
                time.sleep(.1)
            else:
                raise RuntimeError('FAST-LIO initialization/discovery timed out')
            player = subprocess.Popen(bag_command, stdout=bag_log, stderr=subprocess.STDOUT, start_new_session=True)
            children.append(player)
            print(f'Playback at {args.rate}x; logs and artifacts: {run_dir}', flush=True)
            deadline = time.monotonic() + args.timeout
            while player.poll() is None:
                if mapper.poll() is not None or spin_errors:
                    raise RuntimeError('Mapper or odometry recorder stopped during playback')
                if time.monotonic() >= deadline:
                    raise RuntimeError('Playback timed out; artifacts are partial')
                time.sleep(.25)
            manifest['bag_exit_code'] = player.returncode
            if player.returncode != 0:
                raise RuntimeError('Bag playback failed; see bag.log')
            drain_start = time.monotonic()
            time.sleep(2)
            while time.monotonic() - last_received[0] < 2:
                if time.monotonic() - drain_start > 30:
                    raise RuntimeError('Odometry did not settle after playback')
                time.sleep(.25)
            stop(mapper)
            manifest['mapping_exit_code'] = mapper.returncode
            if mapper.returncode != 0 or forced_stops:
                raise RuntimeError('Mapper did not exit cleanly; saved map requires inspection')
    except (Exception, KeyboardInterrupt) as exc:
        failure = str(exc) or type(exc).__name__
    finally:
        for proc in reversed(children):
            stop(proc)
        rclpy.shutdown()
        thread.join(timeout=5)
        observer.destroy_node()
        with (run_dir / 'trajectory_tum.txt').open('w') as output:
            for row in trajectory:
                output.write(' '.join(f'{v:.9f}' for v in row) + '\n')
        mapping_log = (run_dir / 'mapping.log')
        text = mapping_log.read_text(errors='replace') if mapping_log.exists() else ''
        warnings = text.count('No Effective Points')
        manifest.update({'trajectory_poses': len(trajectory), 'observed_frames': sorted(frames),
                         'no_effective_points_count': warnings, 'forced_stop_pids': forced_stops,
                         'recorder_errors': spin_errors,
                         'finished_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        if not failure and (len(trajectory) < 2 or not (run_dir / 'map.pcd').is_file() or warnings or spin_errors):
            failure = 'Missing map/trajectory, recorder error or No Effective Points; inspect logs'
        if not failure and any(b[0] <= a[0] for a, b in zip(trajectory, trajectory[1:])):
            failure = 'Non-increasing trajectory timestamps'
        manifest['status'] = 'failed' if failure else 'completed_needs_accuracy_evaluation'
        manifest['failure'] = failure
        if (run_dir / 'map.pcd').exists():
            manifest['map_sha256'] = digest(run_dir / 'map.pcd')
        save_manifest()
    if failure:
        raise SystemExit(f'FAILED: {failure}; artifacts retained at {run_dir}')
    print(f'PASS: completed playback, saved map and {len(trajectory)} poses. Run check_results.py and evo next.')


if __name__ == '__main__':
    main()
