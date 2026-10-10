"""Recompute evo-matched ATE and document evaluated versus unassessed time ranges."""
import argparse
import copy
import importlib.metadata
from pathlib import Path
import numpy as np
from evo.core import metrics, sync
from evo.tools import file_interface
from common import load_tum, sha256, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--groundtruth', type=Path, required=True)
    parser.add_argument('--estimate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--plot', type=Path)
    parser.add_argument('--max-diff', type=float, default=0.05)
    args = parser.parse_args()
    if args.output.exists() or (args.plot and args.plot.exists()):
        parser.error('Output already exists; choose new paths')
    gt, est = load_tum(args.groundtruth), load_tum(args.estimate)
    ref_full = file_interface.read_tum_trajectory_file(str(args.groundtruth))
    est_full = file_interface.read_tum_trajectory_file(str(args.estimate))
    ref, matched = sync.associate_trajectories(ref_full, est_full, max_diff=args.max_diff)
    aligned = copy.deepcopy(matched)
    rotation, translation, scale = aligned.align(ref, correct_scale=False)
    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((ref, aligned))
    report = {
        'evo_version': importlib.metadata.version('evo'),
        'estimate_sha256': sha256(args.estimate), 'groundtruth_sha256': sha256(args.groundtruth),
        'estimate_poses': len(est), 'estimate_start_s': float(est[0, 0]),
        'estimate_end_s': float(est[-1, 0]), 'estimate_span_s': float(np.ptp(est[:, 0])),
        'groundtruth_poses': len(gt), 'groundtruth_start_s': float(gt[0, 0]),
        'groundtruth_end_s': float(gt[-1, 0]), 'groundtruth_span_s': float(np.ptp(gt[:, 0])),
        'matched_pairs': matched.num_poses, 'matched_estimate_start_s': float(matched.timestamps[0]),
        'matched_estimate_end_s': float(matched.timestamps[-1]),
        'matched_span_s': float(np.ptp(matched.timestamps)), 'max_timestamp_difference_s': args.max_diff,
        'alignment': 'SE(3), Umeyama, no scale correction', 'scale': float(scale),
        'translation_ape_m': {k: float(v) for k, v in ape.get_all_statistics().items()},
        'estimate_poses_after_groundtruth': int(np.sum(est[:, 0] > gt[-1, 0])),
        'tail_after_groundtruth_s': float(max(0, est[-1, 0] - gt[-1, 0])),
        'estimate_poses_before_groundtruth': int(np.sum(est[:, 0] < gt[0, 0])),
        'median_pose_interval_s': float(np.median(np.diff(est[:, 0]))),
        'maximum_pose_interval_s': float(np.max(np.diff(est[:, 0]))),
        'scope_note': 'Errors apply only to matched poses, not every estimated pose or map point.'
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_json(args.output, report)
    if args.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        all_positions = est_full.positions_xyz @ rotation.T + translation
        after = est[:, 0] > gt[-1, 0]
        fig, ax = plt.subplots(figsize=(10, 4.7), layout='constrained')
        ax.plot(ref_full.positions_xyz[:, 0], ref_full.positions_xyz[:, 1], c='black', lw=1.5, label='IMU ground truth')
        ax.plot(all_positions[:, 0], all_positions[:, 1], c='#94a3b8', lw=1, label='All estimated poses (aligned)')
        ax.scatter(aligned.positions_xyz[:, 0], aligned.positions_xyz[:, 1], s=5, c='#0284c7', label=f'{matched.num_poses} matched poses')
        ax.plot(all_positions[after, 0], all_positions[after, 1], c='#ea580c', lw=2, label=f'After GT: {int(after.sum())} poses, unassessed')
        ax.set(title=f'SE(3), no scale | ATE RMSE {report["translation_ape_m"]["rmse"]:.3f} m\nMatched span {report["matched_span_s"]:.2f} s / estimate {report["estimate_span_s"]:.2f} s; match threshold {args.max_diff:.2f} s', xlabel='X (m)', ylabel='Y (m)')
        ax.set_aspect('equal', adjustable='box')
        ax.grid(alpha=.2)
        ax.legend(fontsize=9)
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(args.plot, dpi=180, bbox_inches='tight')
        plt.close(fig)
    print(f'{matched.num_poses} pairs, RMSE={report["translation_ape_m"]["rmse"]:.9f} m; {args.output}')


if __name__ == '__main__':
    main()
