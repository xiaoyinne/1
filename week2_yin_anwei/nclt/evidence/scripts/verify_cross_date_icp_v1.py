from pathlib import Path
import json
import csv
import time
import hashlib
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

root = Path("/mnt/d/nclt_student3")
input_path = root / "retrieval_cross_date_v1/retrieval_only.json"
out = root / "geometry_cross_date_v1"

if out.exists():
    raise SystemExit(f"输出目录已存在，未覆盖：{out}")

items = json.loads(input_path.read_text(encoding="utf-8"))
accepted = sorted(
    [r for r in items if r["accepted"]],
    key=lambda r: r["query_index"],
)
if not accepted:
    raise SystemExit("没有通过SC阈值的候选")

out.mkdir()
started = time.perf_counter()
registration = o3d.pipelines.registration

dtype = np.dtype([
    ("x", "<u2"), ("y", "<u2"), ("z", "<u2"),
    ("intensity", "u1"), ("laser", "u1"),
])

def load_cloud(date, stamp):
    path = root / date / "velodyne_sync" / f"{stamp}.bin"
    assert path.stat().st_size % 8 == 0
    raw = np.fromfile(path, dtype=dtype)

    xyz = np.column_stack([
        raw["x"], raw["y"], raw["z"]
    ]).astype(np.float64)
    xyz = xyz * 0.005 - 100.0
    xyz *= np.array([1.0, -1.0, -1.0])

    radius = np.linalg.norm(xyz[:, :2], axis=1)
    xyz = xyz[
        np.isfinite(xyz).all(axis=1)
        & (radius > 1.0)
        & (radius < 80.0)
    ]
    assert len(xyz) > 0, f"空点云：{path}"

    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(xyz)
    return cloud

# 第一阶段：只运行ICP与几何检查，不加载参考位姿。
records = []
print("待验证候选数：", len(accepted), flush=True)

with (out / "geometry_only.jsonl").open(
    "x", encoding="utf-8"
) as log:
    for number, item in enumerate(accepted, start=1):
        source = load_cloud(
            "2012-02-05", int(item["query_stamp_us"])
        )
        target = load_cloud(
            "2012-01-08", int(item["best_db_stamp_us"])
        )

        yaw_deg = (
            int(item["shift_sectors"]) * 6.0 + 180.0
        ) % 360.0 - 180.0

        T = np.eye(4)
        T[:3, :3] = Rotation.from_euler(
            "z", yaw_deg, degrees=True
        ).as_matrix()

        for voxel, max_distance in [
            (1.0, 3.0),
            (0.5, 1.5),
            (0.3, 0.5),
        ]:
            src = source.voxel_down_sample(voxel)
            dst = target.voxel_down_sample(voxel)

            result = registration.registration_icp(
                src, dst, max_distance, T,
                registration.TransformationEstimationPointToPoint(),
                registration.ICPConvergenceCriteria(
                    max_iteration=60
                ),
            )
            T = result.transformation.copy()
            assert np.isfinite(T).all()

        # 最后一层点云的体素大小是0.3米。
        forward = registration.evaluate_registration(
            src, dst, 0.5, T
        )
        reverse = registration.evaluate_registration(
            dst, src, 0.5, np.linalg.inv(T)
        )

        forward_count = len(forward.correspondence_set)
        reverse_count = len(reverse.correspondence_set)

        passed = bool(
            forward_count > 0
            and reverse_count > 0
            and forward.fitness >= 0.5
            and reverse.fitness >= 0.5
            and forward.inlier_rmse <= 0.3
            and reverse.inlier_rmse <= 0.3
        )

        record = {
            "query_index": int(item["query_index"]),
            "db_index": int(item["best_db_index"]),
            "query_stamp_us": int(item["query_stamp_us"]),
            "db_stamp_us": int(item["best_db_stamp_us"]),
            "sc_distance": float(item["sc_distance"]),
            "initial_yaw_deg": float(yaw_deg),
            "forward_overlap": float(forward.fitness),
            "reverse_overlap": float(reverse.fitness),
            "forward_inlier_rmse_m": float(forward.inlier_rmse),
            "reverse_inlier_rmse_m": float(reverse.inlier_rmse),
            "forward_correspondences": forward_count,
            "reverse_correspondences": reverse_count,
            "geometry_passed": passed,
            "T_db_query": T.tolist(),
        }
        records.append(record)
        log.write(json.dumps(record) + "\n")
        log.flush()

        if number == 1 or number % 10 == 0 or number == len(accepted):
            passed_so_far = sum(
                r["geometry_passed"] for r in records
            )
            print(
                f"已验证 {number}/{len(accepted)} 对，"
                f"累计通过 {passed_so_far} 对，"
                f"用时 {time.perf_counter() - started:.1f} 秒",
                flush=True,
            )

# 第二阶段：全部ICP完成后，加载参考位姿进行评价。
def load_reference(date):
    path = (
        root / "reference_audit" /
        f"{date}_scan_reference.npz"
    )
    with np.load(path, allow_pickle=False) as data:
        stamps = data["stamps_us"].copy()
        poses = data["poses_xyz_rpy"].copy()
    assert np.isfinite(poses).all()
    return {
        int(stamp): pose
        for stamp, pose in zip(stamps, poses)
    }

db_reference = load_reference("2012-01-08")
query_reference = load_reference("2012-02-05")

def world_flu(pose):
    T = np.eye(4)
    T[:3, :3] = Rotation.from_euler(
        "xyz", pose[3:6]
    ).as_matrix()
    T[:3, 3] = pose[:3]
    return T @ np.diag([1.0, -1.0, -1.0, 1.0])

for record in records:
    world_db = world_flu(
        db_reference[record["db_stamp_us"]]
    )
    world_query = world_flu(
        query_reference[record["query_stamp_us"]]
    )
    reference_T = np.linalg.inv(world_db) @ world_query
    estimated_T = np.asarray(record["T_db_query"])

    reference_distance = np.linalg.norm(
        world_db[:3, 3] - world_query[:3, 3]
    )
    translation_error = np.linalg.norm(
        estimated_T[:3, 3] - reference_T[:3, 3]
    )
    rotation_error = np.degrees(
        Rotation.from_matrix(
            reference_T[:3, :3].T @ estimated_T[:3, :3]
        ).magnitude()
    )

    record.update({
        "reference_distance_m": float(reference_distance),
        "near_by_reference": bool(reference_distance <= 5.0),
        "translation_reference_error_m": float(translation_error),
        "rotation_reference_error_deg": float(rotation_error),
    })

# 保存所有结果，包括未通过的候选。
(out / "results.json").write_text(
    json.dumps(records, indent=2),
    encoding="utf-8",
)

csv_rows = [
    {k: v for k, v in r.items() if k != "T_db_query"}
    for r in records
]
with (out / "results.csv").open(
    "w", newline="", encoding="utf-8"
) as f:
    writer = csv.DictWriter(f, fieldnames=list(csv_rows[0]))
    writer.writeheader()
    writer.writerows(csv_rows)

def error_stats(group):
    if not group:
        return None
    result = {"count": len(group)}
    for field in [
        "translation_reference_error_m",
        "rotation_reference_error_deg",
    ]:
        values = np.array([r[field] for r in group])
        result[field] = {
            "median": float(np.median(values)),
            "p95": float(np.percentile(values, 95)),
            "max": float(values.max()),
        }
    return result

passed = [r for r in records if r["geometry_passed"]]
near = [r for r in records if r["near_by_reference"]]
far = [r for r in records if not r["near_by_reference"]]
passed_near = [r for r in passed if r["near_by_reference"]]
passed_far = [r for r in passed if not r["near_by_reference"]]

report = {
    "tested_candidates": len(records),
    "geometry_passed": len(passed),
    "geometry_rejected": len(records) - len(passed),
    "reference_near_before_geometry": len(near),
    "reference_far_before_geometry": len(far),
    "geometry_passed_reference_near": len(passed_near),
    "geometry_passed_reference_far": len(passed_far),
    "geometry_rejected_reference_far": len(far) - len(passed_far),
    "passed_all_error_stats": error_stats(passed),
    "passed_reference_near_error_stats": error_stats(passed_near),
    "passed_reference_far_error_stats": error_stats(passed_far),
    "initialization": "SC yaw; zero translation; no reference pose",
    "transform_direction": "query FLU body to database FLU body",
    "geometry_rule": "both overlap >=0.5; both inlier RMSE <=0.3m; nonempty correspondences",
    "evaluation_voxel_m": 0.3,
    "evaluation_correspondence_distance_m": 0.5,
    "reference_proximity_threshold_m": 5.0,
    "elapsed_s": round(time.perf_counter() - started, 2),
    "open3d_version": o3d.__version__,
    "retrieval_sha256": hashlib.sha256(
        input_path.read_bytes()
    ).hexdigest(),
    "script_sha256": hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest(),
    "note": (
        "Reference proximity and geometric screening are separate diagnostics. "
        "A geometrically accepted candidate is not automatically correct. "
        "Relative pose reference errors are not trajectory ATE."
    ),
}

(out / "report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)

print("\n结果目录：", out)
print(json.dumps(report, indent=2))

print("\n位置超过5米、但仍通过几何筛选的候选：")
for r in passed_far:
    print(
        f"查询 {r['query_index']} -> 历史 {r['db_index']}，"
        f"位置距离={r['reference_distance_m']:.2f}m，"
        f"平移参考误差={r['translation_reference_error_m']:.3f}m，"
        f"旋转参考误差={r['rotation_reference_error_deg']:.3f}度"
    )
