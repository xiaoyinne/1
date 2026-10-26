import argparse
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

parser = argparse.ArgumentParser()
parser.add_argument("--run", required=True)
args = parser.parse_args()

run = Path(args.run)
folder = Path("/home/yaw/fastlio_week3/fixed_query_v1")

odom = np.load(folder / "odometry.npz")
corrections = np.load(run / "corrections.npz")

odom_ns = odom["stamp_ns"]
poses = odom["xyz_quat"]
correction_ns = corrections["stamp_ns"]
transforms = corrections["transforms"]

assert len(correction_ns) == len(transforms)
assert np.all(np.diff(odom_ns) > 0)
assert np.all(np.diff(correction_ns) > 0)

if len(correction_ns) == 0:
    raise RuntimeError("没有成功修正，不能生成定位轨迹")

count = 0
skipped = 0
destination = run / "trajectory_tum.txt"

with destination.open("x") as f:
    for ns, pose in zip(odom_ns, poses):
        # 找到时间不晚于当前里程计的最新修正。
        index = np.searchsorted(correction_ns, ns, side="right") - 1
        if index < 0:
            skipped += 1
            continue

        assert correction_ns[index] <= ns

        # 机器人在局部坐标系中的位姿。
        local_pose = np.eye(4)
        local_pose[:3, :3] = Rotation.from_quat(pose[3:]).as_matrix()
        local_pose[:3, 3] = pose[:3]

        # 坐标修正 × 局部位姿 = 地图位姿。
        map_pose = transforms[index] @ local_pose
        xyz = map_pose[:3, 3]
        quat = Rotation.from_matrix(map_pose[:3, :3]).as_quat()

        timestamp = f"{int(ns)//10**9}.{int(ns)%10**9:09d}"
        values = np.concatenate((xyz, quat))
        f.write(timestamp + " " +
                " ".join(f"{v:.12f}" for v in values) + "\n")
        count += 1

print("使用的成功修正数：", len(correction_ns))
print("首次修正之前跳过的里程计数：", skipped)
print("输出定位位姿数：", count)
print("轨迹已保存：", destination)
