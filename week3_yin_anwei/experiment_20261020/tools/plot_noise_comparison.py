from pathlib import Path
import json

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

root = Path("/home/yaw/fastlio_week3/fixed_runs")
clean_dir = root / "clean_v1"
noise_dir = root / "noise_sigma0p10_seed11_v1"

clean = np.loadtxt(clean_dir / "errors.csv", delimiter=",", skiprows=1)
noise = np.loadtxt(noise_dir / "errors.csv", delimiter=",", skiprows=1)

# 必须比较同一批评价时刻。
assert np.array_equal(clean[:, 0], noise[:, 0])

start = clean[0, 0]
elapsed = clean[:, 0] - start

fig, ax = plt.subplots(figsize=(11, 4.5))

for directory, data, label in [
    (clean_dir, clean, "Original map"),
    (noise_dir, noise, "Noise: sigma=0.1 m, seed=11"),
]:
    report = json.loads((directory / "ate_report.json").read_text())
    rmse = report["ATE_m"]["rmse"]
    ax.plot(
        elapsed, data[:, 1],
        label=f"{label} | RMSE={rmse:.3f} m",
        linewidth=1.2,
    )
    i = int(np.argmax(data[:, 1]))
    print(
        f"{label}: 最大误差{data[i, 1]:.6f}米，"
        f"评价开始后{elapsed[i]:.2f}秒，"
        f"消息时间戳{data[i, 0]:.9f}"
    )

ax.set_xlabel("Time since first evaluated pose (s)")
ax.set_ylabel("Translation error after SE(3) alignment (m)")
ax.set_title("Fixed-query comparison: same 753 matched pose pairs")
ax.grid(alpha=0.3)
ax.legend()
fig.tight_layout()

destination = noise_dir / "clean_vs_noise_errors.png"
fig.savefig(destination, dpi=180)
plt.close(fig)
print("图片已保存：", destination)
