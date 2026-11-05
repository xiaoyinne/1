import rclpy
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose


def main():
    rclpy.init()
    node = rclpy.create_node("patrol_client")

    client = ActionClient(
        node, NavigateToPose, "/navigate_to_pose"
    )

    print("正在等待导航服务……")

    if client.wait_for_server(timeout_sec=10.0):
        print("已连接导航服务")
    else:
        print("等待超时，未发现导航服务")

    client.destroy()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
