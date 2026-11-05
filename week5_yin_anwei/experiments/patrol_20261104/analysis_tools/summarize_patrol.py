import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import argparse

parser = argparse.ArgumentParser(description='Export measured patrol JSON results as CSV and summary')
parser.add_argument('folder', type=Path)
args = parser.parse_args()
folder = args.folder
repeat_count = json.loads((folder / 'protocol.json').read_text())['repeats']
rows, rounds = [], []
for i in range(1, repeat_count + 1):
    trial = folder / f'round_{i:02d}'
    file = trial / 'result.json'
    result = json.loads(file.read_text()) if file.exists() else {}
    rounds.append({'round': i, 'completed': result.get('completed', False),
                   'wall_route_s': result.get('wall_route_including_dwell_s'), 'error': result.get('error'),
                   'ready': result.get('ready'), 'runtime_parameters': result.get('runtime_parameters')})
    segments = {s['index']: s for s in result.get('segments', [])}
    for index, name in enumerate(['A1', 'B', 'A2'], start=1):
        s = segments.get(index, {})
        xy = s.get('truth_endpoint_distance_m')
        angle = s.get('truth_endpoint_yaw_error_rad')
        plan = s.get('last_plan_endpoint')
        goal = s.get('goal')
        row = {'round': i, 'segment': name, 'status': s.get('status', 'NOT_RUN'),
               'wall_action_s': s.get('wall_action_s'), 'sim_action_s': s.get('sim_action_s'),
               'settle_sim_s': s.get('settle_sim_s'), 'stopped': s.get('stopped_verified'),
               'position_error_m': xy, 'yaw_error_deg': math.degrees(angle) if angle is not None else None,
               'position_le_025': xy <= .25 if xy is not None else None,
               'yaw_le_025rad': angle <= .25 if angle is not None else None,
               'joint_precision_pass': (xy <= .25 and angle <= .25 and bool(s.get('stopped_verified'))) if xy is not None and angle is not None else None,
               'recoveries': s.get('max_recoveries'),
               'estimated_position_error_m': s.get('estimated_endpoint_distance_m'),
               'estimate_truth_distance_m': s.get('estimate_to_truth_distance_m'),
               'plan_endpoint_target_distance_m': math.dist(plan, goal[:2]) if plan and goal else None}
        rows.append(row)

with (folder / 'measurements.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

summary = {'rounds': rounds, 'measurements': rows,
           'completed_rounds': sum(r['completed'] for r in rounds),
           'successful_actions': sum(r['status'] == 'SUCCEEDED' for r in rows),
           'planned_actions': 3 * repeat_count,
           'measured_actions': sum(r['position_error_m'] is not None for r in rows),
           'position_pass_count': sum(r['position_le_025'] is True for r in rows),
           'yaw_pass_count': sum(r['yaw_le_025rad'] is True for r in rows),
           'joint_precision_pass_count': sum(r['joint_precision_pass'] is True for r in rows)}
for segment in ['A1', 'B', 'A2']:
    subset = [r for r in rows if r['segment'] == segment and r['position_error_m'] is not None]
    summary[segment] = {'count': len(subset)}
    for key in ['position_error_m', 'yaw_error_deg', 'wall_action_s']:
        values = [r[key] for r in subset if r[key] is not None]
        if values:
            summary[segment][key] = {'mean': statistics.mean(values), 'min': min(values), 'max': max(values)}
(folder / 'summary.json').write_text(json.dumps(summary, indent=2))
print(json.dumps({k: v for k, v in summary.items() if k not in ['measurements', 'rounds']}, indent=2))
