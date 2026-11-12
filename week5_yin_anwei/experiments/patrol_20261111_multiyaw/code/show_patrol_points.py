"""Display the patrol targets in RViz; coordinates come from patrol.py."""
import math
import rclpy
from rclpy.qos import QoSProfile, DurabilityPolicy, ReliabilityPolicy
from visualization_msgs.msg import Marker, MarkerArray

from patrol import WAYPOINTS


def make_markers():
    array = MarkerArray()
    seen = set()
    for name, x, y, yaw_deg in WAYPOINTS:
        if (name, x, y) in seen:
            continue  # A 在路线中出现两次，但地图上只标一次。
        seen.add((name, x, y))
        color = {"A": (0.05, 0.20, 0.95), "B": (1.0, 0.25, 0.05), "C": (0.1, 0.75, 0.25), "S": (0.55, 0.15, 0.75)}[name]

        point = Marker()
        point.header.frame_id = "map"
        point.ns = "patrol_points"
        point.id = len(array.markers)
        point.type = Marker.ARROW
        point.action = Marker.ADD
        point.pose.position.x = float(x)
        point.pose.position.y = float(y)
        point.pose.position.z = 0.08
        point.pose.orientation.z = math.sin(math.radians(yaw_deg)/2)
        point.pose.orientation.w = math.cos(math.radians(yaw_deg)/2)
        point.scale.x = 0.35
        point.scale.y = point.scale.z = 0.07
        point.color.r, point.color.g, point.color.b = color
        point.color.a = 1.0
        array.markers.append(point)

        label = Marker()
        label.header.frame_id = "map"
        label.ns = "patrol_points"
        label.id = len(array.markers)
        label.type = Marker.TEXT_VIEW_FACING
        label.action = Marker.ADD
        label.pose.position.x = float(x) + 0.22
        label.pose.position.y = float(y) + 0.22
        label.pose.position.z = 0.25
        label.pose.orientation.w = 1.0
        label.scale.z = 0.28
        label.color.r, label.color.g, label.color.b = color
        label.color.a = 1.0
        label.text = f"{name} {yaw_deg:g}°"
        array.markers.append(label)
    return array


def main():
    rclpy.init()
    node = rclpy.create_node("patrol_waypoint_markers")
    qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL,
                     reliability=ReliabilityPolicy.RELIABLE)
    publisher = node.create_publisher(MarkerArray, "/patrol_waypoints", qos)
    markers = make_markers()
    publisher.publish(markers)
    timer = node.create_timer(1.0, lambda: publisher.publish(markers))
    print("正在发布 A、B、C、S 固定位姿标记：/patrol_waypoints", flush=True)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_timer(timer)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
