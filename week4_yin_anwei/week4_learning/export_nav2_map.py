"""Export the already-taught projection grid as a Nav2 PGM/YAML map.

This preserves the projection exactly: no border, morphology, or free-space
verification is added. White means below the selected-point threshold.
"""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
import yaml


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projection', type=Path,
                        default=root/'projection_-1.5_-0.8.npz')
    parser.add_argument('--out-dir', type=Path, default=root/'scene_learning')
    args = parser.parse_args()
    with np.load(args.projection, allow_pickle=False) as data:
        occupied = data['occupied']
        bounds = np.asarray(data['bounds'], dtype=float)
        resolution = float(data['resolution'])
    if occupied.dtype != np.bool_ or occupied.ndim != 2 or not occupied.size:
        parser.error('occupied must be a nonempty 2D boolean grid')
    if bounds.shape != (4,) or not np.isfinite(bounds).all():
        parser.error('bounds must be finite [xmin,xmax,ymin,ymax]')
    if not np.isfinite(resolution) or resolution <= 0:
        parser.error('resolution must be finite and positive')
    xmin, xmax, ymin, ymax = bounds
    rows, cols = occupied.shape
    if not np.allclose([xmax-xmin, ymax-ymin],
                       [cols*resolution, rows*resolution], rtol=0, atol=1e-8):
        parser.error('grid dimensions do not match bounds and resolution')
    # Image row zero is the top, while projection row zero is minimum Y.
    image = np.where(np.flipud(occupied), 0, 254).astype(np.uint8)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image).save(args.out_dir/'map.pgm')
    config = {'image': 'map.pgm', 'mode': 'trinary', 'resolution': resolution,
              'origin': [float(xmin), float(ymin), 0.0], 'negate': 0,
              'occupied_thresh': .65, 'free_thresh': .196}
    (args.out_dir/'map.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
    print(f'Map: {cols} columns x {rows} rows; occupied={int(occupied.sum())}')
    print(args.out_dir/'map.yaml')


if __name__ == '__main__':
    main()
