import argparse
import json
from pathlib import Path

import numpy as np
import open3d as o3d

parser = argparse.ArgumentParser()
parser.add_argument("--sigma", type=float, required=True)
parser.add_argument("--seed", type=int, required=True)
args = parser.parse_args()

assert np.isfinite(args.sigma) and args.sigma >= 0
assert args.seed >= 0

source = Path("/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd")
sigma_label = f"{args.sigma:.2f}".replace(".", "p")
folder = Path("/home/yaw/fastlio_week3/maps") / (
    f"noise_sigma{sigma_label}_seed{args.seed}"
)

assert not folder.exists(), "输出目录已存在，请勿覆盖"

original = o3d.io.read_point_cloud(str(source))
xyz = np.asarray(original.points)
assert len(xyz) > 0 and np.isfinite(xyz).all()

rng = np.random.default_rng(args.seed)
noise = rng.normal(0.0, args.sigma, size=xyz.shape)
noisy_xyz = xyz + noise

result = o3d.geometry.PointCloud()
result.points = o3d.utility.Vector3dVector(noisy_xyz)

folder.mkdir(parents=True, exist_ok=False)
destination = folder / "map.pcd"
if not o3d.io.write_point_cloud(
    str(destination), result, write_ascii=False, compressed=False
):
    raise RuntimeError("地图保存失败")

report = {
    "source": str(source),
    "output": str(destination),
    "points": len(xyz),
    "sigma_per_axis_m": args.sigma,
    "seed": args.seed,
    "numpy_version": np.__version__,
    "open3d_version": o3d.__version__,
    "noise_mean_xyz_m": noise.mean(axis=0).tolist(),
    "noise_std_xyz_m": noise.std(axis=0).tolist(),
    "output_fields": "XYZ only",
}
with (folder / "report.json").open("x") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
