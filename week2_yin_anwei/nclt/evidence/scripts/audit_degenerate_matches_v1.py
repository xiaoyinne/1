from pathlib import Path
import json
import csv
import numpy as np

root = Path("/mnt/d/nclt_student3")
out = root / "degeneracy_audit_v1"
if out.exists():
    raise SystemExit(f"输出目录已存在，未覆盖：{out}")

with np.load(
    root / "descriptors_v1/2012-01-08/descriptors.npz",
    allow_pickle=False,
) as data:
    db_sc = data["descriptors"].copy()

with np.load(
    root / "descriptors_v1/2012-02-05/descriptors.npz",
    allow_pickle=False,
) as data:
    query_sc = data["descriptors"].copy()

retrievals = json.loads(
    (root / "retrieval_cross_date_v1/retrieval_only.json")
    .read_text(encoding="utf-8")
)

geometry = json.loads(
    (root / "geometry_cross_date_v1/results.json")
    .read_text(encoding="utf-8")
)
geometry_lookup = {
    int(r["query_index"]): r for r in geometry
}

# 先只根据描述子检查退化，不使用参考位置。
diagnostics = []

for item in retrievals:
    if not item["accepted"]:
        continue

    q = int(item["query_index"])
    d = int(item["best_db_index"])
    shift = int(item["shift_sectors"]) % 60

    a = np.roll(query_sc[q], shift, axis=1)
    b = db_sc[d]

    count_a = np.count_nonzero(a, axis=0)
    count_b = np.count_nonzero(b, axis=0)

    common = (count_a > 0) & (count_b > 0)
    union = (count_a > 0) | (count_b > 0)

    same_single = (
        common
        & (count_a == 1)
        & (count_b == 1)
        & (np.argmax(a != 0, axis=0) == np.argmax(b != 0, axis=0))
    )

    n_common = int(common.sum())
    n_single = int(same_single.sum())
    n_union = int(union.sum())

    # 一个严格、可解释的诊断标记。
    # 不引入“至少多少个共同扇区”等新的数值阈值。
    degenerate = bool(
        n_common > 0 and n_single == n_common
    )

    diagnostics.append({
        "query_index": q,
        "db_index": d,
        "sc_distance": float(item["sc_distance"]),
        "common_sectors": n_common,
        "union_sectors": n_union,
        "same_single_ring_sectors": n_single,
        "common_fraction": (
            n_common / n_union if n_union else 0.0
        ),
        "all_common_sectors_same_single_ring": degenerate,
    })

# 标记完成后，再结合已有参考评价与ICP结果。
for row in diagnostics:
    g = geometry_lookup[row["query_index"]]
    assert row["db_index"] == int(g["db_index"])

    row.update({
        "near_by_reference": bool(g["near_by_reference"]),
        "geometry_passed": bool(g["geometry_passed"]),
        "translation_reference_error_m":
            float(g["translation_reference_error_m"]),
        "rotation_reference_error_deg":
            float(g["rotation_reference_error_deg"]),
    })

flagged = [
    r for r in diagnostics
    if r["all_common_sectors_same_single_ring"]
]
geometry_passed = [
    r for r in diagnostics if r["geometry_passed"]
]
remaining = [
    r for r in geometry_passed
    if not r["all_common_sectors_same_single_ring"]
]

def counts(rows):
    return {
        "total": len(rows),
        "reference_near": sum(r["near_by_reference"] for r in rows),
        "reference_far": sum(not r["near_by_reference"] for r in rows),
    }

report = {
    "sc_accepted_candidates": len(diagnostics),
    "degenerate_candidates": counts(flagged),
    "degenerate_candidates_that_passed_geometry": counts([
        r for r in flagged if r["geometry_passed"]
    ]),
    "original_geometry_passed": counts(geometry_passed),
    "hypothetical_remaining_after_rejecting_degenerate": counts(remaining),
    "note": (
        "Post-hoc diagnostic on the current sequence pair. "
        "Original retrieval and geometry results are unchanged. "
        "Reference proximity does not establish pose accuracy."
    ),
}

out.mkdir()
with (out / "details.csv").open(
    "w", newline="", encoding="utf-8"
) as f:
    writer = csv.DictWriter(f, fieldnames=list(diagnostics[0]))
    writer.writeheader()
    writer.writerows(diagnostics)

(out / "report.json").write_text(
    json.dumps(report, indent=2),
    encoding="utf-8",
)

print("===== 统计结果 =====")
print(json.dumps(report, indent=2))

print("\n===== 被标记为退化的全部候选 =====")
for r in flagged:
    print(
        f"查询 {r['query_index']} -> 历史 {r['db_index']}，"
        f"共同扇区={r['common_sectors']}，"
        f"位置附近={r['near_by_reference']}，"
        f"几何通过={r['geometry_passed']}，"
        f"平移参考误差={r['translation_reference_error_m']:.3f}米，"
        f"旋转参考误差={r['rotation_reference_error_deg']:.3f}度"
    )

print("\n报告目录：", out)
print("原始检索与ICP结果未修改。")
