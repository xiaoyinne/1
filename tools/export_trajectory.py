"""Export unaligned TUM poses as row-major KITTI [R|t] and timestamps."""
import argparse
from pathlib import Path
import numpy as np
from scipy.spatial.transform import Rotation
from common import load_tum


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tum', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    poses = load_tum(args.tum)
    targets = [args.output_dir / n for n in ('trajectory_kitti.txt', 'trajectory_times.txt')]
    if any(p.exists() for p in targets):
        parser.error('Output already exists; choose a new directory')
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rotations = Rotation.from_quat(poses[:, 4:8]).as_matrix()
    matrices = np.concatenate((rotations, poses[:, 1:4, None]), axis=2)
    np.savetxt(targets[0], matrices.reshape(-1, 12), fmt='%.9f')
    np.savetxt(targets[1], poses[:, 0], fmt='%.9f')
    print(f'Exported {len(poses)} poses; no alignment, scaling or origin reset applied')


if __name__ == '__main__':
    main()
