"""Learning exercise: project a PCD height band onto an XY count grid.

White cells are below the point-count threshold, not ray-verified free space.
This stage does not add artificial walls, filter components, or generate a world.
"""
import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read_xyz(path):
    header = {}
    with path.open('rb') as stream:
        for _ in range(100):
            line = stream.readline().decode('ascii').strip()
            if not line or line.startswith('#'):
                continue
            key, *values = line.split()
            header[key] = values
            if key == 'DATA':
                offset = stream.tell()
                break
        else:
            raise ValueError('No DATA entry found in PCD header')
    if (header['DATA'] != ['binary']
            or any(v != '4' for v in header['SIZE'])
            or any(v != 'F' for v in header['TYPE'])
            or any(v != '1' for v in header.get('COUNT', ['1'] * len(header['FIELDS'])))):
        raise ValueError('This exercise expects uncompressed binary float32 scalar fields')
    n = int(header['POINTS'][0])
    fields = header['FIELDS']
    if path.stat().st_size != offset + n * len(fields) * 4:
        raise ValueError('PCD byte count does not match its header')
    raw = np.memmap(path, dtype='<f4', mode='r', offset=offset, shape=(n, len(fields)))
    return raw[:, fields.index('x')], raw[:, fields.index('y')], raw[:, fields.index('z')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pcd', type=Path, default=Path('/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd'))
    parser.add_argument('--z', type=float, nargs=2, required=True, metavar=('MIN', 'MAX'))
    parser.add_argument('--min-points', type=int, default=5)
    parser.add_argument('--bounds', type=float, nargs=4,
                        default=[-2.2, 1.4, -1.8, 3.8], metavar=('XMIN', 'XMAX', 'YMIN', 'YMAX'))
    parser.add_argument('--resolution', type=float, default=0.1)
    parser.add_argument('--out-dir', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--name', default=None, help='Output filename stem, without directory components')
    args = parser.parse_args()
    z_min, z_max = args.z
    if not np.isfinite([z_min, z_max]).all() or z_min >= z_max or args.min_points < 1:
        parser.error('Require Z_MIN < Z_MAX and min-points >= 1')

    # Step 1: choose a region and height band in the source coordinate frame.
    xmin, xmax, ymin, ymax = args.bounds
    resolution = args.resolution
    if (not np.isfinite([xmin, xmax, ymin, ymax, resolution]).all()
            or xmin >= xmax or ymin >= ymax or resolution <= 0):
        parser.error('Require finite increasing bounds and positive resolution')
    shape_float = np.array([(ymax-ymin)/resolution, (xmax-xmin)/resolution])
    shape = np.rint(shape_float).astype(int)
    if not np.allclose(shape_float, shape) or np.any(shape < 1) or np.prod(shape) > 2_000_000:
        parser.error('Bounds must cover whole grid cells and at most two million cells')
    x, y, z = read_xyz(args.pcd)
    selected = ((x >= xmin) & (x < xmax) & (y >= ymin) & (y < ymax)
                & (z >= z_min) & (z <= z_max)
                & np.isfinite(x) & np.isfinite(y) & np.isfinite(z))
    px, py, pz = [a[selected].astype(np.float64) for a in (x, y, z)]
    # Enforce exact bounds after promotion: float32 boundary comparisons can round.
    inside = ((px >= xmin) & (px < xmax) & (py >= ymin) & (py < ymax)
              & (pz >= z_min) & (pz <= z_max))
    px, py = px[inside], py[inside]
    if len(px) == 0:
        parser.error('No points in the selected height band and XY region')

    # Step 2: convert coordinates in metres to integer grid indices.
    height, width = map(int, shape)
    col = np.floor((px - xmin) / resolution).astype(int)
    row = np.floor((py - ymin) / resolution).astype(int)

    # Step 3: count retained points per cell and apply a density threshold.
    count = np.zeros((height, width), dtype=np.int64)
    np.add.at(count, (row, col), 1)
    occupied = count >= args.min_points

    folder = args.out_dir.resolve()
    folder.mkdir(parents=True, exist_ok=True)
    stem = args.name or f'projection_{z_min:g}_{z_max:g}'
    if stem in ('.', '..') or '/' in stem or '\\' in stem:
        parser.error('Name must not contain directory components')
    np.savez_compressed(folder / f'{stem}.npz', point_count=count, occupied=occupied,
                        bounds=np.array([xmin, xmax, ymin, ymax]),
                        resolution=resolution, height_band=np.array(args.z),
                        min_points_per_cell=args.min_points, selected_points=len(px),
                        source_pcd=str(args.pcd.resolve()))
    fig, ax = plt.subplots(figsize=(5.5, 7.4))
    ax.imshow(~occupied, origin='lower', extent=[xmin, xmax, ymin, ymax],
              cmap='gray', vmin=0, vmax=1, interpolation='nearest')
    ax.set(xlabel='Source X (m)', ylabel='Source Y (m)',
           title=f'XY projection: Z in [{z_min:g}, {z_max:g}] m\n'
                 f'{len(px):,} points; black cells have >= {args.min_points} points')
    ax.set_aspect('equal')
    fig.text(.5, .025, 'White = below threshold; not verified traversable ground.\n'
             'Raw projection: no artificial border or morphology applied.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .07, 1, 1))
    figure_path = folder / f'{stem}.png'
    fig.savefig(figure_path, dpi=150)
    plt.close(fig)
    print(f'Height band: [{z_min:g}, {z_max:g}] m')
    print(f'Selected points: {len(px)}')
    print(f'Grid: {width} columns x {height} rows; resolution={resolution:g} m')
    print(f'Cells meeting threshold: {int(occupied.sum())}/{occupied.size}')
    print(f'Figure: {figure_path}')


if __name__ == '__main__':
    main()
