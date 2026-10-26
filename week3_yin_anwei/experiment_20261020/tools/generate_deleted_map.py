import argparse
import json
from pathlib import Path

import numpy as np
import open3d as o3d

parser = argparse.ArgumentParser()
parser.add_argument("--ratio", type=float, required=True)
parser.add_argument("--seed", type=int, required=True)
parser.add_argument("--block", type=float, default=3.0)
args = parser.parse_args()

assert np.isfinite(args.ratio) and 0 <= args.ratio < 1
assert np.isfinite(args.block) and args.block > 0
assert args.seed >= 0

source = Path("/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd")
ratio_label = f"{args.ratio:.2f}".replace(".", "p")
block_label = f"{args.block:g}".replace(".", "p")
folder = Path("/home/yaw/fastlio_week3/maps") / (
    f"delete_block{block_label}m_ratio{ratio_label}_seed{args.seed}"
)
assert not folder.exists(), "输出目录已存在，请勿覆盖"

original = o3d.io.read_point_cloud(str(source))
xyz = np.asarray(original.points)
assert len(xyz) > 0 and np.isfinite(xyz).all()

# 固定网格原点为(0,0,0)，计算每个点所属的空间块。
block_indices = np.floor(xyz / args.block).astype(np.int64)
cells, inverse = np.unique(
    block_indices, axis=0, return_inverse=True
)

# 对有点的块排序，删除随机顺序中的前一部分。
rng = np.random.default_rng(args.seed)
order = rng.permutation(len(cells))
deleted_count = int(np.floor(args.ratio * len(cells)))
deleted_ids = order[:deleted_count]

keep_cell = np.ones(len(cells), dtype=bool)
keep_cell[deleted_ids] = False
kept_xyz = xyz[keep_cell[inverse]]
assert len(kept_xyz) > 0

result = o3d.geometry.PointCloud()
result.points = o3d.utility.Vector3dVector(kept_xyz)

folder.mkdir(parents=True, exist_ok=False)
destination = folder / "map.pcd"
if not o3d.io.write_point_cloud(
    str(destination), result, write_ascii=False, compressed=False
):
    raise RuntimeError("地图保存失败")

np.save(folder / "deleted_cells.npy", cells[deleted_ids])

report = {
    "source": str(source),
    "output": str(destination),
    "block_size_m": args.block,
    "grid_origin_xyz_m": [0, 0, 0],
    "requested_deleted_block_fraction": args.ratio,
    "seed": args.seed,
    "occupied_blocks": len(cells),
    "deleted_blocks": deleted_count,
    "original_points": len(xyz),
    "remaining_points": len(kept_xyz),
    "actual_deleted_point_fraction": 1 - len(kept_xyz) / len(xyz),
    "numpy_version": np.__version__,
    "open3d_version": o3d.__version__,
    "output_fields": "XYZ only",
}
with (folder / "report.json").open("x") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
