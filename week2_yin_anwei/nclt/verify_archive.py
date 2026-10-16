"""Read-only evidence verification. Requires Python 3 and NumPy; no raw scans."""
from pathlib import Path
import hashlib
import json
import numpy as np

ROOT = Path(__file__).resolve().parent
E = ROOT / 'evidence'

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def check(condition, message):
    if not condition:
        raise RuntimeError(message)

def close(a, b):
    check(np.allclose(a, b, rtol=1e-8, atol=1e-7), f'Mismatch: {a} != {b}')

manifest = read(ROOT / 'manifest.json')['files']
for entry in manifest:
    data = (ROOT / entry['path']).read_bytes()
    check(len(data) == entry['bytes'], entry['path'])
    check(hashlib.sha256(data).hexdigest() == entry['sha256'], entry['path'])
scripts = list((E / 'scripts').glob('*.py'))
for script in scripts:
    compile(script.read_text(encoding='utf-8-sig'), str(script), 'exec')

datasets = []
for date, count in [('2012-01-08', 1296), ('2012-02-05', 1306)]:
    with np.load(E / 'descriptors_v1' / date / 'descriptors.npz', allow_pickle=False) as f:
        stamps, sc, rk = (f[k].copy() for k in ['stamps_us', 'descriptors', 'ring_keys'])
    check(sc.shape == (count, 20, 60) and rk.shape == (count, 20), date)
    check(np.isfinite(sc).all() and np.isfinite(rk).all(), date)
    check(np.all(np.diff(stamps) > 0), date)
    close(sc.mean(axis=2), rk)
    with np.load(E / 'reference_audit' / f'{date}_scan_reference.npz', allow_pickle=False) as f:
        lookup = dict(zip(map(int, f['stamps_us']), f['poses_xyz_rpy']))
    poses = np.array([lookup[int(t)] for t in stamps])
    check(np.isfinite(poses).all(), date)
    datasets.append((stamps, sc, poses))
(ds, dc, dp), (qs, qc, qp) = datasets

items = read(E / 'retrieval_cross_date_v1/retrieval_only.json')
report = read(E / 'retrieval_cross_date_v1/report.json')
check(len(items) == len(qs), 'query count')
check(sorted(i['query_index'] for i in items) == list(range(len(qs))), 'query IDs')
counts = dict(queries_with_near_history=0, queries_without_near_history=0,
              queries_with_near_in_top10=0, top1_near_by_reference=0,
              accepted_candidates=0, accepted_near_by_reference=0,
              accepted_far_by_reference=0, accepted_when_no_near_history=0,
              rejected_when_no_near_history=0)
accepted = {}
for item in items:
    q, d = item['query_index'], item['best_db_index']
    check(int(qs[q]) == item['query_stamp_us'] and int(ds[d]) == item['best_db_stamp_us'], 'stamps')
    distance = np.linalg.norm(dp[:, :3] - qp[q, :3], axis=1)
    near, best = bool(np.any(distance <= 5)), bool(distance[d] <= 5)
    accept = item['sc_distance'] < report['sc_threshold']
    check(accept == item['accepted'], 'SC threshold')
    counts['queries_with_near_history'] += near
    counts['queries_without_near_history'] += not near
    counts['queries_with_near_in_top10'] += bool(np.any(distance[item['candidate_indices']] <= 5))
    counts['top1_near_by_reference'] += best
    counts['accepted_candidates'] += accept
    counts['accepted_near_by_reference'] += accept and best
    counts['accepted_far_by_reference'] += accept and not best
    counts['accepted_when_no_near_history'] += accept and not near
    counts['rejected_when_no_near_history'] += not accept and not near
    if accept:
        accepted[q] = item
for key, value in counts.items():
    check(value == report[key], key)

def world_flu(p):
    # Extrinsic xyz Euler convention: Rz(yaw) @ Ry(pitch) @ Rx(roll).
    r, pch, y = p[3:6]
    cr, sr, cp, sp, cy, sy = np.cos(r), np.sin(r), np.cos(pch), np.sin(pch), np.cos(y), np.sin(y)
    rx = np.array([[1, 0, 0], [0, cr, -sr], [0, sr, cr]])
    ry = np.array([[cp, 0, sp], [0, 1, 0], [-sp, 0, cp]])
    rz = np.array([[cy, -sy, 0], [sy, cy, 0], [0, 0, 1]])
    t = np.eye(4)
    t[:3, :3] = rz @ ry @ rx @ np.diag([1, -1, -1])
    t[:3, 3] = p[:3]
    return t

records = read(E / 'geometry_cross_date_v1/results.json')
gr = read(E / 'geometry_cross_date_v1/report.json')
check(sorted(r['query_index'] for r in records) == sorted(accepted), 'ICP candidate IDs')
flagged = []
for r in records:
    q, d = r['query_index'], r['db_index']
    check(d == accepted[q]['best_db_index'], 'ICP db ID')
    check(r['query_stamp_us'] == int(qs[q]) and r['db_stamp_us'] == int(ds[d]), 'ICP stamps')
    gate = (min(r['forward_overlap'], r['reverse_overlap']) >= .5
            and max(r['forward_inlier_rmse_m'], r['reverse_inlier_rmse_m']) <= .3
            and min(r['forward_correspondences'], r['reverse_correspondences']) > 0)
    check(gate == r['geometry_passed'], 'geometry gate')
    ref = np.linalg.inv(world_flu(dp[d])) @ world_flu(qp[q])
    est = np.array(r['T_db_query'])
    close(est[3], [0, 0, 0, 1])
    close(est[:3, :3].T @ est[:3, :3], np.eye(3))
    close(np.linalg.det(est[:3, :3]), 1)
    close(np.linalg.norm(est[:3, 3] - ref[:3, 3]), r['translation_reference_error_m'])
    relative = ref[:3, :3].T @ est[:3, :3]
    angle = np.degrees(np.arccos(np.clip((np.trace(relative) - 1) / 2, -1, 1)))
    close(angle, r['rotation_reference_error_deg'])
    distance = np.linalg.norm(dp[d, :3] - qp[q, :3])
    close(distance, r['reference_distance_m'])
    check(bool(distance <= 5) == r['near_by_reference'], 'reference label')
    a, b = np.roll(qc[q], accepted[q]['shift_sectors'], axis=1), dc[d]
    ca, cb = np.count_nonzero(a, axis=0), np.count_nonzero(b, axis=0)
    common = (ca > 0) & (cb > 0)
    single = common & (ca == 1) & (cb == 1) & (np.argmax(a, axis=0) == np.argmax(b, axis=0))
    if common.sum() > 0 and single.sum() == common.sum():
        flagged.append(r)

passed = [r for r in records if r['geometry_passed']]
near = [r for r in passed if r['near_by_reference']]
far = [r for r in passed if not r['near_by_reference']]
for key, value in dict(tested_candidates=len(records), geometry_passed=len(passed),
                      geometry_rejected=len(records)-len(passed),
                      geometry_passed_reference_near=len(near), geometry_passed_reference_far=len(far)).items():
    check(gr[key] == value, key)
for name, group in [('passed_all_error_stats', passed), ('passed_reference_near_error_stats', near),
                    ('passed_reference_far_error_stats', far)]:
    check(gr[name]['count'] == len(group), name)
    for field in ['translation_reference_error_m', 'rotation_reference_error_deg']:
        values = [r[field] for r in group]
        for metric, value in zip(['median', 'p95', 'max'], [np.median(values), np.percentile(values, 95), np.max(values)]):
            close(value, gr[name][field][metric])

def summary(group):
    n = sum(r['near_by_reference'] for r in group)
    return dict(total=len(group), reference_near=n, reference_far=len(group)-n)

ar = read(E / 'degeneracy_audit_v1/report.json')
flag_ids = {r['query_index'] for r in flagged}
for key, group in [('degenerate_candidates', flagged),
                   ('degenerate_candidates_that_passed_geometry', [r for r in flagged if r['geometry_passed']]),
                   ('original_geometry_passed', passed),
                   ('hypothetical_remaining_after_rejecting_degenerate', [r for r in passed if r['query_index'] not in flag_ids])]:
    check(summary(group) == ar[key], key)
print(json.dumps(dict(status='PASS', manifest_files=len(manifest), syntax_checked_scripts=len(scripts),
                     retrieval_counts=counts, geometry_passed=summary(passed),
                     relative_pose_errors_recomputed=len(records), degenerate=summary(flagged),
                     scope='Archive integrity and numerical checks only; ICP and retrieval were not rerun.'), indent=2))
