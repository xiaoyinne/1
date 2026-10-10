"""Render actual PCD points with equal axis scales and explicitly labeled sampling."""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import read_pcd, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pcd', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Choose a new output directory')
    args.output_dir.mkdir(parents=True)
    _, xyz = read_pcd(args.pcd)
    # Limits are based on data quantiles, recorded explicitly; no map file is modified.
    limits = np.quantile(xyz[:, :2], [.01, .99], axis=0)
    median = np.median(xyz[:, :2], axis=0)
    half = 5.0
    detail = xyz[(np.abs(xyz[:, 0] - median[0]) <= half) & (np.abs(xyz[:, 1] - median[1]) <= half)]
    for filename, points, title, bounds in (
        ('map_top.png', xyz, 'Accumulated map: XY view (1st–99th percentile window)', limits),
        ('map_detail.png', detail, 'Local XY projection: 10 m window around median XY', np.array([median - half, median + half]))):
        step = max(1, int(np.ceil(len(points) / 350000)))
        sampled = points[::step]
        fig, ax = plt.subplots(figsize=(9, 7), layout='constrained')
        plot = ax.scatter(sampled[:, 0], sampled[:, 1], c=sampled[:, 2], s=.25, cmap='viridis', rasterized=True)
        ax.set(xlim=bounds[:, 0], ylim=bounds[:, 1], xlabel='X (m)', ylabel='Y (m)',
               title=f'{title}\nDisplay stride {step}; original map {len(xyz):,} points; camera_init, meters')
        ax.set_aspect('equal', adjustable='box')
        ax.grid(alpha=.15)
        fig.colorbar(plot, ax=ax, label='Z (m)')
        fig.savefig(args.output_dir / filename, dpi=180)
        plt.close(fig)
    write_json(args.output_dir / 'render_info.json', {
        'point_count': len(xyz), 'full_xyz_span_m': np.ptp(xyz, axis=0).tolist(),
        'top_xy_bounds_m': limits.tolist(), 'detail_center_xy_m': median.tolist(),
        'detail_width_m': 10, 'note': 'XY projection merges heights; visible bands alone do not prove wall duplication. Display crop/stride only, source PCD unchanged.'})


if __name__ == '__main__':
    main()
