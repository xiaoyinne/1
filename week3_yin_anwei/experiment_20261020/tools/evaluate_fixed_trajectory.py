import os
import json
import copy
import argparse
from pathlib import Path

import numpy as np
from evo.core import metrics
from evo.tools import file_interface

parser = argparse.ArgumentParser()
parser.add_argument("--run", required=True)
args = parser.parse_args()

run = Path(args.run)
reference = Path(os.environ["RUN_DIR"]) / "common_eval"

# 沿用之前已确定的753对时间关联，不重新挑选样本。
gt = file_interface.read_tum_trajectory_file(
    str(reference / "gt_matched.txt")
)
sample = file_interface.read_tum_trajectory_file(
    str(reference / "localization_matched.txt")
)
trajectory = file_interface.read_tum_trajectory_file(
    str(run / "trajectory_tum.txt")
)

indices = np.searchsorted(trajectory.timestamps, sample.timestamps)
assert np.all(indices < trajectory.num_poses), "评价时刻缺少输出"
assert np.array_equal(
    trajectory.timestamps[indices], sample.timestamps
), "评价时刻缺少输出"

matched = copy.deepcopy(trajectory)
matched.reduce_to_ids(indices.tolist())
assert matched.num_poses == gt.num_poses

rotation, translation, scale = matched.align(gt, correct_scale=False)

ape = metrics.APE(metrics.PoseRelation.translation_part)
ape.process_data((gt, matched))
stats = {
    key: float(value)
    for key, value in ape.get_all_statistics().items()
}

report = {
    "pairs": matched.num_poses,
    "method": "independent SE3 alignment; no scale correction",
    "ATE_m": stats,
    "alignment_rotation": rotation.tolist(),
    "alignment_translation": translation.tolist(),
    "alignment_scale": float(scale),
}

with (run / "ate_report.json").open("x") as f:
    json.dump(report, f, indent=2)

np.savetxt(
    run / "errors.csv",
    np.column_stack((matched.timestamps, ape.error)),
    delimiter=",",
    header="timestamp,translation_error_m",
    comments="",
    fmt=["%.9f", "%.9f"],
)

print("评价样本数：", matched.num_poses)
print(f"ATE RMSE：{stats['rmse']:.6f}米")
print(f"平均误差：{stats['mean']:.6f}米")
print(f"最大误差：{stats['max']:.6f}米")
