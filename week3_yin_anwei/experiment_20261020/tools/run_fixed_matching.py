import os
import sys
import json
import csv
import argparse
import shutil
from pathlib import Path

import numpy as np
import open3d as o3d
import rclpy
from nav_msgs.msg import Odometry

parser = argparse.ArgumentParser()
parser.add_argument("--map", required=True)
parser.add_argument("--out", required=True)
args = parser.parse_args()

run = Path(os.environ["RUN_DIR"])
folder = Path("/home/yaw/fastlio_week3/fixed_query_v1")
output = Path(args.out)
output.mkdir(parents=True, exist_ok=False)

sys.path.insert(0, str(run / "scripts"))
from global_localization_synced import GlobalLocalizationNode

# 只记录原方法返回的fitness，不改变其计算或返回值。
class RecordedLocalization(GlobalLocalizationNode):
    def registration_at_scale(self, *a, **kw):
        result = super().registration_at_scale(*a, **kw)
        self.last_fitness = float(result[1])
        return result

schedule = json.loads((folder / "schedule.json").read_text())
data = np.load(folder / "odometry.npz")
poses = dict(zip(data["stamp_ns"].tolist(), data["xyz_quat"]))

shutil.copy2(run / "localization.yaml", output / "localization.yaml")
shutil.copy2(
    run / "scripts/global_localization_synced.py",
    output / "frozen_matcher.py"
)
shutil.copy2(folder / "schedule.json", output / "schedule.json")
(output / "map_path.txt").write_text(str(Path(args.map).resolve()) + "\n")

rclpy.init(args=[
    "--ros-args", "--params-file", str(output / "localization.yaml")
])
node = RecordedLocalization()

try:
    prior = o3d.io.read_point_cloud(args.map)
    assert len(prior.points) > 0
    node.global_map = node.voxel_down_sample(prior, node.map_voxel_size)

    correction = np.eye(4)
    accepted_ns, accepted_transforms, records = [], [], []

    for i, ns in enumerate(schedule["selected_stamp_ns"]):
        xyz = np.load(folder / f"scans/scan_{i:03d}.npy")
        scan = o3d.geometry.PointCloud()
        scan.points = o3d.utility.Vector3dVector(xyz)
        node.cur_scan = scan
        node.scan_source_time = ns / 1e9

        pose = poses[ns]
        odom = Odometry()
        odom.header.stamp.sec, odom.header.stamp.nanosec = divmod(ns, 10**9)
        odom.header.frame_id = "camera_init"
        odom.child_frame_id = "body"
        p, q = odom.pose.pose.position, odom.pose.pose.orientation
        p.x, p.y, p.z = pose[:3].tolist()
        q.x, q.y, q.z, q.w = pose[3:].tolist()
        node.cur_odom = odom

        node.last_fitness = 0.0
        accepted = bool(node.global_localization(correction))
        if accepted:
            correction = node.T_map_to_odom.copy()
            accepted_ns.append(ns)
            accepted_transforms.append(correction.copy())

        records.append([ns, int(accepted), node.last_fitness])

    with (output / "attempts.csv").open("x", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["stamp_ns", "accepted", "fitness"])
        writer.writerows(records)

    np.savez(
        output / "corrections.npz",
        stamp_ns=np.array(accepted_ns, dtype=np.int64),
        transforms=np.array(accepted_transforms).reshape(-1, 4, 4),
    )

    print("匹配尝试次数：", len(records))
    print("接受修正次数：", len(accepted_ns))
    print("结果目录：", output)
finally:
    node.destroy_node()
    rclpy.shutdown()
