"""Read-only static sensor/TF audit in an owned headless simulator."""
import json
import math
import os
from pathlib import Path
import subprocess
import time
from datetime import datetime
import xml.etree.ElementTree as ET

import rclpy
from gazebo_msgs.srv import GetEntityState
from nav_msgs.msg import Odometry
from tf2_ros import Time

import repeat_navigation as experiment


def main():
    root = Path(__file__).resolve().parent
    for comm in ['gzserver','controller_server','amcl']:
        if subprocess.run(['pgrep','-x',comm],capture_output=True).returncode == 0:
            raise RuntimeError('Existing simulation; refusing to disturb it')
    folder = root/'validation'/('diagnostic_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    folder.mkdir()
    source = root/'scene_learning/hilti_cells.world'
    tree = ET.parse(source)
    plugin = ET.SubElement(tree.getroot().find('world'),'plugin',name='evaluation_state',filename='libgazebo_ros_state.so')
    ros = ET.SubElement(plugin,'ros')
    ET.SubElement(ros,'namespace').text = '/evaluation'
    world = folder/'measurement.world'; tree.write(world)
    experiment.SPAWN = [-.427,1.370,1.641]
    stream = (folder/'launch.log').open('w')
    command = ['ros2','launch','nav2_bringup','tb3_simulation_launch.py',
               'use_sim_time:=True','use_composition:=False','use_rviz:=False',
               'headless:=True','world:='+str(world),'map:='+str(root/'scene_learning/map.yaml'),
               'x_pose:=-0.427','y_pose:=1.370','yaw:=1.641']
    proc = subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    rclpy.init(); probe = None
    try:
        probe = experiment.Probe(folder)
        scans = []; odom = []
        def scan_cb(msg):
            scans.append({'stamp':msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9,
                          'frame':msg.header.frame_id,'angle_min':msg.angle_min,
                          'angle_increment':msg.angle_increment,'range_min':msg.range_min,
                          'range_max':msg.range_max,'ranges':list(msg.ranges)})
        def odom_cb(msg):
            odom.append({'stamp':msg.header.stamp.sec+msg.header.stamp.nanosec*1e-9,
                         'frame':msg.header.frame_id,'child':msg.child_frame_id,
                         'pose':experiment.pose(msg.pose.pose)})
        probe.create_subscription(experiment.LaserScan,'/scan',scan_cb,experiment.qos_profile_sensor_data)
        probe.create_subscription(Odometry,'/odom',odom_cb,experiment.qos_profile_sensor_data)
        readiness = probe.ready()
        probe.spin_for(4)
        entities = {}
        for name in ['turtlebot3_waffle','turtlebot3_waffle::base_footprint',
                     'turtlebot3_waffle::base_link','turtlebot3_waffle::base_scan']:
            req = GetEntityState.Request(); req.name=name; req.reference_frame='world'
            response = probe.await_future(probe.state.call_async(req))
            entities[name] = {'success':response.success,'pose':experiment.pose(response.state.pose),
                              'z':response.state.pose.position.z}
        transforms = {}
        for parent,child in [('base_footprint','base_scan'),('map','base_footprint'),('odom','base_footprint')]:
            t=probe.tf.lookup_transform(parent,child,Time())
            transforms[parent+'->'+child]={'xyz':[t.transform.translation.x,t.transform.translation.y,t.transform.translation.z],
                                          'yaw':experiment.yaw(t.transform.rotation)}
        data={'readiness':readiness,'entities_world':entities,'tf':transforms,
              'scans':scans[-3:],'odom':odom[-3:]}
        (folder/'static_sensor_audit.json').write_text(json.dumps(data,indent=2))
        print('EVIDENCE',folder,flush=True)
        print(json.dumps({'entities_world':entities,'tf':transforms,'odom':odom[-1:]},indent=2),flush=True)
    finally:
        if probe:probe.destroy_node()
        experiment.owned_shutdown(proc,stream)
        rclpy.shutdown()


if __name__ == '__main__':main()
