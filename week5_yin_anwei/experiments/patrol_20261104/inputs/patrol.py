import time
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

    # 服务器可发现后，继续处理消息，让新客户端完成通信发现。
    settle_until = time.perf_counter() + 2.0
    while time.perf_counter() < settle_until:
        rclpy.spin_once(node, timeout_sec=0.1)

    print(f"正在发送 {name} 点目标，最多等待接收回复 10 秒……", flush=True)
    send_future = client.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, send_future, timeout_sec=10.0)
    if not send_future.done():
        print("接收回复超时：目标是否被接受尚不确定，停止发送后续巡检点。", flush=True)
        return False
    if send_future.exception() is not None:
        print(f"发送目标失败：{send_future.exception()}", flush=True)
        return False
    goal_handle = send_future.result()

    if not goal_handle.accepted:
        print(f"{name} 点目标被拒绝", flush=True)
        return False
    print(f"目标已接受，正在前往 {name} 点……", flush=True)

    # 等待整个导航任务结束后，函数才会返回。
    result_future = goal_handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=120.0)
    if not result_future.done():
        print(f"{name} 点导航超过 120 秒，正在请求取消本段任务……", flush=True)
        cancel_future = goal_handle.cancel_goal_async()
        rclpy.spin_until_future_complete(node, cancel_future, timeout_sec=5.0)
        if cancel_future.done() and cancel_future.exception() is None:
            cancel_response = cancel_future.result()
            if cancel_response.goals_canceling:
                print("服务器已接受取消请求，巡检停止。", flush=True)
            else:
                print("取消请求未确认有正在取消的目标，请检查导航状态。", flush=True)
        else:
            print("未收到取消回复，请检查导航状态。", flush=True)
        return False
    if result_future.exception() is not None:
        print(f"读取导航结果失败：{result_future.exception()}", flush=True)
        return False
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

        # 计时使用单调时钟，单位为秒，统计的是实际等待的墙钟时间。
        patrol_started = time.perf_counter()
        for index, (name, x, y) in enumerate(WAYPOINTS, start=1):
            print(f"巡检进度 {index}/{len(WAYPOINTS)}：{name} 点", flush=True)
            segment_started = time.perf_counter()
            succeeded = navigate_to_point(node, client, name, x, y)
            segment_seconds = time.perf_counter() - segment_started
            print(f"第 {index} 段（{name} 点）耗时：{segment_seconds:.2f} 秒", flush=True)
            if not succeeded:
                print("本段未成功，巡检停止", flush=True)
                return

        patrol_seconds = time.perf_counter() - patrol_started
        print("A → B → A 巡检任务全部返回成功", flush=True)
        print(f"巡检全程耗时：{patrol_seconds:.2f} 秒（墙钟时间）", flush=True)
    finally:
        client.destroy()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
