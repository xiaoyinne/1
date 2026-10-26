import os
import sqlite3
from pathlib import Path

from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

run = Path(os.environ["RUN_DIR"])
db = run / "recording/recording_0.db3"
conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)

def read_stamps(topic):
    rows = conn.execute(
        """SELECT m.data
           FROM messages m JOIN topics t ON m.topic_id = t.id
           WHERE t.name = ?""",
        (topic,),
    )
    stamps = []
    for (data,) in rows:
        msg = deserialize_message(bytes(data), Odometry)
        s = msg.header.stamp
        stamps.append(s.sec * 1_000_000_000 + s.nanosec)
    return sorted(stamps)

odom = read_stamps("/Odometry")
loc = read_stamps("/localization")

for name, stamps in [("前端", odom), ("定位", loc)]:
    if not stamps:
        raise RuntimeError(name + "没有消息")
    print(f"{name}：{len(stamps)}条，重复时间戳{len(stamps)-len(set(stamps))}条")
    print(f"  首时间：{stamps[0] / 1e9:.9f}")
    print(f"  末时间：{stamps[-1] / 1e9:.9f}")
    print(f"  跨度：{(stamps[-1]-stamps[0]) / 1e9:.6f}秒")

odom_set, loc_set = set(odom), set(loc)
print("首次定位之前的前端位姿数：", sum(t < loc[0] for t in odom))
print("定位时间范围内，前端有但定位没有的时间戳数：",
      sum(loc[0] <= t <= loc[-1] and t not in loc_set for t in odom_set))
print("最后一次定位之后的前端位姿数：", sum(t > loc[-1] for t in odom))
print("定位有但前端没有的时间戳数：", len(loc_set - odom_set))

conn.close()
