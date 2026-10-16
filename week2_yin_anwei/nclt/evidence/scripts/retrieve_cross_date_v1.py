from pathlib import Path
import sys
import csv
import json
import hashlib
import time
import numpy as np

root = Path("/mnt/d/nclt_student3")
repo = Path(
    "/home/yaw/fastlio_week2/scancontext/vendor/PyICP-SLAM-master"
)
sys.path.insert(0, str(repo))
from utils.ScanContextManager import distance_sc

out = root / "retrieval_cross_date_v1"
if out.exists():
    raise SystemExit(f"结果目录已存在，未覆盖：{out}")

def load_descriptors(date):
    folder = root / "descriptors_v1" / date
    with np.load(folder / "descriptors.npz", allow_pickle=False) as data:
        result = {
            "stamps": data["stamps_us"].copy(),
            "sc": data["descriptors"].copy(),
            "rk": data["ring_keys"].copy(),
        }
    result["report"] = json.loads(
        (folder / "report.json").read_text(encoding="utf-8")
    )
    return result

db = load_descriptors("2012-01-08")
query = load_descriptors("2012-02-05")

for key in [
    "input_frame",
    "horizontal_range_m",
    "height_offset_m",
    "upstream_max_points_per_cell",
    "module_sha256",
]:
    assert db["report"][key] == query["report"][key], key

module_path = repo / "utils/ScanContextManager.py"
module_hash = hashlib.sha256(module_path.read_bytes()).hexdigest()
assert module_hash == db["report"]["module_sha256"], "SC源码版本已改变"

for data in [db, query]:
    n = len(data["stamps"])
    assert data["sc"].shape == (n, 20, 60)
    assert data["rk"].shape == (n, 20)
    assert np.isfinite(data["sc"]).all()
    assert np.isfinite(data["rk"]).all()

candidate_count = 10
sc_threshold = 0.15
near_threshold = 5.0

# 第一阶段只读描述子，完全不读取参考位置。
out.mkdir()
started = time.perf_counter()
retrievals = []

print("开始跨日期检索。参考位置不参与候选选择。", flush=True)

for q in range(len(query["stamps"])):
    ring_distances = np.linalg.norm(
        db["rk"] - query["rk"][q], axis=1
    )
    candidates = np.argsort(
        ring_distances, kind="stable"
    )[:candidate_count]

    scores = []
    for index in candidates:
        distance, shift = distance_sc(
            query["sc"][q].copy(),
            db["sc"][index].copy(),
        )
        assert np.isfinite(distance), f"查询{q}的SC距离异常"
        scores.append((float(distance), int(index), int(shift) % 60))

    # 相同分数保留粗筛顺序。
    scores.sort(key=lambda item: item[0])
    distance, best, shift = scores[0]

    retrievals.append({
        "query_index": q,
        "query_stamp_us": int(query["stamps"][q]),
        "best_db_index": best,
        "best_db_stamp_us": int(db["stamps"][best]),
        "sc_distance": distance,
        "shift_sectors": shift,
        "accepted": bool(distance < sc_threshold),
        "candidate_indices": [int(i) for i in candidates],
    })

    if (q + 1) % 50 == 0 or q + 1 == len(query["stamps"]):
        print(
            f"已检索 {q + 1}/{len(query['stamps'])} 帧，"
            f"用时 {time.perf_counter() - started:.1f} 秒",
            flush=True,
        )

# 先保存纯检索结果，再加载参考位置。
(out / "retrieval_only.json").write_text(
    json.dumps(retrievals, indent=2),
    encoding="utf-8",
)

def load_positions(date, stamps):
    path = root / "reference_audit" / f"{date}_scan_reference.npz"
    with np.load(path, allow_pickle=False) as data:
        ref_stamps = data["stamps_us"].copy()
        positions = data["poses_xyz_rpy"][:, :3].copy()

    lookup = {int(t): i for i, t in enumerate(ref_stamps)}
    assert all(int(t) in lookup for t in stamps)
    result = np.array([positions[lookup[int(t)]] for t in stamps])
    assert np.isfinite(result).all()
    return result

# 第二阶段：参考位置仅用于事后评价。
db_positions = load_positions("2012-01-08", db["stamps"])
query_positions = load_positions("2012-02-05", query["stamps"])

rows = []
for item in retrievals:
    q = item["query_index"]
    distances = np.linalg.norm(
        db_positions - query_positions[q], axis=1
    )
    candidates = np.array(item["candidate_indices"], dtype=int)

    row = {k: v for k, v in item.items() if k != "candidate_indices"}
    row.update({
        "nearest_reference_distance_m": float(distances.min()),
        "has_near_history": bool(distances.min() <= near_threshold),
        "near_in_top10": bool(
            np.any(distances[candidates] <= near_threshold)
        ),
        "best_reference_distance_m": float(
            distances[item["best_db_index"]]
        ),
        "best_is_near": bool(
            distances[item["best_db_index"]] <= near_threshold
        ),
    })
    rows.append(row)

with (out / "results.csv").open(
    "w", newline="", encoding="utf-8"
) as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

def count(predicate):
    return sum(bool(predicate(row)) for row in rows)

has_near = count(lambda r: r["has_near_history"])
without_near = len(rows) - has_near
accepted = count(lambda r: r["accepted"])
accepted_near = count(lambda r: r["accepted"] and r["best_is_near"])
accepted_far = count(lambda r: r["accepted"] and not r["best_is_near"])

report = {
    "database_date": "2012-01-08",
    "query_date": "2012-02-05",
    "database_frames": len(db["stamps"]),
    "query_frames": len(rows),
    "max_candidates": candidate_count,
    "sc_threshold": sc_threshold,
    "reference_proximity_threshold_m": near_threshold,
    "queries_with_near_history": has_near,
    "queries_without_near_history": without_near,
    "queries_with_near_in_top10": count(lambda r: r["near_in_top10"]),
    "top1_near_by_reference": count(lambda r: r["best_is_near"]),
    "accepted_candidates": accepted,
    "accepted_near_by_reference": accepted_near,
    "accepted_far_by_reference": accepted_far,
    "accepted_when_no_near_history": count(
        lambda r: r["accepted"] and not r["has_near_history"]
    ),
    "rejected_when_no_near_history": count(
        lambda r: not r["accepted"] and not r["has_near_history"]
    ),
    "accepted_near_fraction_of_near_queries": (
        accepted_near / has_near if has_near else None
    ),
    "near_fraction_of_accepted_candidates": (
        accepted_near / accepted if accepted else None
    ),
    "elapsed_s": round(time.perf_counter() - started, 2),
    "module_sha256": module_hash,
    "script_sha256": hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest(),
    "note": (
        "Reference proximity is an evaluation proxy. "
        "No ICP geometry verification has been performed. "
        "Reference positions are loaded only after retrieval."
    ),
}

(out / "report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)

print("\n结果目录：", out)
print(json.dumps(report, indent=2))

print("\n通过SC阈值的前5个查询（按查询编号）：")
for row in [r for r in rows if r["accepted"]][:5]:
    print(
        f"查询 {row['query_index']} -> 历史 {row['best_db_index']}，"
        f"SC距离={row['sc_distance']:.4f}，"
        f"参考位置距离={row['best_reference_distance_m']:.2f}米"
    )
