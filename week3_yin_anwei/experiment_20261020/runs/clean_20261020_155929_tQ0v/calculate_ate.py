import os
import json
from pathlib import Path

import numpy as np
from evo.core import metrics
from evo.tools import file_interface

out = Path(os.environ["RUN_DIR"]) / "common_eval"
gt = file_interface.read_tum_trajectory_file(str(out / "gt_matched.txt"))

report = {}

for name in ["odometry", "localization"]:
    estimate = file_interface.read_tum_trajectory_file(
        str(out / f"{name}_matched.txt")
    )
    assert estimate.num_poses == gt.num_poses

    # 独立SE(3)对齐：只旋转和平移，不缩放。
    rotation, translation, scale = estimate.align(
        gt, correct_scale=False
    )

    # 计算对应位姿之间的三维位置误差。
    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((gt, estimate))
    stats = {
        key: float(value)
        for key, value in ape.get_all_statistics().items()
    }

    report[name] = {
        "pairs": estimate.num_poses,
        "ATE_m": stats,
        "alignment_rotation": rotation.tolist(),
        "alignment_translation": translation.tolist(),
        "alignment_scale": float(scale),
    }

    np.savetxt(
        out / f"{name}_errors.csv",
        np.column_stack((estimate.timestamps, ape.error)),
        delimiter=",",
        header="timestamp,translation_error_m",
        comments="",
        fmt=["%.9f", "%.9f"],
    )

    file_interface.write_tum_trajectory_file(
        str(out / f"{name}_aligned.txt"), estimate
    )

    print(
        f"{name}: ATE RMSE={stats['rmse']:.6f} m, "
        f"mean={stats['mean']:.6f} m, "
        f"max={stats['max']:.6f} m"
    )

(out / "ate_report.json").write_text(json.dumps(report, indent=2))
