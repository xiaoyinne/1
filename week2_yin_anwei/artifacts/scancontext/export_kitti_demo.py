from pathlib import Path
import csv
import json
import numpy as np
import open3d as o3d
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

base = Path("/home/yaw/fastlio_week2/scancontext/runs")
geometry = base / "kitti0020_geometry_v1"
out = geometry / "demo"
out.mkdir(exist_ok=True)

with (geometry / "results.csv").open() as f:
    results = list(csv.DictReader(f))
with (base / "kitti0020_retrieval_v1/queries.csv").open() as f:
    queries = list(csv.DictReader(f))

report = json.loads((geometry / "report.json").read_text())
reference = np.load(
    base / "kitti0020_reference_v2/reference.npz", allow_pickle=False
)
transforms = np.load(geometry / "transforms.npz", allow_pickle=False)
lookup = {int(v): i for i, v in enumerate(reference["ids"])}
positions = reference["T_reference_velo"][:, :3, 3]
valid = reference["valid"]

passed = [r for r in results if r["geometry_pass"].lower() == "true"]
assert passed, "没有通过几何验证的候选"

# 选平移参考误差居中的样本展示，避免只挑最佳结果。
ordered = sorted(
    passed, key=lambda r: float(r["reference_translation_error_m"])
)
example = ordered[len(ordered) // 2]
q, c = int(example["query_id"]), int(example["candidate_id"])
mask = (
    (transforms["query_ids"] == q)
    & (transforms["candidate_ids"] == c)
)
assert mask.sum() == 1
T = transforms["T_query_candidate"][mask][0]

def points(frame_id):
    path = str(reference["lidar_files"][lookup[frame_id]])
    p = np.fromfile(path, dtype="<f4").reshape(-1, 4)[:, :3]
    radius = np.linalg.norm(p[:, :2], axis=1)
    p = p[np.isfinite(p).all(axis=1) & (radius > 1) & (radius < 80)]
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(p)
    return pc.voxel_down_sample(0.3)

candidate = points(c)
query = points(q)
candidate.transform(T)
candidate.paint_uniform_color([1.0, 0.45, 0.05])
query.paint_uniform_color([0.1, 0.45, 1.0])
assert o3d.io.write_point_cloud(
    str(out / f"aligned_{q}_{c}.ply"), candidate + query
)

fig, axes = plt.subplots(1, 3, figsize=(18, 5))

ax = axes[0]
ax.plot(positions[valid, 0], positions[valid, 1],
        color="0.65", linewidth=1, label="OXTS-derived reference")
for n, r in enumerate(passed):
    qi, ci = lookup[int(r["query_id"])], lookup[int(r["candidate_id"])]
    ax.plot(positions[[ci, qi], 0], positions[[ci, qi], 1],
            color="tab:orange", alpha=0.7)
    ax.scatter(positions[qi, 0], positions[qi, 1],
               s=12, color="tab:red",
               label="Verified query" if n == 0 else None)
ax.set(title="23 verified historical matches", xlabel="X (m)", ylabel="Y (m)")
ax.axis("equal")
ax.legend(fontsize=8)

ax = axes[1]
origin = int(reference["scan_stamps_ns"][0])
times = np.array([
    (int(reference["scan_stamps_ns"][lookup[int(r["query_id"])]]) - origin) / 1e9
    for r in queries
])
scores = np.array([float(r["sc_distance"]) for r in queries])
near = np.array([r["near_by_reference"].lower() == "true" for r in queries])
ax.scatter(times[~near], scores[~near], s=12, color="0.6",
           label="Top-1 reference distance > 5 m")
ax.scatter(times[near], scores[near], s=14, color="tab:blue",
           label="Top-1 reference distance <= 5 m")
ax.axhline(0.15, color="tab:red", linestyle="--", label="SC threshold 0.15")
ax.set(title="Historical retrieval (30 s exclusion)",
       xlabel="Time since first scan (s)", ylabel="SC distance")
ax.legend(fontsize=8)

ax = axes[2]
a = np.asarray(candidate.points)
b = np.asarray(query.points)
# 图中仅裁剪到 30 米，指标仍使用原来的 80 米范围。
a = a[np.linalg.norm(a[:, :2], axis=1) < 30]
b = b[np.linalg.norm(b[:, :2], axis=1) < 30]
ax.scatter(b[:, 0], b[:, 1], s=0.3, alpha=0.4,
           color="tab:blue", label=f"Query {q}")
ax.scatter(a[:, 0], a[:, 1], s=0.3, alpha=0.4,
           color="tab:orange", label=f"History {c}, ICP aligned")
ax.set(title=f"Representative alignment: {q} -> {c}",
       xlabel="Query-frame X (m)", ylabel="Query-frame Y (m)")
ax.axis("equal")
ax.legend(fontsize=8, markerscale=8)

for ax in axes:
    ax.grid(alpha=0.2)
fig.tight_layout()
fig.savefig(out / "scancontext_demo.png", dpi=200)
plt.close(fig)

text = f"""# KITTI Scan Context 离线回环演示

数据：2011_09_30_drive_0020_sync。
每隔 5 帧采样，共 220 帧；描述子 20 环、60 扇区、80 米范围。
历史检索排除最近 30 秒，环向索引取 10 个候选，SC 阈值为 0.15。

## 检索结果
- 162 个有效历史查询。
- 按 5 米参考位置标准，54 个查询存在附近历史帧。
- 这 54 个查询的第一名均为附近历史帧。
- 23 个第一名通过 SC 阈值，均在参考位置 5 米内。
- 其余 31 个附近查询未通过 SC 阈值，不能声称全部被接受。

## 几何验证
- 全部 23 个通过 SC 阈值的候选接受验证，23 个通过。
- 初值仅使用 SC 旋转，平移为零，不使用参考位姿初始化。
- 筛选：双向重叠 >= 0.5，双向内点 RMSE <= 0.3 米。
- 平移参考误差中位数：
  {report["passed_reference_translation_error_median_m"]:.6f} 米。
- 平移参考误差最大值：
  {report["passed_reference_translation_error_max_m"]:.6f} 米。
- 旋转参考误差中位数：
  {report["passed_reference_rotation_error_median_deg"]:.6f} 度。
- 旋转参考误差最大值：
  {report["passed_reference_rotation_error_max_deg"]:.6f} 度。

## 展示文件
- scancontext_demo.png：轨迹、检索分数和配准叠加。
- aligned_{q}_{c}.ply：配准后的双色点云。
- 展示样本按通过样本的平移参考误差排序，取中间样本。

## 结论边界
完成了单序列离线地点检索及几何验证。
23 对匹配属于同一序列的重复经过区域，不代表 23 个独立回环事件。
参考位姿来自插值后的 OXTS；上述误差不是轨迹 ATE。
未接入在线重定位或闭环优化，也未证明跨序列泛化能力。
"""
(out / "README.md").write_text(text, encoding="utf-8")
print("展示样本：", q, "->", c)
print("图像：", out / "scancontext_demo.png")
print("说明：", out / "README.md")
print("点云：", out / f"aligned_{q}_{c}.ply")
