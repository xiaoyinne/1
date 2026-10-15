from pathlib import Path
import sys
import csv
import json
import hashlib
import time
import numpy as np

base = Path("/home/yaw/fastlio_week2/scancontext")
root = base / "runs/raw_20261013_193630/keyframes_v1"
repo = base / "vendor/PyICP-SLAM-master"
sys.path.insert(0, str(repo))
from utils.ScanContextManager import distance_sc

source = repo / "utils/ScanContextManager.py"
manifest = json.loads((root / "descriptors_v2/manifest.json").read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["module_sha256"]
assert hashlib.sha256((root / "index.csv").read_bytes()).hexdigest() == manifest["index_sha256"]

with (root / "index.csv").open() as f:
    rows = list(csv.DictReader(f))
data = np.load(root / "descriptors_v2/descriptors.npz", allow_pickle=False)
ids = data["ids"]
stamps = data["stamps_ns"]
sc = data["descriptors"]
rk = data["ring_keys"]
valid = data["valid"]

assert list(ids) == [int(r["id"]) for r in rows]
xyz = np.array([[float(r[k]) for k in ("x", "y", "z")] for r in rows])
out = root / "retrieval_v2"
out.mkdir(exist_ok=False)

results = []
all_candidates = []
no_history = 0
no_finite_match = 0
started = time.perf_counter()

for q in range(len(ids)):
    if not valid[q]:
        continue
    history = np.flatnonzero(
        valid & ((stamps[q] - stamps) >= 30_000_000_000)
    )
    if len(history) == 0:
        no_history += 1
        continue

    # Candidate selection uses descriptors only.
    ring_dist = np.linalg.norm(rk[history] - rk[q], axis=1)
    chosen = np.argsort(ring_dist, kind="stable")[:10]
    candidates = history[chosen]
    matches = []

    for c, ring_d in zip(candidates, ring_dist[chosen]):
        distance, shift = distance_sc(sc[c], sc[q])
        if not np.isfinite(distance):
            continue
        shift = int(shift) % sc.shape[2]
        shifted = np.roll(sc[c], shift, axis=1)
        shared = int(np.sum(
            (np.linalg.norm(shifted, axis=0) > 0)
            & (np.linalg.norm(sc[q], axis=0) > 0)
        ))
        record = {
            "query_id": int(ids[q]),
            "candidate_id": int(ids[c]),
            "time_gap_s": float((stamps[q] - stamps[c]) / 1e9),
            "ring_distance": float(ring_d),
            "sc_distance": float(distance),
            "candidate_sector_shift": shift,
            "shared_sectors": shared,
            "odom_separation_m": float(np.linalg.norm(xyz[q] - xyz[c])),
        }
        matches.append(record)

    matches.sort(key=lambda r: (r["sc_distance"], r["candidate_id"]))
    for rank, record in enumerate(matches, 1):
        all_candidates.append(dict(record, rank=rank))
    if not matches:
        no_finite_match += 1
        continue

    best = dict(matches[0])
    best["accepted"] = best["sc_distance"] < 0.15
    best["near_by_odom"] = best["odom_separation_m"] <= 3.0
    best["history_count"] = len(history)
    best["nearest_history_odom_m"] = float(
        np.min(np.linalg.norm(xyz[history] - xyz[q], axis=1))
    )
    results.append(best)

    if len(results) % 20 == 0:
        print(f"已检索 {len(results)} 个查询帧", flush=True)

for name, records in [
    ("queries.csv", results),
    ("candidates.csv", all_candidates),
]:
    if records:
        with (out / name).open("x", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)

accepted = [r for r in results if r["accepted"]]
near = [r for r in accepted if r["near_by_odom"]]
far = [r for r in accepted if not r["near_by_odom"]]
report = {
    "mode": "same-sequence historical retrieval",
    "exclusion_seconds": 30,
    "max_candidates": 10,
    "acceptance_distance_threshold": 0.15,
    "odom_proximity_threshold_m": 3.0,
    "queries_without_eligible_history": no_history,
    "queries_without_finite_match": no_finite_match,
    "queried_frames": len(results),
    "queries_with_history_within_3m_by_odom": sum(
        r["nearest_history_odom_m"] <= 3.0 for r in results
    ),
    "accepted_candidates": len(accepted),
    "accepted_near_by_odom": len(near),
    "accepted_far_by_odom": len(far),
    "elapsed_s": round(time.perf_counter() - started, 3),
    "note": "Odometry proximity is a diagnostic proxy, not GT or geometric verification.",
    "module_sha256": manifest["module_sha256"],
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(out / "report.json").write_text(json.dumps(report, indent=2))
print("结果目录：", out)
print(json.dumps(report, indent=2))

for title, records in [
    ("位置接近的已接受候选", near),
    ("位置较远的已接受候选", far),
]:
    print("\n" + title + "（按描述子距离列出最多 5 条）：")
    for r in sorted(records, key=lambda r: r["sc_distance"])[:5]:
        print(
            f"查询 {r['query_id']} -> 历史 {r['candidate_id']}, "
            f"SC距离={r['sc_distance']:.4f}, "
            f"位姿距离={r['odom_separation_m']:.2f}m, "
            f"时间差={r['time_gap_s']:.1f}s, "
            f"共同有效扇区={r['shared_sectors']}"
        )
