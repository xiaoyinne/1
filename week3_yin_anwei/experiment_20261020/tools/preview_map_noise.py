from pathlib import Path
import json

import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

folder = Path("/home/yaw/fastlio_week3/maps/noise_sigma0p10_seed11")
original = np.asarray(o3d.io.read_point_cloud(
    "/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd"
).points)
noisy = np.asarray(o3d.io.read_point_cloud(str(folder / "map.pcd")).points)

assert original.shape == noisy.shape

# 在地图中央附近选一个实际存在的点作为显示中心。
median = np.median(original, axis=0)
center = original[np.argmin(np.sum((original - median) ** 2, axis=1))]

# 按原图选择4米×4米区域，以及厚0.6米的水平切片。
mask = (
    (np.abs(original[:, 0] - center[0]) <= 2)
    & (np.abs(original[:, 1] - center[1]) <= 2)
    & (np.abs(original[:, 2] - center[2]) <= 0.3)
)
indices = np.flatnonzero(mask)
assert len(indices) > 0

# 显示点过多时抽样，两幅图仍使用相同点编号。
if len(indices) > 30000:
    rng = np.random.default_rng(123)
    indices = rng.choice(indices, 30000, replace=False)

fig, axes = plt.subplots(1, 2, figsize=(10, 5))
for ax, points, title in [
    (axes[0], original, "Original map"),
    (axes[1], noisy, "Noise: sigma = 0.1 m per axis"),
]:
    ax.scatter(points[indices, 0], points[indices, 1], s=0.6, alpha=0.5)
    ax.set_xlim(center[0] - 2, center[0] + 2)
    ax.set_ylim(center[1] - 2, center[1] + 2)
    ax.set_aspect("equal")
    ax.set_xlabel("Map X (m)")
    ax.set_ylabel("Map Y (m)")
    ax.set_title(title)
    ax.grid(alpha=0.2)

fig.suptitle("XY view of the same points selected from an original-map Z slice")
fig.tight_layout()
path = folder / "local_comparison.png"
fig.savefig(path, dpi=180)
plt.close(fig)

settings = {
    "center_xyz_m": center.tolist(),
    "display_width_m": 4,
    "original_z_slice_thickness_m": 0.6,
    "displayed_points_per_panel": len(indices),
}
(folder / "preview_settings.json").write_text(json.dumps(settings, indent=2))
print("每幅图显示点数：", len(indices))
print("图片已保存：", path)
