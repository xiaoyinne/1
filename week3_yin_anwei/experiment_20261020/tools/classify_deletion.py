import csv
import json
import hashlib
from pathlib import Path

root = Path("/home/yaw/fastlio_week3")
folder = root / "delete_runs"
source = folder / "deletion_summary.csv"

baseline = json.loads(
    (root / "fixed_runs/clean_v1/ate_report.json").read_text()
)["ATE_m"]["rmse"]

criteria = {
    "analysis_type": "post_hoc_working_criteria",
    "baseline_ate_rmse_m": baseline,
    "ate_degraded_if_above_m": 2 * baseline,
    "map_interrupted_if_gap_above_s": 10.0,
    "required_coverage": 1.0,
    "summary_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    "note": "ATE uses the fixed GT window; correction gaps use the full query.",
}

with source.open() as f:
    reader = csv.DictReader(f)
    original_fields = reader.fieldnames
    rows = list(reader)

flags = ["ate_degraded", "map_interrupted", "coverage_incomplete"]

for row in rows:
    for key in flags:
        row[key] = ""

    if row["status"] == "error":
        continue

    if row["ate_rmse_m"] != "":
        row["ate_degraded"] = int(
            float(row["ate_rmse_m"]) > criteria["ate_degraded_if_above_m"]
        )
    if row["max_correction_gap_s"] != "":
        row["map_interrupted"] = int(
            float(row["max_correction_gap_s"]) > 10.0
        )
    if row["coverage"] != "":
        row["coverage_incomplete"] = int(float(row["coverage"]) < 1.0)

with (folder / "deletion_classified.csv").open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=original_fields + flags)
    writer.writeheader()
    writer.writerows(rows)

(folder / "posthoc_criteria.json").write_text(
    json.dumps(criteria, indent=2)
)

print(f"ATE退化阈值：严格大于{2 * baseline:.6f}米")
print("修正中断阈值：严格大于10数据秒")

for ratio in sorted({float(r["deleted_block_fraction"]) for r in rows}):
    group = [r for r in rows if float(r["deleted_block_fraction"]) == ratio]
    parts = []
    for key in flags:
        known = [int(r[key]) for r in group if r[key] != ""]
        parts.append(f"{key}={sum(known)}/{len(known)}")
    print(f"删块{ratio:.0%}：" + "，".join(parts))

print("分类表：", folder / "deletion_classified.csv")
print("事后判据：", folder / "posthoc_criteria.json")
