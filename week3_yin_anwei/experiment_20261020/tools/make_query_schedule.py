import os
import json
import bisect
import sqlite3
from pathlib import Path

from rclpy.serialization import deserialize_message
from nav_msgs.msg import Odometry

run = Path(os.environ["RUN_DIR"])
db = run / "recording/recording_0.db3"
conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)

def read_stamps(topic):
    rows = conn.execute(
        """SELECT m.data FROM messages m
           JOIN topics t ON m.topic_id = t.id
           WHERE t.name = ?""", (topic,)
    )
    result = []
    for (data,) in rows:
        msg = deserialize_message(bytes(data), Odometry)
        s = msg.header.stamp
        result.append(s.sec * 1_000_000_000 + s.nanosec)
    return sorted(result)

stamps = read_stamps("/Odometry")
corrections = read_stamps("/map_to_odom")
assert stamps and corrections
assert len(stamps) == len(set(stamps))

start = corrections[0]
period = 2_000_000_000
selected = []
target = start

while target <= stamps[-1]:
    i = bisect.bisect_left(stamps, target)
    if i == len(stamps):
        break
    selected.append(stamps[i])
    target += period

assert len(selected) == len(set(selected))

folder = Path("/home/yaw/fastlio_week3/fixed_query_v1")
folder.mkdir(exist_ok=False)

report = {
    "source_db": str(db),
    "start_rule": "first recorded accepted correction timestamp",
    "target_period_ns": period,
    "selection_rule": "first paired frame at or after each target",
    "selected_stamp_ns": selected,
}
(folder / "schedule.json").write_text(json.dumps(report, indent=2))

print("固定匹配次数：", len(selected))
print(f"首次扫描时间：{selected[0]/1e9:.9f}")
print(f"末次扫描时间：{selected[-1]/1e9:.9f}")
print("已保存：", folder / "schedule.json")

conn.close()
