import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

out = Path(os.environ["RUN_DIR"]) / "common_eval"

odom = np.loadtxt(out / "odometry_errors.csv", delimiter=",", skiprows=1)
loc = np.loadtxt(out / "localization_errors.csv", delimiter=",", skiprows=1)

# 两条曲线必须使用相同的评价时间。
assert np.array_equal(odom[:, 0], loc[:, 0])

start = odom[0, 0]
elapsed = odom[:, 0] - start

fig, ax = plt.subplots(figsize=(11, 4.5))
ax.plot(elapsed, odom[:, 1], label="FAST-LIO odometry", linewidth=1.2)
ax.plot(elapsed, loc[:, 1], label="Map localization", linewidth=1.2)

ax.set_xlabel("Time since first evaluated pose (s)")
ax.set_ylabel("Translation error after SE(3) alignment (m)")
ax.set_title("Clean-map baseline: same 753 matched pose pairs")
ax.grid(alpha=0.3)
ax.legend()
fig.tight_layout()

path = out / "translation_errors.png"
fig.savefig(path, dpi=180)
plt.close(fig)

print("图片已保存：", path)
for name, data in [("前端", odom), ("地图定位", loc)]:
    i = int(np.argmax(data[:, 1]))
    print(
        f"{name}最大误差：{data[i, 1]:.6f}米，"
        f"出现在评价开始后{data[i, 0]-start:.2f}秒，"
        f"消息时间戳{data[i, 0]:.9f}"
    )
