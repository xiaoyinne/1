import os
import sqlite3
from pathlib import Path

from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

run = Path(os.environ["RUN_DIR"])
db = run / "recording/recording_0.db3"
conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)

for topic, filename in [
    ("/Odometry", "odometry_tum.txt"),
    ("/localization", "localization_tum.txt"),
]:
    rows = conn.execute(
        """SELECT m.data
           FROM messages m JOIN topics t ON m.topic_id = t.id
           WHERE t.name = ?""",
        (topic,),
    )
    poses = []
    for (data,) in rows:
        msg = deserialize_message(bytes(data), Odometry)
        stamp = msg.header.stamp
        ns = stamp.sec * 1_000_000_000 + stamp.nanosec
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        poses.append((ns, p.x, p.y, p.z, q.x, q.y, q.z, q.w))

    poses.sort(key=lambda row: row[0])
    path = run / filename
    with path.open("x") as f:
        for ns, *values in poses:
            timestamp = f"{ns // 1_000_000_000}.{ns % 1_000_000_000:09d}"
            f.write(timestamp + " " +
                    " ".join(f"{v:.12f}" for v in values) + "\n")
    print(f"{topic} → {path.name}：{len(poses)}条")

conn.close()
