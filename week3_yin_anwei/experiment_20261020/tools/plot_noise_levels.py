import csv
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path("/home/yaw/fastlio_week3/fixed_runs")
with (root / "noise_summary.csv").open() as f:
    rows = list(csv.DictReader(f))

baseline = next(r for r in rows if r["run"] == "clean_v1")
baseline_ate = float(baseline["ate_rmse_m"])
noise_rows = [r for r in rows if float(r["sigma_m"]) > 0]

levels = sorted({float(r["sigma_m"]) for r in noise_rows})
seeds = sorted({int(r["seed"]) for r in noise_rows})

fig, ax = plt.subplots(figsize=(9, 5))

# 每条细线表示同一个种子在不同噪声强度下的结果。
for seed in seeds:
    selected = sorted(
        [r for r in noise_rows if int(r["seed"]) == seed],
        key=lambda r: float(r["sigma_m"]),
    )
    ax.plot(
        [float(r["sigma_m"]) for r in selected],
        [float(r["ate_rmse_m"]) for r in selected],
        "o--", linewidth=1, alpha=0.7, label=f"Seed {seed}",
    )

# 用误差棒表示中位数和最小—最大范围。
medians, lower, upper = [], [], []
for sigma in levels:
    values = [
        float(r["ate_rmse_m"])
        for r in noise_rows if float(r["sigma_m"]) == sigma
    ]
    m = median(values)
    medians.append(m)
    lower.append(m - min(values))
    upper.append(max(values) - m)

ax.errorbar(
    levels, medians, yerr=[lower, upper],
    fmt="ks-", linewidth=2, capsize=6,
    label="Median and min-max range",
)

# 原图只运行一次，作为参考水平线。
ax.axhline(
    baseline_ate, color="gray", linestyle=":",
    label=f"Original map: {baseline_ate:.3f} m",
)

ax.set_xticks(levels)
ax.set_xlabel("Gaussian noise sigma per axis (m)")
ax.set_ylabel("Aligned translation ATE RMSE (m)")
ax.set_title("Map-noise sensitivity: 3 seeds per tested level")
ax.grid(alpha=0.25)
ax.legend()
fig.tight_layout()

destination = root / "noise_levels.png"
fig.savefig(destination, dpi=180)
plt.close(fig)
print("图片已保存：", destination)
