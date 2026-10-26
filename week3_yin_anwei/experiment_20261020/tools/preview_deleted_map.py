from pathlib import Path
import json

import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

folder = Path("/home/yaw/fastlio_week3/maps/delete_block3m_ratio0p25_seed11")
report = json.loads((folder / "report.json").read_text())
size = report["block_size_m"]

xyz = np.asarray(o3d.io.read_point_cloud(report["source"]).points)
deleted = np.load(folder / "deleted_cells.npy")

cells, inverse, counts = np.unique(
    np.floor(xyz / size).astype(np.int64),
    axis=0, return_inverse=True, return_counts=True
)

cell_lookup = {tuple(cell): i for i, cell in enumerate(cells)}
deleted_ids = np.array([cell_lookup[tuple(cell)] for cell in deleted])

# 选择点数最多的被删块，方便观察缺口。
target_id = deleted_ids[np.argmax(counts[deleted_ids])]
target = cells[target_id]
center = (target + 0.5) * size

keep_cell = np.ones(len(cells), dtype=bool)
keep_cell[deleted_ids] = False

# 展示9米×9米范围，Z方向只取目标块所在的3米厚层。
mask = (
    (np.abs(xyz[:, 0] - center[0]) <= 4.5)
    & (np.abs(xyz[:, 1] - center[1]) <= 4.5)
    & (xyz[:, 2] >= target[2] * size)
    & (xyz[:, 2] < (target[2] + 1) * size)
)
indices = np.flatnonzero(mask)

if len(indices) > 40000:
    rng = np.random.default_rng(123)
    indices = rng.choice(indices, 40000, replace=False)

# 右图仅保留同一批展示点中未被删除的点。
remaining = indices[keep_cell[inverse[indices]]]

fig, axes = plt.subplots(1, 2, figsize=(11, 5))
for ax, ids, title in [
    (axes[0], indices, "Original map"),
    (axes[1], remaining, "Delete 25% of occupied blocks"),
]:
    ax.scatter(xyz[ids, 0], xyz[ids, 1], s=0.6, alpha=0.5)
    ax.add_patch(Rectangle(
        (target[0] * size, target[1] * size),
        size, size, fill=False, edgecolor="red", linewidth=1.5
    ))
    ax.set_xlim(center[0] - 4.5, center[0] + 4.5)
    ax.set_ylim(center[1] - 4.5, center[1] + 4.5)
    ax.set_aspect("equal")
    ax.set_xlabel("Map X (m)")
    ax.set_ylabel("Map Y (m)")
    ax.set_title(title)
    ax.grid(alpha=0.2)

fig.suptitle(
    "XY view of a 3 m Z slab | most populated deleted block highlighted"
)
fig.tight_layout()
destination = folder / "local_comparison.png"
fig.savefig(destination, dpi=180)
plt.close(fig)

print("左图展示点数：", len(indices))
print("右图展示点数：", len(remaining))
print("红框对应块索引：", target)
print("图片已保存：", destination)
