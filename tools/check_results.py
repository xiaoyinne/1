"""Check saved artifacts; structural success is not a map-accuracy certificate."""
import argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from common import load_tum, read_pcd, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pcd', type=Path, required=True)
    parser.add_argument('--tum', type=Path, required=True)
    parser.add_argument('--kitti', type=Path)
    parser.add_argument('--times', type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--mapping-log', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Report already exists')
    header, xyz = read_pcd(args.pcd)
    poses = load_tum(args.tum)
    digest = sha256(args.pcd)
    if args.expected_sha256 and digest != args.expected_sha256.lower():
        raise ValueError('PCD SHA256 mismatch')
    if bool(args.kitti) != bool(args.times):
        parser.error('--kitti and --times must be provided together')
    if args.kitti:
        kitti = np.loadtxt(args.kitti, ndmin=2)
        times = np.loadtxt(args.times, ndmin=1)
        expected = np.concatenate((Rotation.from_quat(poses[:, 4:8]).as_matrix(), poses[:, 1:4, None]), axis=2).reshape(-1, 12)
        if kitti.shape != expected.shape or not np.allclose(kitti, expected, atol=2e-8, rtol=0):
            raise ValueError('KITTI matrices do not match TUM')
        if times.shape != poses[:, 0].shape or not np.allclose(times, poses[:, 0], atol=1e-7, rtol=0):
            raise ValueError('KITTI timestamps do not match TUM')
    warnings = None
    if args.mapping_log:
        warnings = args.mapping_log.read_text(errors='replace').count('No Effective Points')
    report = {'pcd_bytes': args.pcd.stat().st_size, 'pcd_points': len(xyz), 'pcd_sha256': digest,
              'pcd_fields': header['FIELDS'], 'xyz_span_m': np.ptp(xyz, axis=0).tolist(),
              'trajectory_poses': len(poses), 'trajectory_span_s': float(np.ptp(poses[:, 0])),
              'no_effective_points_count': warnings,
              'structural_checks_passed': True,
              'scope_note': 'Nonempty, finite PCD and consistent trajectory formats; geometric accuracy must be evaluated separately.'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    print(f'PASS: {len(xyz)} points, {len(poses)} poses; warnings={warnings}')
    if warnings:
        raise SystemExit('Artifact structure is valid but mapping has No Effective Points warnings; inspect the run')


if __name__ == '__main__':
    main()
