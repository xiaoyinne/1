"""Run one A-B-A route, measuring every endpoint in the instrumented world."""
import argparse
import json
import time
from pathlib import Path
import rclpy
from rcl_interfaces.srv import GetParameters
from measurement_core import Probe
from patrol import WAYPOINTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.run:
        parser.error('--run is required: this program moves the simulated robot')
    folder = args.output
    folder.mkdir(parents=True, exist_ok=True)
    data = {'segments': [], 'completed': False}
    rclpy.init()
    node = Probe(folder)
    try:
        data['ready'] = node.ready()
        data['runtime_parameters'] = {}
        for owner, names in [('planner_server', ['GridBased.use_astar', 'GridBased.tolerance']),
                             ('controller_server', ['FollowPath.plugin', 'general_goal_checker.xy_goal_tolerance',
                                                    'general_goal_checker.yaw_goal_tolerance', 'general_goal_checker.stateful'])]:
            service = node.create_client(GetParameters, '/' + owner + '/get_parameters')
            if not service.wait_for_service(timeout_sec=10):
                raise RuntimeError('Parameter service unavailable: ' + owner)
            request = GetParameters.Request()
            request.names = names
            response = node.await_future(service.call_async(request), 10)
            for name, value in zip(names, response.values):
                result = {1: value.bool_value, 2: value.integer_value, 3: value.double_value,
                          4: value.string_value}.get(value.type)
                data['runtime_parameters'][owner + '.' + name] = result
        if data['runtime_parameters']['planner_server.GridBased.use_astar'] is not True:
            raise RuntimeError('A* is not enabled')
        if data['runtime_parameters']['controller_server.FollowPath.plugin'] != 'dwb_core::DWBLocalPlanner':
            raise RuntimeError('Unexpected controller')
        started = time.monotonic()
        for index, (name, x, y) in enumerate(WAYPOINTS, start=1):
            print(f'Segment {index}/3: {name}', flush=True)
            segment = node.execute([x, y, 1.5707963267948966], 120)
            segment.update(index=index, name=name)
            segment['last_plan_endpoint'] = node.plans[-1]['xy'][-1] if node.plans and node.plans[-1]['xy'] else None
            data['segments'].append(segment)
            (folder / 'result.json').write_text(json.dumps(data, indent=2))
            print(f"{segment['status']}; distance={segment.get('truth_endpoint_distance_m')}; stopped={segment.get('stopped_verified')}", flush=True)
            if segment['status'] != 'SUCCEEDED' or not segment.get('stopped_verified'):
                break
        data['wall_route_including_dwell_s'] = time.monotonic() - started
        data['completed'] = len(data['segments']) == 3 and all(s['status'] == 'SUCCEEDED' and s.get('stopped_verified') for s in data['segments'])
    except Exception as exc:
        data['error'] = repr(exc)
        print('ERROR:', repr(exc), flush=True)
    finally:
        (folder / 'result.json').write_text(json.dumps(data, indent=2))
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    raise SystemExit(0 if data['completed'] else 1)


if __name__ == '__main__':
    main()
