"""Read-only checks of archived hashes, numerical results and source syntax."""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
from scipy.spatial.transform import Rotation

ROOT = Path(__file__).resolve().parent
ART = ROOT / 'artifacts'

def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))

def read_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest = read_json(ROOT / 'manifest.json')
    omitted = {
        'artifacts/scancontext/vendor/PyICP-SLAM-master/utils/ScanContextManager.py',
        'artifacts/scancontext/vendor/PyICP-SLAM-master/utils/ScanContextManager.py.original',
    }
    checked = 0
    for item in manifest['files']:
        if item['path'] in omitted:
            continue
        path = ROOT / item['path']
        assert path.stat().st_size == item['bytes'], path
        assert sha(path) == item['sha256'], path
        checked += 1
    python_files = list(ROOT.rglob('*.py'))
    for path in python_files:
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')

    evaluation = ART / 'runs/event_20261013_132410/evaluation_common_v1'
    report = read_json(evaluation / 'report.json')
    errors = np.loadtxt(evaluation / 'errors.csv', delimiter=',', skiprows=1)
    gt = np.loadtxt(evaluation / 'gt_matched.txt')
    assert len(errors) == len(gt) == report['evaluated_pairs'] == 763
    ate = {}
    for col, name in ((2, 'odometry'), (3, 'localization')):
        aligned = np.loadtxt(evaluation / (name + '_aligned.txt'))
        distances = np.linalg.norm(aligned[:, 1:4] - gt[:, 1:4], axis=1)
        assert np.allclose(distances, errors[:, col], atol=1e-8, rtol=0)
        rmse = float(np.sqrt(np.mean(distances ** 2)))
        assert abs(rmse - report[name]['ATE_m']['rmse']) < 1e-8
        ate[name] = rmse

    runs = ART / 'scancontext/runs'
    retrieval = runs / 'kitti0020_retrieval_v1'
    ret = read_json(retrieval / 'report.json')
    queries = read_csv(retrieval / 'queries.csv')
    accepted = [r for r in queries if r['accepted'].lower() == 'true']
    assert len(queries) == ret['queried_frames'] == 162
    assert len(accepted) == ret['accepted_candidates'] == 23
    assert all(float(r['sc_distance']) < .15 for r in accepted)
    assert all(float(r['time_gap_s']) >= 30 for r in queries)
    near = sum(float(r['reference_distance_m']) <= 5 for r in accepted)
    assert near == ret['accepted_near_by_reference'] == 23

    geometry = runs / 'kitti0020_geometry_v1'
    geo = read_json(geometry / 'report.json')
    results = read_csv(geometry / 'results.csv')
    assert len(results) == geo['tested_candidates'] == 23
    assert {(r['query_id'], r['candidate_id']) for r in results} == {
        (r['query_id'], r['candidate_id']) for r in accepted
    }
    assert sha(retrieval / 'queries.csv') == geo['retrieval_sha256']
    ref_path = runs / 'kitti0020_reference_v2/reference.npz'
    assert sha(ref_path) == geo['reference_sha256']
    ref = np.load(ref_path, allow_pickle=False)
    lookup = {int(v): i for i, v in enumerate(ref['ids'])}
    ts = np.load(geometry / 'transforms.npz', allow_pickle=False)
    transform_lookup = {(int(q), int(c)): T for q, c, T in zip(
        ts['query_ids'], ts['candidate_ids'], ts['T_query_candidate'])}
    translation, rotation = [], []
    for row in results:
        q, c = int(row['query_id']), int(row['candidate_id'])
        T = transform_lookup[q, c]
        assert np.isfinite(T).all()
        assert np.allclose(T[3], [0, 0, 0, 1])
        assert np.allclose(T[:3, :3].T @ T[:3, :3], np.eye(3), atol=1e-6)
        expected = (np.linalg.inv(ref['T_reference_velo'][lookup[q]])
                    @ ref['T_reference_velo'][lookup[c]])
        delta = np.linalg.inv(expected) @ T
        te = float(np.linalg.norm(delta[:3, 3]))
        re = float(np.rad2deg(Rotation.from_matrix(delta[:3, :3]).magnitude()))
        assert abs(te - float(row['reference_translation_error_m'])) < 1e-8
        assert abs(re - float(row['reference_rotation_error_deg'])) < 1e-8
        gate = (float(row['forward_overlap']) >= .5
                and float(row['reverse_overlap']) >= .5
                and float(row['forward_inlier_rmse_m']) <= .3
                and float(row['reverse_inlier_rmse_m']) <= .3)
        assert gate and row['geometry_pass'].lower() == 'true'
        translation.append(te)
        rotation.append(re)
    assert geo['geometry_passed'] == 23
    assert abs(np.median(translation) - geo['passed_reference_translation_error_median_m']) < 1e-8
    assert abs(np.median(rotation) - geo['passed_reference_rotation_error_median_deg']) < 1e-8
    for report_path, fields in (
        (runs / 'kitti0020_descriptors_v1/manifest.json', {
            'script_sha256': ART / 'scancontext/build_kitti_descriptors.py',
            'reference_sha256': ref_path}),
        (retrieval / 'report.json', {
            'script_sha256': ART / 'scancontext/retrieve_kitti_v1.py',
            'descriptor_sha256': runs / 'kitti0020_descriptors_v1/descriptors.npz'}),
        (geometry / 'report.json', {
            'script_sha256': ART / 'scancontext/verify_kitti_icp_v1.py'}),
    ):
        recorded = read_json(report_path)
        for key, file in fields.items():
            assert sha(file) == recorded[key], (file, key)
    print(json.dumps({
        'status': 'PASS', 'archived_files_hash_checked': checked,
        'upstream_files_not_redistributed': sorted(omitted),
        'python_files_syntax_checked': len(python_files),
        'ate_recomputed_m': ate, 'retrieval_queries': len(queries),
        'accepted_and_geometry_verified': len(results),
        'relative_translation_error_median_m': float(np.median(translation)),
        'relative_rotation_error_median_deg': float(np.median(rotation)),
        'scope': 'Archived evidence consistency; no ROS replay or raw-cloud ICP rerun.'
    }, indent=2))

if __name__ == '__main__':
    main()
