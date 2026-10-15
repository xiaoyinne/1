from pathlib import Path
import sys
import csv
import json
import hashlib
import time
import numpy as np

base = Path("/home/yaw/fastlio_week2/scancontext")
repo = base / "vendor/PyICP-SLAM-master"
sys.path.insert(0, str(repo))
from utils.ScanContextManager import distance_sc

descriptor_path = base / "runs/kitti0020_descriptors_v1/descriptors.npz"
reference_path = base / "runs/kitti0020_reference_v2/reference.npz"
out = base / "runs/kitti0020_retrieval_v1"
if out.exists():
    raise RuntimeError(f"输出目录已存在，未覆盖：{out}")

data = np.load(descriptor_path, allow_pickle=False)
ids = data["ids"]
stamps = data["stamps_ns"]
sc = data["descriptors"]
rk = data["ring_keys"]
valid = data["valid"]

queries = []
candidates = []
no_history = 0
no_finite_match = 0
start = time.perf_counter()

# 检索阶段不读取参考位置。
for q in np.flatnonzero(valid):
    history = np.flatnonzero(
        valid & ((stamps[q] - stamps) >= 30_000_000_000)
    )
    if not len(history):
        no_history += 1
        continue

    ring_distances = np.linalg.norm(rk[history] - rk[q], axis=1)
    chosen = np.argsort(ring_distances, kind="stable")[:10]
    ranked = []

    for k in chosen:
        c = int(history[k])
        distance, shift = distance_sc(sc[c], sc[q])
        if not np.isfinite(distance):
            continue
        ranked.append({
            "query_id": int(ids[q]),
            "candidate_id": int(ids[c]),
            "time_gap_s": float((stamps[q] - stamps[c]) / 1e9),
            "ring_distance": float(ring_distances[k]),
            "sc_distance": float(distance),
            "candidate_sector_shift": int(shift) % 60,
        })

    ranked.sort(key=lambda r: (r["sc_distance"], r["candidate_id"]))
    if not ranked:
        no_finite_match += 1
        continue

    for rank, row in enumerate(ranked, 1):
        candidates.append(dict(row, rank=rank))
    queries.append(dict(
        ranked[0],
        accepted=ranked[0]["sc_distance"] < 0.15,
        history_count=len(history),
    ))
    if len(queries) % 20 == 0:
        print(f"已检索 {len(queries)} 个查询帧", flush=True)

# 检索结束后，才使用参考位置做诊断。
reference = np.load(reference_path, allow_pickle=False)
reference_lookup = {
    int(frame_id): i for i, frame_id in enumerate(reference["ids"])
}
positions = {
    int(frame_id): reference["T_reference_velo"][
        reference_lookup[int(frame_id)], :3, 3
    ]
    for frame_id in ids
}
index_lookup = {int(frame_id): i for i, frame_id in enumerate(ids)}

for row in candidates:
    row["reference_distance_m"] = float(np.linalg.norm(
        positions[row["query_id"]] - positions[row["candidate_id"]]
    ))

shortlist_near = {}
for row in candidates:
    qid = row["query_id"]
    shortlist_near[qid] = (
        shortlist_near.get(qid, False)
        or row["reference_distance_m"] <= 5.0
    )

for row in queries:
    qid = row["query_id"]
    q = index_lookup[qid]
    history = np.flatnonzero(
        valid & ((stamps[q] - stamps) >= 30_000_000_000)
    )
    row["reference_distance_m"] = float(np.linalg.norm(
        positions[qid] - positions[row["candidate_id"]]
    ))
    row["nearest_history_reference_m"] = min(
        float(np.linalg.norm(positions[qid] - positions[int(ids[c])]))
        for c in history
    )
    row["near_by_reference"] = row["reference_distance_m"] <= 5.0
    row["shortlist_contains_near"] = shortlist_near[qid]

accepted = [r for r in queries if r["accepted"]]
report = {
    "mode": "same-sequence historical retrieval",
    "exclusion_seconds": 30,
    "max_candidates": 10,
    "acceptance_distance_threshold": 0.15,
    "reference_proximity_threshold_m": 5.0,
    "queries_without_history": no_history,
    "queries_without_finite_match": no_finite_match,
    "queried_frames": len(queries),
    "queries_with_history_within_5m": sum(
        r["nearest_history_reference_m"] <= 5 for r in queries
    ),
    "queries_with_near_in_top10": sum(
        r["shortlist_contains_near"] for r in queries
    ),
    "top1_near_by_reference": sum(r["near_by_reference"] for r in queries),
    "accepted_candidates": len(accepted),
    "accepted_near_by_reference": sum(
        r["near_by_reference"] for r in accepted
    ),
    "accepted_far_by_reference": sum(
        not r["near_by_reference"] for r in accepted
    ),
    "elapsed_s": round(time.perf_counter() - start, 3),
    "note": "Reference proximity is diagnostic; geometry is not yet verified.",
    "descriptor_sha256": hashlib.sha256(descriptor_path.read_bytes()).hexdigest(),
    "module_sha256": hashlib.sha256(
        (repo / "utils/ScanContextManager.py").read_bytes()
    ).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}

out.mkdir(parents=True, exist_ok=False)
for filename, rows in (("queries.csv", queries), ("candidates.csv", candidates)):
    if rows:
        with (out / filename).open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
(out / "report.json").write_text(json.dumps(report, indent=2))

print("\n结果目录：", out)
print(json.dumps(report, indent=2))
for near, title in (
    (True, "通过阈值且参考位置接近"),
    (False, "通过阈值但参考位置较远"),
):
    print(f"\n{title}，最多 5 条：")
    subset = [r for r in accepted if r["near_by_reference"] == near]
    for r in sorted(subset, key=lambda r: r["sc_distance"])[:5]:
        print(
            f'{r["query_id"]}->{r["candidate_id"]}：'
            f'SC距离={r["sc_distance"]:.4f}，'
            f'参考距离={r["reference_distance_m"]:.2f}m，'
            f'时间差={r["time_gap_s"]:.1f}s'
        )
