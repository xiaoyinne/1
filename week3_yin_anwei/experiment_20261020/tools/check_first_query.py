import os
import sys
import json
from pathlib import Path

import numpy as np
import open3d as o3d
import rclpy
from nav_msgs.msg import Odometry

run = Path(os.environ["RUN_DIR"])
folder = Path("/home/yaw/fastlio_week3/fixed_query_v1")

# 导入本次基线保存的定位代码。
sys.path.insert(0, str(run / "scripts"))
from global_localization_synced import GlobalLocalizationNode

schedule = json.loads((folder / "schedule.json").read_text())
ns = schedule["selected_stamp_ns"][0]

data = np.load(folder / "odometry.npz")
indices = np.flatnonzero(data["stamp_ns"] == ns)
assert len(indices) == 1
pose = data["xyz_quat"][indices[0]]
xyz = np.load(folder / "scans/scan_000.npy")

# 读取之前保存的匹配参数。
rclpy.init(args=[
    "--ros-args", "--params-file", str(run / "localization.yaml")
])
node = GlobalLocalizationNode()

try:
    # 原图按既有参数降采样，作为匹配目标。
    prior = o3d.io.read_point_cloud(
        "/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd"
    )
    node.global_map = node.voxel_down_sample(prior, node.map_voxel_size)

    # 放入第一帧扫描，坐标已经是camera_init。
    scan = o3d.geometry.PointCloud()
    scan.points = o3d.utility.Vector3dVector(xyz)
    node.cur_scan = scan
    node.scan_source_time = ns / 1e9

    # 放入同时间戳的里程计。
    odom = Odometry()
    odom.header.stamp.sec, odom.header.stamp.nanosec = divmod(ns, 10**9)
    odom.header.frame_id = "camera_init"
    odom.child_frame_id = "body"
    p, q = odom.pose.pose.position, odom.pose.pose.orientation
    p.x, p.y, p.z = pose[:3].tolist()
    q.x, q.y, q.z, q.w = pose[3:].tolist()
    node.cur_odom = odom

    # 与此前初始化一样，使用单位修正作为初值。
    accepted = node.global_localization(np.eye(4))
    print("第一帧修正是否被接受：", accepted)
    if accepted:
        print("接受的修正矩阵：")
        print(node.T_map_to_odom)
finally:
    node.destroy_node()
    rclpy.shutdown()
