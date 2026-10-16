from pathlib import Path
import json
import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.spatial.transform import Rotation

root = Path("/mnt/d/nclt_student3")
out = root / "demo_cases_v1"
if out.exists():
    raise SystemExit(f"输出目录已存在，未覆盖：{out}")

records = json.loads(
    (root / "geometry_cross_date_v1/results.json")
    .read_text(encoding="utf-8")
)
lookup = {int(r["query_index"]): r for r in records}

# 明确选取的诊断案例，不代表总体性能。
selected_queries = [73, 1294]

dtype = np.dtype([
    ("x", "<u2"), ("y", "<u2"), ("z", "<u2"),
    ("intensity", "u1"), ("laser", "u1"),
])

def read_points(date, stamp):
    path = root / date / "velodyne_sync" / f"{stamp}.bin"
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

    # 仅为显示抽取最多8000个点，不改变实验数据。
    if len(xyz) > 8000:
        rng = np.random.default_rng(42)
        indices = np.sort(
            rng.choice(len(xyz), 8000, replace=False)
        )
        xyz = xyz[indices]
    return xyz

def load_reference(date):
    path = (
        root / "reference_audit" /
        f"{date}_scan_reference.npz"
    )
    with np.load(path, allow_pickle=False) as data:
        return {
            int(t): pose.copy()
            for t, pose in zip(
                data["stamps_us"],
                data["poses_xyz_rpy"],
            )
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

def transform(points, T):
    return points @ T[:3, :3].T + T[:3, 3]

fig, axes = plt.subplots(2, 3, figsize=(17, 11))
case_report = []

for row_number, q in enumerate(selected_queries):
    r = lookup[q]

    query = read_points("2012-02-05", r["query_stamp_us"])
    history = read_points("2012-01-08", r["db_stamp_us"])

    initial_T = np.eye(4)
    initial_T[:3, :3] = Rotation.from_euler(
        "z", r["initial_yaw_deg"], degrees=True
    ).as_matrix()

    icp_T = np.asarray(r["T_db_query"])

    world_db = world_flu(
        db_reference[r["db_stamp_us"]]
    )
    world_query = world_flu(
        query_reference[r["query_stamp_us"]]
    )
    reference_T = np.linalg.inv(world_db) @ world_query

    transforms = [initial_T, icp_T, reference_T]
    aligned = [transform(query, T) for T in transforms]

    # 同一行三张图使用相同范围，避免缩放造成视觉误判。
    all_xy = np.vstack([history] + aligned)[:, :2]
    lower = all_xy.min(axis=0)
    upper = all_xy.max(axis=0)
    center = (lower + upper) / 2
    half_width = max(float((upper - lower).max()) / 2, 1.0) * 1.05

    titles = [
        "SC initialization",
        "ICP alignment",
        "Reference alignment (evaluation only)",
    ]

    for column, (points, title) in enumerate(zip(aligned, titles)):
        ax = axes[row_number, column]

        ax.scatter(
            history[:, 0], history[:, 1],
            s=1, alpha=0.45, color="#167ca5",
            label="History",
        )
        ax.scatter(
            points[:, 0], points[:, 1],
            s=1, alpha=0.45, color="#d46c34",
            label="Transformed query",
        )

        ax.set_xlim(center[0] - half_width, center[0] + half_width)
        ax.set_ylim(center[1] - half_width, center[1] + half_width)
        ax.set_aspect("equal")
        ax.set_xlabel("History-frame X (m)")
        ax.set_ylabel("History-frame Y (m)")
        ax.grid(alpha=0.2)
        ax.set_title(
            f"Query {q} -> history {r['db_index']}\n{title}",
            fontsize=11,
        )

        if row_number == 0 and column == 0:
            ax.legend(markerscale=4, fontsize=9)

        if column == 1:
            ax.text(
                0.03, 0.03,
                f"Overlap: {r['forward_overlap']:.3f} / "
                f"{r['reverse_overlap']:.3f}\n"
                f"Reference error: "
                f"{r['translation_reference_error_m']:.3f} m, "
                f"{r['rotation_reference_error_deg']:.3f} deg",
                transform=ax.transAxes,
                fontsize=9,
                bbox=dict(facecolor="white", alpha=0.9, edgecolor="none"),
            )

    case_report.append({
        "query_index": q,
        "db_index": r["db_index"],
        "geometry_passed": r["geometry_passed"],
        "translation_reference_error_m":
            r["translation_reference_error_m"],
        "rotation_reference_error_deg":
            r["rotation_reference_error_deg"],
    })

fig.suptitle(
    "NCLT cross-date alignment: a low-error case and a false acceptance",
    fontsize=16,
)
fig.text(
    0.5, 0.015,
    "XY projections; display subsampling only. "
    "Reference poses were not used to initialize ICP.",
    ha="center", fontsize=10,
)
fig.tight_layout(rect=(0, 0.045, 1, 0.95))

out.mkdir()
figure_path = out / "alignment_cases.png"
fig.savefig(figure_path, dpi=180)
plt.close(fig)

(out / "cases.json").write_text(
    json.dumps(case_report, indent=2),
    encoding="utf-8",
)

print("图片已保存：", figure_path)
print("第一行：查询73，配准参考误差较小的对照。")
print("第二行：查询1294，几何筛选误接受的案例。")
print("三列依次为：SC初始对齐、ICP配准、参考位姿对齐。")
print("这是XY投影图，三维误差仍以数值评价为准。")
