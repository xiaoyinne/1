"""Plot recorded map-frame pose estimates; never moves the simulated robot."""
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    records = json.loads((args.evidence/'results.json').read_text())
    config = yaml.safe_load((ROOT/'scene_learning/map.yaml').read_text())
    image = np.asarray(Image.open(ROOT/'scene_learning'/config['image']))
    x0, y0, _ = config['origin']
    extent = [x0, x0+image.shape[1]*config['resolution'],
              y0, y0+image.shape[0]*config['resolution']]
    fig, axes = plt.subplots(1, len(records), figsize=(5*len(records), 7),
                             squeeze=False, layout='constrained')
    for ax, record in zip(axes[0], records):
        ax.imshow(image, cmap='gray', vmin=0, vmax=254, extent=extent,
                  origin='upper', interpolation='nearest')
        samples = np.asarray(record['estimated_feedback_xy_samples'])
        if samples.size:
            ax.plot(samples[:, 0], samples[:, 1], color='#0077bb', lw=2,
                    label='Feedback pose estimates')
        before = record['before_estimated_pose_xyz']
        after = record['after_estimated_pose_xyz']
        if before:
            ax.scatter(*before[:2], marker='o', s=70, color='#009988', label='Start estimate')
        if after:
            ax.scatter(*after[:2], marker='s', s=45, color='#ee7733', label='End estimate')
        x, y, _ = record['goal_xy_yaw']
        ax.scatter(x, y, marker='*', s=130, color='#cc3311', label='Requested goal')
        ax.add_patch(plt.Circle((x, y), .25, fill=False, linestyle='--',
                               color='#cc3311', alpha=.6))
        ax.set_title(record['case'].replace('_', ' ')+'\n'+record['action_status']+
                     f" | recoveries={record['max_feedback_recoveries']}")
        ax.set_xlabel('Map X (m)')
        ax.set_ylabel('Map Y (m)')
        ax.set_aspect('equal')
        ax.grid(alpha=.15)
    axes[0, 0].legend(loc='upper left', fontsize=8)
    fig.suptitle('Recorded navigation checks: pose estimates, not external ground truth\n'
                 'White cells: below point threshold; synthetic flat floor; dashed circle: 0.25 m XY tolerance', fontsize=11)
    destination = args.evidence/'navigation_checks.png'
    fig.savefig(destination, dpi=160)
    plt.close(fig)
    print(destination)


if __name__ == '__main__':
    main()
