import json
import sqlite3
from pathlib import Path

import numpy as np
from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2

folder = Path("/home/yaw/fastlio_week3/fixed_query_v1")
schedule = json.loads((folder / "schedule.json").read_text())
selected = schedule["selected_stamp_ns"]
selected_index = {ns: i for i, ns in enumerate(selected)}

db = Path(schedule["source_db"])
conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)

def rows(topic):
    return conn.execute(
        """SELECT m.data FROM messages m
           JOIN topics t ON m.topic_id = t.id
           WHERE t.name = ? ORDER BY m.id""", (topic,)
    )

def stamp_ns(msg):
    s = msg.header.stamp
    return s.sec * 1_000_000_000 + s.nanosec

# 保存全部里程计，不做地图修正。
poses = {}
for (data,) in rows("/Odometry"):
    msg = deserialize_message(bytes(data), Odometry)
    assert msg.header.frame_id == "camera_init"
    assert msg.child_frame_id == "body"
    ns = stamp_ns(msg)
    assert ns not in poses
    p, q = msg.pose.pose.position, msg.pose.pose.orientation
    poses[ns] = [p.x, p.y, p.z, q.x, q.y, q.z, q.w]

assert all(ns in poses for ns in selected)

scans = folder / "scans"
scans.mkdir(exist_ok=False)
counts = {}

# 只提取时间表选中的53帧点云。
for (data,) in rows("/cloud_registered"):
    msg = deserialize_message(bytes(data), PointCloud2)
    ns = stamp_ns(msg)
    if ns not in selected_index:
        continue

    assert msg.header.frame_id == "camera_init"
    assert ns not in counts
    xyz = np.array([
        [p[0], p[1], p[2]]
        for p in point_cloud2.read_points(
            msg, field_names=("x", "y", "z"), skip_nans=True
        )
    ], dtype=np.float64)

    assert xyz.ndim == 2 and xyz.shape[1] == 3
    assert len(xyz) > 0 and np.isfinite(xyz).all()
    np.save(scans / f"scan_{selected_index[ns]:03d}.npy", xyz)
    counts[ns] = len(xyz)

assert set(counts) == set(selected)

ns_sorted = sorted(poses)
np.savez(
    folder / "odometry.npz",
    stamp_ns=np.array(ns_sorted, dtype=np.int64),
    xyz_quat=np.array([poses[ns] for ns in ns_sorted]),
)

print("保存扫描帧数：", len(counts))
print("保存里程计条数：", len(poses))
print("每帧点数范围：", min(counts.values()), "～", max(counts.values()))
print("扫描坐标系：camera_init")
print("保存位置：", folder)
conn.close()
