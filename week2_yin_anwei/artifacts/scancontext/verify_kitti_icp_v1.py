from pathlib import Path
import csv
import json
import hashlib
import time
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

base = Path("/home/yaw/fastlio_week2/scancontext/runs")
retrieval = base / "kitti0020_retrieval_v1/queries.csv"
reference_path = base / "kitti0020_reference_v2/reference.npz"
out = base / "kitti0020_geometry_v1"
if out.exists():
    raise RuntimeError(f"输出目录已存在，未覆盖：{out}")

with retrieval.open() as f:
    rows = [
        r for r in csv.DictReader(f)
        if r["accepted"].lower() == "true"
    ]
assert rows, "没有通过描述子阈值的候选"

reference = np.load(reference_path, allow_pickle=False)
lookup = {int(v): i for i, v in enumerate(reference["ids"])}
cache = {}

def cloud(frame_id):
    if frame_id not in cache:
        i = lookup[frame_id]
        raw = np.fromfile(
            str(reference["lidar_files"][i]), dtype="<f4"
        ).reshape(-1, 4)
        p = raw[:, :3]
        radius = np.linalg.norm(p[:, :2], axis=1)
        p = p[
            np.isfinite(p).all(axis=1)
            & (radius > 1) & (radius < 80)
        ]
        pc = o3d.geometry.PointCloud()
        pc.points = o3d.utility.Vector3dVector(p)
        cache[frame_id] = pc
    return cache[frame_id]

results = []
transforms = []
start = time.perf_counter()

for number, row in enumerate(rows, 1):
    q = int(row["query_id"])
    c = int(row["candidate_id"])
    source, target = cloud(c), cloud(q)

    # 候选点云 -> 查询点云；初值只用 SC 扇区偏移。
    yaw = np.deg2rad(int(row["candidate_sector_shift"]) * 6.0)
    T = np.eye(4)
    T[:3, :3] = Rotation.from_euler("z", yaw).as_matrix()

    for voxel, max_distance in ((1.0, 3.0), (0.5, 1.5), (0.3, 0.5)):
        source_down = source.voxel_down_sample(voxel)
        target_down = target.voxel_down_sample(voxel)
        registration = o3d.pipelines.registration.registration_icp(
            source_down, target_down, max_distance, T,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(),
            o3d.pipelines.registration.ICPConvergenceCriteria(
                max_iteration=60
            ),
        )
        T = registration.transformation.copy()

    assert np.isfinite(T).all(), "ICP 变换包含无效数值"
    forward = o3d.pipelines.registration.evaluate_registration(
        source_down, target_down, 0.5, T
    )
    reverse = o3d.pipelines.registration.evaluate_registration(
        target_down, source_down, 0.5, np.linalg.inv(T)
    )
    geometry_pass = (
        forward.fitness >= 0.5 and reverse.fitness >= 0.5
        and forward.inlier_rmse <= 0.3
        and reverse.inlier_rmse <= 0.3
    )

    # 配准完成后，才使用参考相对位姿计算误差。
    T_reference = (
        np.linalg.inv(reference["T_reference_velo"][lookup[q]])
        @ reference["T_reference_velo"][lookup[c]]
    )
    delta = np.linalg.inv(T_reference) @ T
    translation_error = float(np.linalg.norm(delta[:3, 3]))
    rotation_error = float(np.rad2deg(
        Rotation.from_matrix(delta[:3, :3]).magnitude()
    ))

    result = {
        "query_id": q,
        "candidate_id": c,
        "sc_distance": float(row["sc_distance"]),
        "forward_overlap": float(forward.fitness),
        "reverse_overlap": float(reverse.fitness),
        "forward_inlier_rmse_m": float(forward.inlier_rmse),
        "reverse_inlier_rmse_m": float(reverse.inlier_rmse),
        "geometry_pass": bool(geometry_pass),
        "reference_translation_error_m": translation_error,
        "reference_rotation_error_deg": rotation_error,
    }
    results.append(result)
    transforms.append(T)
    print(
        f"[{number}/{len(rows)}] {q}->{c}："
        f"重叠={forward.fitness:.3f}/{reverse.fitness:.3f}，"
        f"RMSE={forward.inlier_rmse:.3f}/{reverse.inlier_rmse:.3f}m，"
        f"参考误差={translation_error:.3f}m/{rotation_error:.2f}度，"
        f"几何筛选={'通过' if geometry_pass else '未通过'}",
        flush=True,
    )

passed = [r for r in results if r["geometry_pass"]]
report = {
    "tested_candidates": len(results),
    "geometry_passed": len(passed),
    "initialization": "SC yaw only; zero translation; no reference pose",
    "geometry_rule": "both overlap >= 0.5 and both inlier RMSE <= 0.3m",
    "evaluation_distance_m": 0.5,
    "reference_note": "Interpolated OXTS reference, not exact ground truth",
    "elapsed_s": round(time.perf_counter() - start, 3),
    "retrieval_sha256": hashlib.sha256(retrieval.read_bytes()).hexdigest(),
    "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
if passed:
    report["passed_reference_translation_error_median_m"] = float(
        np.median([r["reference_translation_error_m"] for r in passed])
    )
    report["passed_reference_translation_error_max_m"] = max(
        r["reference_translation_error_m"] for r in passed
    )
    report["passed_reference_rotation_error_median_deg"] = float(
        np.median([r["reference_rotation_error_deg"] for r in passed])
    )
    report["passed_reference_rotation_error_max_deg"] = max(
        r["reference_rotation_error_deg"] for r in passed
    )

out.mkdir(parents=True, exist_ok=False)
with (out / "results.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(results[0]))
    writer.writeheader()
    writer.writerows(results)
np.savez_compressed(
    out / "transforms.npz",
    query_ids=np.array([r["query_id"] for r in results]),
    candidate_ids=np.array([r["candidate_id"] for r in results]),
    T_query_candidate=np.array(transforms),
)
(out / "report.json").write_text(json.dumps(report, indent=2))
print("\n结果目录：", out)
print(json.dumps(report, indent=2))
