import rclpy
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose


# 每项依次填写：点的名称、地图中的 x 坐标、y 坐标（米）。
# 最后一项重复 A，表示巡检后返回 A。
WAYPOINTS = [
    ("A", 0.05, 0.65),
    ("B", 0.85, 3.25),
    ("A", 0.05, 0.65),
]


def navigate_to_point(node, client, name, x, y):
    """完成一个点的导航；成功返回 True，否则返回 False。"""
    goal = NavigateToPose.Goal()
    goal.pose.header.frame_id = "map"
    goal.pose.pose.position.x = x
    goal.pose.pose.position.y = y
    # 本次所有巡检点均要求朝向地图 +Y 方向。
    goal.pose.pose.orientation.z = 0.7071068
    goal.pose.pose.orientation.w = 0.7071068

    # 等待目标是否被接受。
    send_future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send_future)
    goal_handle = send_future.result()

    if not goal_handle.accepted:
        print(f"{name} 点目标被拒绝", flush=True)
        return False
    print(f"目标已接受，正在前往 {name} 点……", flush=True)

    # 等待整个导航任务结束后，函数才会返回。
    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future)
    result = result_future.result()

    if result.status == GoalStatus.STATUS_SUCCEEDED:
        print(f"{name} 点导航成功", flush=True)
        return True

    print(f"{name} 点导航未成功，状态码：{result.status}", flush=True)
    return False


def main():
    rclpy.init()
    node = rclpy.create_node("patrol_client")
    client = ActionClient(node, NavigateToPose, "/navigate_to_pose")

    try:
        print("正在等待导航服务……", flush=True)
        if not client.wait_for_server(timeout_sec=10.0):
            print("等待超时，未发现导航服务", flush=True)
            return
        print("已连接导航服务", flush=True)

        # 依次取出一个点，等待完成，再处理下一个点。
        for index, (name, x, y) in enumerate(WAYPOINTS, start=1):
            print(f"巡检进度 {index}/{len(WAYPOINTS)}：{name} 点", flush=True)
            if not navigate_to_point(node, client, name, x, y):
                print("本段未成功，巡检停止", flush=True)
                return

        print("A → B → A 巡检任务全部返回成功", flush=True)
    finally:
        client.destroy()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
