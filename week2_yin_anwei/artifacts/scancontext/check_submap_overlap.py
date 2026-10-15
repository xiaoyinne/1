from pathlib import Path
import csv
import json
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

root = Path(
    "/home/yaw/fastlio_week2/scancontext/runs/"
    "raw_20261013_193630/keyframes_v1"
)
with (root / "index.csv").open() as f:
    rows = list(csv.DictReader(f))

times = np.array([int(r["stamp_ns"]) for r in rows], dtype=np.int64)
lookup = {int(r["id"]): i for i, r in enumerate(rows)}
poses = []
for r in rows:
    T = np.eye(4)
    T[:3, :3] = Rotation.from_quat(
        [float(r[k]) for k in ("qx", "qy", "qz", "qw")]
    ).as_matrix()
    T[:3, 3] = [float(r[k]) for k in ("x", "y", "z")]
    poses.append(T)

previous = json.loads(
    (root / "geometry_v1/all_nearby_overlap.json").read_text()
)["results"]

clouds = {}
submaps = {}

def read_points(i):
    if i not in clouds:
        p = np.asarray(o3d.io.read_point_cloud(
            str(root / rows[i]["pcd"])
        ).points)
        radius = np.linalg.norm(p[:, :2], axis=1)
        clouds[i] = p[
            np.isfinite(p).all(axis=1) & (radius > 0) & (radius < 25)
        ].copy()
    return clouds[i]

def submap(i):
    if i not in submaps:
        members = np.flatnonzero(
            (times <= times[i]) &
            ((times[i] - times) <= 5_000_000_000)
        )
        transformed = []
        anchor_inverse = np.linalg.inv(poses[i])
        for j in members:
            p = read_points(int(j))
            T = anchor_inverse @ poses[int(j)]
            transformed.append(p @ T[:3, :3].T + T[:3, 3])
        pc = o3d.geometry.PointCloud()
        pc.points = o3d.utility.Vector3dVector(
            np.concatenate(transformed, axis=0)
        )
        submaps[i] = pc.voxel_down_sample(0.2)
    return submaps[i]

results = []
for n, old in enumerate(previous, 1):
    q = lookup[old["query_id"]]
    c = lookup[old["candidate_id"]]
    source, target = submap(c), submap(q)
    T = np.linalg.inv(poses[q]) @ poses[c]
    forward = o3d.pipelines.registration.evaluate_registration(
        source, target, 0.3, T
    )
    reverse = o3d.pipelines.registration.evaluate_registration(
        target, source, 0.3, np.linalg.inv(T)
    )
    results.append({
        "query_id": old["query_id"],
        "candidate_id": old["candidate_id"],
        "single_frame_min_overlap": old["min_bidirectional_fitness"],
        "submap_forward": float(forward.fitness),
        "submap_reverse": float(reverse.fitness),
        "submap_min_overlap": float(min(forward.fitness, reverse.fitness)),
        "candidate_points": len(source.points),
        "query_points": len(target.points),
    })
    if n % 20 == 0:
        print(f"已检查 {n}/{len(previous)} 对", flush=True)

results.sort(key=lambda r: r["submap_min_overlap"], reverse=True)
print("\n5 秒子地图重叠最高的 10 对：")
for r in results[:10]:
    print(
        f'{r["query_id"]}->{r["candidate_id"]}：'
        f'单帧较小值={r["single_frame_min_overlap"]:.3f}，'
        f'子地图双向={r["submap_forward"]:.3f}/'
        f'{r["submap_reverse"]:.3f}，'
        f'点数={r["candidate_points"]}/{r["query_points"]}'
    )

print("\n重叠分布（不是回环验收标准）：")
for threshold in (0.05, 0.10, 0.20, 0.30):
    selected = [r for r in results if r["submap_min_overlap"] >= threshold]
    print(
        f"双向均 >= {threshold:.2f}：{len(selected)} 对，"
        f'{len({r["query_id"] for r in selected})} 个查询帧'
    )

path = root / "geometry_v1/submap_overlap_5s.json"
path.write_text(json.dumps({
    "purpose": "Odometry-based diagnostic; not Scan Context retrieval",
    "past_window_seconds": 5,
    "voxel_size_m": 0.2,
    "correspondence_distance_m": 0.3,
    "results": results,
}, indent=2))
print("\n报告：", path)
