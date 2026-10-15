from pathlib import Path
import json
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation, Slerp

base = Path("/home/yaw/fastlio_week2/scancontext/runs")
src = base / "kitti0020_reference_v1"
out = base / "kitti0020_reference_v2"

data = np.load(src / "reference.npz", allow_pickle=False)
scan_ns = data["scan_stamps_ns"]
oxts_ns = data["oxts_stamps_ns"]
original = data["T_reference_velo"]
files = data["lidar_files"]
ids = data["ids"]

# 使用相对时间，避免大数时间戳损失精度。
origin = int(oxts_ns[0])
sensor_t = (oxts_ns - origin) / 1e9
scan_t = (scan_ns - origin) / 1e9
valid = (scan_ns >= oxts_ns[0]) & (scan_ns <= oxts_ns[-1])

# 只插值，不对 OXTS 时间范围之外的扫描外推。
poses = np.full(original.shape, np.nan)
poses[valid] = np.eye(4)
for axis in range(3):
    poses[valid, axis, 3] = np.interp(
        scan_t[valid], sensor_t, original[:, axis, 3]
    )
rotation_interpolator = Slerp(
    sensor_t, Rotation.from_matrix(original[:, :3, :3])
)
poses[valid, :3, :3] = rotation_interpolator(
    scan_t[valid]
).as_matrix()

near = []
for q in np.flatnonzero(valid):
    history = np.flatnonzero(
        valid & ((scan_ns[q] - scan_ns) >= 30_000_000_000)
    )
    if not len(history):
        continue
    distances = np.linalg.norm(
        poses[history, :3, 3] - poses[q, :3, 3], axis=1
    )
    k = int(np.argmin(distances))
    if distances[k] <= 5:
        near.append((int(q), int(history[k]), float(distances[k])))

# 按查询时间分散抽取，避免只检查几乎相同的相邻帧。
selected = []
if near:
    picks = np.unique(
        np.linspace(0, len(near) - 1, min(8, len(near))).astype(int)
    )
    selected = [near[i] for i in picks]

def cloud(i):
    raw = np.fromfile(str(files[i]), dtype="<f4").reshape(-1, 4)
    p = raw[:, :3]
    radius = np.linalg.norm(p[:, :2], axis=1)
    p = p[np.isfinite(p).all(axis=1) & (radius > 1) & (radius < 80)]
    pc = o3d.geometry.PointCloud()
    pc.points = o3d.utility.Vector3dVector(p)
    return pc.voxel_down_sample(0.3)

print("可插值的扫描数：", int(valid.sum()))
print("时间范围外排除的帧号：", ids[~valid].tolist())
print("插值后存在 5 米内历史帧的查询数：", len(near))
print("\n参考位姿下的点云重叠（未运行 ICP）：", flush=True)

results = []
for q, c, distance in selected:
    source, target = cloud(c), cloud(q)
    T_query_candidate = np.linalg.inv(poses[q]) @ poses[c]
    forward = o3d.pipelines.registration.evaluate_registration(
        source, target, 0.5, T_query_candidate
    )
    reverse = o3d.pipelines.registration.evaluate_registration(
        target, source, 0.5, np.linalg.inv(T_query_candidate)
    )
    result = {
        "query_id": int(ids[q]),
        "candidate_id": int(ids[c]),
        "reference_distance_m": distance,
        "time_gap_s": float((scan_ns[q] - scan_ns[c]) / 1e9),
        "forward_overlap": float(forward.fitness),
        "reverse_overlap": float(reverse.fitness),
        "forward_inlier_rmse_m": (
            float(forward.inlier_rmse) if forward.fitness > 0 else None
        ),
        "reverse_inlier_rmse_m": (
            float(reverse.inlier_rmse) if reverse.fitness > 0 else None
        ),
    }
    results.append(result)
    print(
        f'{ids[q]}->{ids[c]}：距离={distance:.2f}m，'
        f'间隔={result["time_gap_s"]:.1f}s，'
        f'双向重叠={forward.fitness:.3f}/{reverse.fitness:.3f}',
        flush=True,
    )

out.mkdir(parents=True, exist_ok=False)
np.savez_compressed(
    out / "reference.npz",
    ids=ids,
    scan_stamps_ns=scan_ns,
    oxts_stamps_ns=oxts_ns,
    T_reference_velo=poses,
    valid=valid,
    lidar_files=files,
)
(out / "overlap_report.json").write_text(json.dumps({
    "reference": "OXTS-derived lidar poses interpolated to scan timestamps",
    "interpolation": "linear translation and SLERP rotation; no extrapolation",
    "valid_frames": int(valid.sum()),
    "queries_with_history_within_5m": len(near),
    "voxel_size_m": 0.3,
    "correspondence_distance_m": 0.5,
    "note": "Reference-selected diagnostic pairs, not retrieval results.",
    "results": results,
}, indent=2))
print("\n已保存：", out)
