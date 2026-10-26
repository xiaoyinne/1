import json
from pathlib import Path

import numpy as np
import open3d as o3d

source = Path("/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd")
output = Path("/home/yaw/fastlio_week3/maps/noise_sigma0p10_seed11")

sigma = 0.1
seed = 11

# 1. 读取原地图的XYZ坐标。
original = o3d.io.read_point_cloud(str(source))
xyz = np.asarray(original.points)
assert len(xyz) > 0, "地图为空或读取失败"
assert np.isfinite(xyz).all(), "地图包含非有限坐标"

# 2. 每个点的X、Y、Z分别生成高斯噪声。
rng = np.random.default_rng(seed)
noise = rng.normal(loc=0.0, scale=sigma, size=xyz.shape)

# 3. 相加生成新坐标，不原地修改原坐标。
noisy_xyz = xyz + noise

# 4. 建立新点云并另存，已有输出目录时停止。
output.mkdir(parents=True, exist_ok=False)
noisy_map = o3d.geometry.PointCloud()
noisy_map.points = o3d.utility.Vector3dVector(noisy_xyz)

destination = output / "map.pcd"
success = o3d.io.write_point_cloud(
    str(destination), noisy_map,
    write_ascii=False, compressed=False
)
if not success:
    raise RuntimeError("加噪地图写入失败")

report = {
    "source": str(source),
    "output": str(destination),
    "points": len(xyz),
    "sigma_per_axis_m": sigma,
    "seed": seed,
    "numpy_version": np.__version__,
    "open3d_version": o3d.__version__,
    "noise_mean_xyz_m": noise.mean(axis=0).tolist(),
    "noise_std_xyz_m": noise.std(axis=0).tolist(),
    "output_fields": "XYZ only",
}
with (output / "report.json").open("x") as f:
    json.dump(report, f, indent=2)

print(json.dumps(report, indent=2))
