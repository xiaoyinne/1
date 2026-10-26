import csv
import json
from pathlib import Path
from statistics import median

root = Path("/home/yaw/fastlio_week3/fixed_runs")
records = []

for report_path in sorted(root.glob("*/ate_report.json")):
    run = report_path.parent
    report = json.loads(report_path.read_text())

    if run.name == "clean_v1":
        sigma, seed = 0.0, ""
    else:
        map_path = Path((run / "map_path.txt").read_text().strip())
        metadata = json.loads((map_path.parent / "report.json").read_text())
        sigma = metadata["sigma_per_axis_m"]
        seed = metadata["seed"]

    with (run / "attempts.csv").open() as f:
        attempts = list(csv.DictReader(f))

    stats = report["ATE_m"]
    records.append({
        "run": run.name,
        "sigma_m": sigma,
        "seed": seed,
        "attempts": len(attempts),
        "accepted": sum(int(x["accepted"]) for x in attempts),
        "pairs": report["pairs"],
        "ate_rmse_m": stats["rmse"],
        "ate_mean_m": stats["mean"],
        "ate_max_m": stats["max"],
    })

assert records, "没有找到评价结果"
records.sort(key=lambda x: (x["sigma_m"], str(x["seed"])))

destination = root / "noise_summary.csv"
with destination.open("w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(records[0]))
    writer.writeheader()
    writer.writerows(records)

print("已汇总运行数：", len(records))
print("汇总文件：", destination)

for sigma in sorted({r["sigma_m"] for r in records if r["sigma_m"] > 0}):
    values = [r["ate_rmse_m"] for r in records if r["sigma_m"] == sigma]
    print(
        f"σ={sigma:g}米，重复{len(values)}次："
        f"中位数={median(values):.6f}米，"
        f"范围=[{min(values):.6f}, {max(values):.6f}]米"
    )
