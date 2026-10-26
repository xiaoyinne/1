import os
import sqlite3
from pathlib import Path

from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2
from nav_msgs.msg import Odometry

db = Path(os.environ["RUN_DIR"]) / "recording/recording_0.db3"
conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)

def stamps(topic, message_type):
    rows = conn.execute(
        """SELECT m.data FROM messages m
           JOIN topics t ON m.topic_id = t.id
           WHERE t.name = ?""", (topic,)
    )
    result = []
    for (data,) in rows:
        msg = deserialize_message(bytes(data), message_type)
        s = msg.header.stamp
        result.append(s.sec * 1_000_000_000 + s.nanosec)
    return result

cloud = stamps("/cloud_registered", PointCloud2)
odom = stamps("/Odometry", Odometry)
correction = stamps("/map_to_odom", Odometry)

print("扫描数量：", len(cloud))
print("里程计数量：", len(odom))
print("扫描重复时间戳数：", len(cloud) - len(set(cloud)))
print("里程计重复时间戳数：", len(odom) - len(set(odom)))
print("共有时间戳数：", len(set(cloud) & set(odom)))
print("扫描有、里程计没有：", len(set(cloud) - set(odom)))
print("里程计有、扫描没有：", len(set(odom) - set(cloud)))
if correction:
    print(f"首次接受修正的扫描时间：{min(correction)/1e9:.9f}")

conn.close()
