import os
import copy
import json
from pathlib import Path

import numpy as np
from evo.core import sync
from evo.tools import file_interface

run = Path(os.environ["RUN_DIR"])
gt_path = Path(
    "/home/yaw/fastlio_week2/data/exp18_corridor_lower_gallery_2_imu.txt"
)

gt = file_interface.read_tum_trajectory_file(str(gt_path))
loc = file_interface.read_tum_trajectory_file(str(run / "localization_tum.txt"))
odom = file_interface.read_tum_trajectory_file(str(run / "odometry_tum.txt"))

# 用消息时间关联定位轨迹与真值，最大时间差0.05秒。
gt_match, loc_match = sync.associate_trajectories(
    gt, loc, max_diff=0.05
)

# 取出与这些定位位姿时间完全相同的前端位姿。
indices = np.searchsorted(odom.timestamps, loc_match.timestamps)
assert np.all(indices < len(odom.timestamps))
assert np.array_equal(odom.timestamps[indices], loc_match.timestamps)

odom_match = copy.deepcopy(odom)
odom_match.reduce_to_ids(indices.tolist())

# 检查本次评价没有重复使用时间戳。
assert len(np.unique(gt_match.timestamps)) == len(gt_match.timestamps)
assert len(np.unique(loc_match.timestamps)) == len(loc_match.timestamps)

out = run / "common_eval"
out.mkdir(exist_ok=False)

for name, trajectory in [
    ("gt_matched.txt", gt_match),
    ("odometry_matched.txt", odom_match),
    ("localization_matched.txt", loc_match),
]:
    file_interface.write_tum_trajectory_file(str(out / name), trajectory)

report = {
    "matched_pairs": len(loc_match.timestamps),
    "estimate_start_s": float(loc_match.timestamps[0]),
    "estimate_end_s": float(loc_match.timestamps[-1]),
    "estimate_span_s": float(
        loc_match.timestamps[-1] - loc_match.timestamps[0]
    ),
    "max_time_difference_s": float(np.max(
        np.abs(gt_match.timestamps - loc_match.timestamps)
    )),
    "localization_poses_after_gt_end": int(np.sum(
        loc.timestamps > gt.timestamps[-1]
    )),
}
text = json.dumps(report, indent=2)
(out / "scope.json").write_text(text)
print(text)
