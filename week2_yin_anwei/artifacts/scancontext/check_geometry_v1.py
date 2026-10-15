from pathlib import Path
import csv
import json
import time
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

root = Path(
    "/home/yaw/fastlio_week2/scancontext/runs/"
    "raw_20261013_193630/keyframes_v1"
)
out = root / "geometry_v1"
out.mkdir(exist_ok=False)

with (root / "index.csv").open() as f:
    frames = {int(r["id"]): r for r in csv.DictReader(f)}
with (root / "retrieval_all_v1/queries.csv").open() as f:
    queries = {int(r["query_id"]): r for r in csv.DictReader(f)}

def load_cloud(frame_id):
    cloud = o3d.io.read_point_cloud(str(root / frames[frame_id]["pcd"]))
    points = np.asarray(cloud.points)
    radius = np.linalg.norm(points[:, :2], axis=1)
    keep = np.isfinite(points).all(axis=1) & (radius > 0) & (radius < 25)
    result = o3d.geometry.PointCloud()
    result.points = o3d.utility.Vector3dVector(points[keep])
    return result

def pose(frame_id):
    row = frames[frame_id]
    transform = np.eye(4)
    transform[:3, :3] = Rotation.from_quat(
        [float(row[k]) for k in ("qx", "qy", "qz", "qw")]
    ).as_matrix()
    transform[:3, 3] = [float(row[k]) for k in ("x", "y", "z")]
    return transform

results = []
for query_id in [79, 80, 56, 142]:
    row = queries[query_id]
    candidate_id = int(row["candidate_id"])
    source = load_cloud(candidate_id)
    target = load_cloud(query_id)

    # Positive column shift rotates candidate toward query.
    yaw_deg = int(row["candidate_sector_shift"]) * 6.0
    transform = np.eye(4)
    transform[:3, :3] = Rotation.from_euler(
        "z", yaw_deg, degrees=True
    ).as_matrix()

    started = time.perf_counter()
    for voxel, correspondence in [(1.0, 3.0), (0.5, 1.5), (0.2, 0.5)]:
        registration = o3d.pipelines.registration.registration_icp(
            source.voxel_down_sample(voxel),
            target.voxel_down_sample(voxel),
            correspondence,
            transform,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50),
        )
        transform = registration.transformation

    a = source.voxel_down_sample(0.2)
    b = target.voxel_down_sample(0.2)
    forward = o3d.pipelines.registration.evaluate_registration(
        a, b, 0.3, transform
    )
    reverse = o3d.pipelines.registration.evaluate_registration(
        b, a, 0.3, np.linalg.inv(transform)
    )

    # Odometry is used only after registration, as a diagnostic reference.
    reference = np.linalg.inv(pose(query_id)) @ pose(candidate_id)
    delta = np.linalg.inv(reference) @ transform
    rotation_difference = np.degrees(
        Rotation.from_matrix(delta[:3, :3]).magnitude()
    )

    result = {
        "query_id": query_id,
        "candidate_id": candidate_id,
        "sc_distance": float(row["sc_distance"]),
        "initial_yaw_deg": yaw_deg,
        "initial_translation": [0, 0, 0],
        "forward_fitness": float(forward.fitness),
        "reverse_fitness": float(reverse.fitness),
        "forward_inliers": len(forward.correspondence_set),
        "reverse_inliers": len(reverse.correspondence_set),
        "forward_inlier_rmse_m": float(forward.inlier_rmse),
        "reverse_inlier_rmse_m": float(reverse.inlier_rmse),
        "translation_difference_from_odom_m": float(np.linalg.norm(delta[:3, 3])),
        "rotation_difference_from_odom_deg": float(rotation_difference),
        "T_query_candidate": transform.tolist(),
        "elapsed_s": round(time.perf_counter() - started, 3),
    }
    results.append(result)

    aligned = source.voxel_down_sample(0.2)
    aligned.transform(transform)
    aligned.paint_uniform_color([1.0, 0.4, 0.0])
    display_target = target.voxel_down_sample(0.2)
    display_target.paint_uniform_color([0.1, 0.4, 1.0])
    path = out / f"query_{query_id}_candidate_{candidate_id}.ply"
    assert o3d.io.write_point_cloud(str(path), aligned + display_target)

    print(f"\n查询 {query_id} -> 历史 {candidate_id}", flush=True)
    print(
        f"双向重叠比例：{forward.fitness:.3f} / {reverse.fitness:.3f}\n"
        f"双向内点 RMSE：{forward.inlier_rmse:.3f} / "
        f"{reverse.inlier_rmse:.3f} m\n"
        f"与里程计相对变换的差异："
        f"{result['translation_difference_from_odom_m']:.3f} m，"
        f"{rotation_difference:.2f} 度",
        flush=True,
    )

report = {
    "purpose": "four diagnostic cases; not a full benchmark",
    "cloud_radius_m": 25,
    "final_voxel_m": 0.2,
    "evaluation_correspondence_m": 0.3,
    "initialization": "Scan Context candidate-to-query yaw, zero translation",
    "results": results,
}
(out / "report.json").write_text(json.dumps(report, indent=2))
print("\n结果目录：", out)
