import json
import sqlite3
import struct
from rclpy.serialization import deserialize_message
from sensor_msgs.msg import PointCloud2, Imu

database = '/home/yaw/week1_validation_20261010/ros2_bag/ros2_bag.db3'
connection = sqlite3.connect(f'file:{database}?mode=ro', uri=True)
result = {}
for name, cls in (('/hesai/pandar', PointCloud2), ('/alphasense/imu', Imu)):
    topic_id = connection.execute('SELECT id FROM topics WHERE name=?', (name,)).fetchone()[0]
    result[name] = {}
    for label, ordering in (('first', 'ASC'), ('last', 'DESC')):
        row = connection.execute(f'SELECT timestamp, data FROM messages WHERE topic_id=? ORDER BY timestamp {ordering} LIMIT 1', (topic_id,)).fetchone()
        msg = deserialize_message(row[1], cls)
        record = {'bag_timestamp_s': row[0]/1e9, 'header_timestamp_s': msg.header.stamp.sec + msg.header.stamp.nanosec/1e9}
        if cls is PointCloud2:
            record.update(points=msg.width*msg.height, payload_bytes=len(msg.data), point_step=msg.point_step)
            offset = next(field.offset for field in msg.fields if field.name == 'timestamp')
            times = [struct.unpack_from('>d' if msg.is_bigendian else '<d', msg.data, r*msg.row_step+c*msg.point_step+offset)[0]
                     for r in range(msg.height) for c in range(msg.width)]
            record.update(min_point_timestamp_s=min(times), max_point_timestamp_s=max(times))
        result[name][label] = record
print(json.dumps(result, indent=2))
