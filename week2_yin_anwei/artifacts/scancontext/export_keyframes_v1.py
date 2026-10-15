from pathlib import Path
import sqlite3
import csv
import json
import math
import numpy as np
import open3d as o3d

from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2

run = Path("/home/yaw/fastlio_week2/scancontext/runs/raw_20261013_193630")
db = run / "raw_20261013_193630_0.db3"
out = run / "keyframes_v1"

def stamp_ns(msg):
    s = msg.header.stamp
    return s.sec * 1000000000 + s.nanosec

def messages(conn, topic):
    return conn.execute("""
        SELECT messages.data
        FROM messages JOIN topics ON messages.topic_id = topics.id
        WHERE topics.name = ?
        ORDER BY messages.timestamp, messages.id
    """, (topic,))

conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
poses = {}
for (data,) in messages(conn, "/Odometry"):
    msg = deserialize_message(bytes(data), Odometry)
    assert msg.header.frame_id == "camera_init"
    assert msg.child_frame_id == "body"
    ns = stamp_ns(msg)
    assert ns not in poses, "Duplicate odometry timestamp"
    p, q = msg.pose.pose.position, msg.pose.pose.orientation
    xyz = np.array([p.x, p.y, p.z], dtype=float)
    quat = np.array([q.x, q.y, q.z, q.w], dtype=float)
    assert np.isfinite(xyz).all() and np.isfinite(quat).all()
    assert abs(np.linalg.norm(quat) - 1.0) < 0.001
    poses[ns] = (xyz, quat / np.linalg.norm(quat))

assert poses, "No odometry"
out.mkdir(exist_ok=False)
(out / "pcd").mkdir()

records = []
unmatched = []
empty = []
last = None
paired_count = 0
removed_points = 0

for (data,) in messages(conn, "/cloud_registered_body"):
    msg = deserialize_message(bytes(data), PointCloud2)
    assert msg.header.frame_id == "body"
    ns = stamp_ns(msg)
    if ns not in poses:
        unmatched.append(ns)
        continue
    paired_count += 1
    xyz, quat = poses[ns]

    keep = last is None or ns == max(poses)
    if last is not None:
        old_ns, old_xyz, old_quat = last
        distance = np.linalg.norm(xyz - old_xyz)
        dot = np.clip(abs(np.dot(quat, old_quat)), 0.0, 1.0)
        angle = math.degrees(2.0 * math.acos(dot))
        keep = keep or distance >= 1.0 or angle >= 10.0
        keep = keep or (ns - old_ns) >= 2000000000

    if not keep:
        continue

    points = np.array([
        [p[0], p[1], p[2]]
        for p in point_cloud2.read_points(
            msg, field_names=("x", "y", "z"), skip_nans=False
        )
    ], dtype=np.float64).reshape(-1, 3)
    valid = np.isfinite(points).all(axis=1)
    removed_points += int(np.sum(~valid))
    points = points[valid]
    if len(points) == 0:
        empty.append(ns)
        continue

    key_id = len(records)
    relative = f"pcd/{key_id:06d}.pcd"
    cloud = o3d.geometry.PointCloud()
    cloud.points = o3d.utility.Vector3dVector(points)
    if not o3d.io.write_point_cloud(
        str(out / relative), cloud, write_ascii=False
    ):
        raise RuntimeError("PCD write failed: " + relative)

    timestamp = f"{ns // 1000000000}.{ns % 1000000000:09d}"
    records.append([
        key_id, ns, timestamp, relative, len(points),
        *xyz.tolist(), *quat.tolist()
    ])
    last = (ns, xyz.copy(), quat.copy())

conn.close()
assert records, "No keyframes exported"

with (out / "index.csv").open("x", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "id", "stamp_ns", "timestamp", "pcd", "points",
        "x", "y", "z", "qx", "qy", "qz", "qw"
    ])
    writer.writerows(records)

with (out / "poses_tum.txt").open("x") as f:
    for row in records:
        f.write(row[2] + " " + " ".join(
            f"{v:.12g}" for v in row[5:]
        ) + "\n")

report = {
    "source_bag": str(run),
    "point_frame": "body",
    "pose_definition": "T_camera_init_body; quaternion xyzw",
    "selection": {
        "translation_m": 1.0,
        "rotation_deg": 10.0,
        "interval_s": 2.0,
        "rule": "any threshold; also first and last paired frame",
    },
    "paired_frames": paired_count,
    "unmatched_cloud_stamps_ns": unmatched,
    "empty_selected_cloud_stamps_ns": empty,
    "removed_nonfinite_points": removed_points,
    "keyframes": len(records),
    "first_stamp": records[0][2],
    "last_stamp": records[-1][2],
    "point_count_min": min(r[4] for r in records),
    "point_count_max": max(r[4] for r in records),
}
(out / "manifest.json").write_text(json.dumps(report, indent=2))
print("导出目录：", out)
print(json.dumps(report, indent=2))
