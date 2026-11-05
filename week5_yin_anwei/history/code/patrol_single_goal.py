import rclpy
from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose


def main():
    rclpy.init()
    node = rclpy.create_node("patrol_client")
    client = ActionClient(node, NavigateToPose, "/navigate_to_pose")

    try:
        # 第一步：确认导航服务已经就绪。
        print("正在等待导航服务……", flush=True)
        if not client.wait_for_server(timeout_sec=10.0):
            print("等待超时，未发现导航服务", flush=True)
            return
        print("已连接导航服务", flush=True)

        # 第二步：填写一个 B 点目标，坐标单位为米。
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.pose.position.x = 0.85
        goal.pose.pose.position.y = 3.25
        goal.pose.pose.orientation.z = 0.7071068
        goal.pose.pose.orientation.w = 0.7071068

        # 第三步：发送目标，等待服务器确认接收。
        send_future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(node, send_future)
        goal_handle = send_future.result()

        if not goal_handle.accepted:
            print("目标被拒绝", flush=True)
            return
        print("目标已接受，正在前往 B 点……", flush=True)

        # 第四步：等待整个导航任务结束，读取结果。
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(node, result_future)
        result = result_future.result()

        if result.status == GoalStatus.STATUS_SUCCEEDED:
            print("B 点导航成功", flush=True)
        else:
            print(f"导航未成功，状态码：{result.status}", flush=True)
    finally:
        client.destroy()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
