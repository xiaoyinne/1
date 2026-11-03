"""Small repeated baseline; --run starts owned headless simulators and moves the robot.

Unchanged source map, obstacles and navigation parameters. Each trial starts a new
Gazebo/Nav2 process group at the same spawn. Added world plugin only measures state.
"""
import argparse
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import time
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from rclpy.time import Time
from geometry_msgs.msg import PoseWithCovarianceStamped
from gazebo_msgs.srv import GetEntityState
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import NavigateToPose
from nav_msgs.msg import Path as NavPath
from rosgraph_msgs.msg import Clock
from sensor_msgs.msg import LaserScan
from tf2_ros import Buffer, TransformListener

ROOT = Path(__file__).resolve().parent
SPAWN = [.05, -.05, math.pi / 2]
CASES = [('short', [.05, .65, math.pi / 2]),
         ('cross', [.85, 3.25, math.pi / 2]),
         ('detour', [.45, -1.45, 0.])]


def yaw(q):
    return math.atan2(2*(q.w*q.z+q.x*q.y), 1-2*(q.y*q.y+q.z*q.z))


def pose(p):
    return [p.position.x, p.position.y, yaw(p.orientation)]


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Probe(Node):
    def __init__(self, folder):
        super().__init__('repeat_navigation_observer', parameter_overrides=[
            rclpy.parameter.Parameter('use_sim_time', value=True)])
        self.folder = folder
        self.tf = Buffer(cache_time=Duration(seconds=30))
        self.listener = TransformListener(self.tf, self)
        self.initial = self.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
        self.action = ActionClient(self, NavigateToPose, '/navigate_to_pose')
        self.state = self.create_client(GetEntityState, '/evaluation/get_entity_state')
        self.sim = None
        self.scans = 0
        self.last_scan_wall = None
        self.trajectory = []
        self.feedback = []
        self.plans = []
        self.recording = False
        self.create_subscription(Clock, '/clock', self.clock_cb, qos_profile_sensor_data)
        self.create_subscription(LaserScan, '/scan', self.scan_cb, qos_profile_sensor_data)
        self.create_subscription(NavPath, '/plan', self.path_cb, 10)

    def clock_cb(self, m):
        self.sim = m.clock.sec + m.clock.nanosec*1e-9

    def scan_cb(self, m):
        self.scans += 1
        self.last_scan_wall = time.monotonic()

    def path_cb(self, m):
        if self.recording:
            self.plans.append({'sim_s': self.sim, 'frame': m.header.frame_id,
                               'xy': [[p.pose.position.x,p.pose.position.y] for p in m.poses]})

    def spin_for(self, seconds):
        end = time.monotonic()+seconds
        while time.monotonic() < end:
            rclpy.spin_once(self, timeout_sec=.05)

    def await_future(self, future, timeout=6):
        end = time.monotonic()+timeout
        while not future.done() and time.monotonic()<end:
            rclpy.spin_once(self, timeout_sec=.05)
        if not future.done():
            raise TimeoutError('ROS future timed out')
        return future.result()

    def truth(self):
        req = GetEntityState.Request()
        req.name = 'turtlebot3_waffle::base_footprint'
        req.reference_frame = 'world'
        r = self.await_future(self.state.call_async(req))
        if not r.success:
            raise RuntimeError('Gazebo base_footprint state unavailable')
        v = r.state.twist
        return {'sim_s': r.header.stamp.sec+r.header.stamp.nanosec*1e-9,
                'xy_yaw': pose(r.state.pose),
                'linear_speed': math.hypot(v.linear.x,v.linear.y),
                'angular_speed': abs(v.angular.z)}

    def estimate(self):
        try:
            t = self.tf.lookup_transform('map','base_footprint',Time())
            return {'sim_s':t.header.stamp.sec+t.header.stamp.nanosec*1e-9,
                    'xy_yaw':[t.transform.translation.x,t.transform.translation.y,yaw(t.transform.rotation)]}
        except Exception:
            return None

    def ready(self):
        deadline = time.monotonic()+90
        while time.monotonic()<deadline:
            self.spin_for(.2)
            if self.state.service_is_ready() and self.scans>=3 and self.sim is not None:
                break
        else:
            raise RuntimeError('Clock, scan or truth service not ready')
        amcl_client=self.create_client(GetState,'/amcl/get_state')
        while time.monotonic()<deadline:
            if amcl_client.wait_for_service(timeout_sec=.3):
                response=self.await_future(amcl_client.call_async(GetState.Request()))
                if response.current_state.id==3:break
            self.spin_for(.3)
        else:raise RuntimeError('AMCL not active before initial pose')
        start=self.truth()
        if math.dist(start['xy_yaw'][:2],SPAWN[:2])>.05:
            raise RuntimeError('Simulator did not start at intended XY')
        for _ in range(3):
            m=PoseWithCovarianceStamped()
            m.header.frame_id='map'
            m.header.stamp=self.get_clock().now().to_msg()
            m.pose.pose.position.x,m.pose.pose.position.y=SPAWN[:2]
            m.pose.pose.orientation.z=math.sin(SPAWN[2]/2)
            m.pose.pose.orientation.w=math.cos(SPAWN[2]/2)
            m.pose.covariance[0]=m.pose.covariance[7]=.25
            m.pose.covariance[35]=.0685
            self.initial.publish(m)
            self.spin_for(.5)
        states={}
        for name in ['amcl','bt_navigator','planner_server','controller_server']:
            c = self.create_client(GetState,'/'+name+'/get_state')
            while time.monotonic()<deadline:
                if c.wait_for_service(timeout_sec=.3):
                    response=self.await_future(c.call_async(GetState.Request()))
                    if response.current_state.id==3:
                        states[name]=response.current_state.label
                        break
                self.spin_for(.3)
            else:
                raise RuntimeError(name+' not active')
        warmup_start=self.sim
        while time.monotonic()<deadline:
            self.spin_for(.1)
            if self.estimate() is not None and self.sim-warmup_start>=3:
                if self.last_scan_wall and time.monotonic()-self.last_scan_wall<2:
                    return {'lifecycle':states,'truth':self.truth(),'estimate':self.estimate(),
                            'scan_count':self.scans,'warmup_sim_s':self.sim-warmup_start}
        raise RuntimeError('TF initialization did not finish')

    def feedback_cb(self, m):
        f=m.feedback
        self.feedback.append({'sim_s':self.sim,'estimated_xy_yaw':pose(f.current_pose.pose),
                              'recoveries':f.number_of_recoveries,
                              'distance_remaining':f.distance_remaining})

    def execute(self, goal, timeout):
        if not self.action.wait_for_server(timeout_sec=8):
            raise RuntimeError('Navigation action unavailable')
        before=self.truth()
        estimate_before=self.estimate()
        request=NavigateToPose.Goal()
        request.pose.header.frame_id='map'
        request.pose.header.stamp=self.get_clock().now().to_msg()
        request.pose.pose.position.x,request.pose.pose.position.y=goal[:2]
        request.pose.pose.orientation.z=math.sin(goal[2]/2)
        request.pose.pose.orientation.w=math.cos(goal[2]/2)
        self.recording=True
        started=time.monotonic()
        handle=self.await_future(self.action.send_goal_async(request,feedback_callback=self.feedback_cb),10)
        if not handle.accepted:
            return {'status':'REJECTED','goal':goal}
        result=handle.get_result_async()
        next_sample=time.monotonic()
        timed_out=False
        while not result.done():
            self.spin_for(.05)
            if time.monotonic()>=next_sample:
                self.trajectory.append(self.truth())
                next_sample=time.monotonic()+.2
            if time.monotonic()-started>=timeout:
                timed_out=True
                cancel=self.await_future(handle.cancel_goal_async(),10)
                if not cancel.goals_canceling:
                    raise RuntimeError('Owned goal cancellation was not accepted')
                self.await_future(result,15)
                break
        elapsed=time.monotonic()-started
        raw=self.await_future(result,5)
        terminal_truth=self.truth()
        terminal_estimate=self.estimate()
        # Fixed two simulated seconds after terminal status, then verify stopped.
        settle_start=self.sim
        deadline=time.monotonic()+15
        stopped=False
        while time.monotonic()<deadline:
            self.spin_for(.1)
            state=self.truth()
            if self.sim-settle_start>=2 and state['linear_speed']<.01 and state['angular_speed']<.03:
                stopped=True
                break
        self.recording=False
        after=self.truth()
        estimated=self.estimate()
        xy=after['xy_yaw']
        delta=lambda a,b:abs(math.atan2(math.sin(a-b),math.cos(a-b)))
        length=sum(math.dist(a['xy_yaw'][:2],b['xy_yaw'][:2]) for a,b in zip(self.trajectory,self.trajectory[1:]))
        status={4:'SUCCEEDED',5:'CANCELED',6:'ABORTED'}.get(raw.status,str(raw.status))
        return {'status':'TIMEOUT_CANCELED' if timed_out else status,'raw_action_status':raw.status,
                'goal':goal,'truth_before':before,'estimate_before':estimate_before,
                'wall_action_s':elapsed,'sim_action_s':terminal_truth['sim_s']-before['sim_s'],
                'truth_at_terminal':terminal_truth,'estimate_at_terminal':terminal_estimate,
                'truth_after_settle':after,'estimate_after_settle':estimated,
                'stopped_verified':stopped,'settle_sim_s':self.sim-settle_start,
                'truth_endpoint_distance_m':math.dist(xy[:2],goal[:2]),
                'truth_endpoint_yaw_error_rad':delta(xy[2],goal[2]),
                'estimated_endpoint_distance_m':math.dist(estimated['xy_yaw'][:2],goal[:2]) if estimated else None,
                'estimate_to_truth_distance_m':math.dist(estimated['xy_yaw'][:2],xy[:2]) if estimated else None,
                'max_recoveries':max((r['recoveries'] for r in self.feedback),default=None),
                'sampled_truth_path_length_m':length,'truth_trajectory':self.trajectory,
                'feedback':self.feedback,'plans':self.plans}


def owned_shutdown(proc, stream):
    # Only target the process group created by this script, never other user runs.
    record={}
    for sig,seconds in [(signal.SIGINT,20),(signal.SIGTERM,8),(signal.SIGKILL,3)]:
        try:os.killpg(proc.pid,sig)
        except ProcessLookupError:break
        record[signal.Signals(sig).name]=True
        try:
            proc.wait(timeout=seconds)
            break
        except subprocess.TimeoutExpired:continue
    stream.close()
    return record


def main():
    global SPAWN, CASES
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--repeats',type=int,default=3)
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--scenario',choices=['baseline','upper_detour'],default='baseline')
    parser.add_argument('--label',choices=['baseline','exploration','confirmation'],default='baseline')
    args=parser.parse_args()
    if not args.run or args.repeats<1:parser.error('--run is required')
    if args.scenario=='upper_detour':
        SPAWN=[-.45,1.35,-math.pi/2]
        CASES=[('upper_detour',[.45,-1.45,0.])]
    for comm in ['gzserver','controller_server','amcl']:
        if subprocess.run(['pgrep','-x',comm],capture_output=True).returncode==0:
            raise RuntimeError('Existing '+comm+' process; refusing to disturb it')
    stamp=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S')
    folder=ROOT/'validation'/('repeated_'+args.label+'_'+stamp)
    folder.mkdir(parents=True)
    source=ROOT/'scene_learning/hilti_cells.world'
    tree=ET.parse(source)
    world=tree.getroot().find('world')
    plugin=ET.SubElement(world,'plugin',name='evaluation_state',filename='libgazebo_ros_state.so')
    ros=ET.SubElement(plugin,'ros')
    ET.SubElement(ros,'namespace').text='/evaluation'
    ET.SubElement(plugin,'update_rate').text='10.0'
    measured_world=folder/'measurement.world'
    tree.write(measured_world,encoding='utf-8',xml_declaration=True)
    # Confirm that deleting just our observer plugin restores the source XML tree.
    world.remove(plugin)
    if ET.tostring(tree.getroot())!=ET.tostring(ET.parse(source).getroot()):
        raise RuntimeError('Source world geometry differs')
    protocol={'nominal_spawn_xy_yaw':SPAWN,'cases':CASES,'repeats':args.repeats,
              'scenario':args.scenario,'purpose':args.label,
              'comparison_scope':'different-start case; do not pool with original baseline',
              'timeout_wall_s':args.timeout,'fresh_simulator_each_trial':True,
              'world_geometry_unchanged':True,'added_plugin':'read-only state measurement',
              'map_world_alignment':'identity by build_world.py; origin applied to obstacle centres',
              'truth_frame':'world','truth_entity':'turtlebot3_waffle::base_footprint',
              'truth_is':'Gazebo simulation state, not real-world external ground truth',
              'map_sha256':digest(ROOT/'scene_learning/map.pgm'),
              'world_sha256':digest(source),'observer_world_sha256':digest(measured_world),
              'simulated_time_warmup_s':3,'endpoint_settle_sim_s':2,
              'supplementary_endpoint_thresholds':{'distance_m':.25,'yaw_rad':.25,
                   'meaning':'separate geometry check; does not redefine Nav2 Action success'},
              'performance_scope':'small repeated baseline, no algorithm comparison or collision claim'}
    (folder/'protocol.json').write_text(json.dumps(protocol,indent=2))
    params=Path('/opt/ros/humble/share/nav2_bringup/params/nav2_params.yaml')
    (folder/'installed_nav2_params.yaml').write_bytes(params.read_bytes())
    (folder/'script_snapshot.py').write_bytes(Path(__file__).read_bytes())
    (folder/'versions.txt').write_text(subprocess.run(
        ['dpkg-query','-W','ros-humble-nav2-bringup','ros-humble-tf2','ros-humble-tf2-ros'],
        capture_output=True,text=True).stdout)
    print('EVIDENCE',folder,flush=True)
    rclpy.init()
    records=[]
    try:
        # Interleave cases to reduce a simple ordering confound.
        for repeat in range(1,args.repeats+1):
            for name,goal in CASES:
                trial=folder/f'{repeat:02}_{name}'
                trial.mkdir()
                stream=(trial/'launch.log').open('w')
                command=['ros2','launch','nav2_bringup','tb3_simulation_launch.py',
                         'use_sim_time:=True','use_composition:=False','use_rviz:=False',
                         'headless:=True','autostart:=True','world:='+str(measured_world),
                         'map:='+str(ROOT/'scene_learning/map.yaml'),
                         'x_pose:='+str(SPAWN[0]),'y_pose:='+str(SPAWN[1]),'yaw:='+str(SPAWN[2])]
                print('START',repeat,name,flush=True)
                proc=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                probe=None
                try:
                    probe=Probe(trial)
                    readiness=probe.ready()
                    record=probe.execute(goal,args.timeout)
                    record.update({'repeat':repeat,'case':name,'readiness':readiness})
                except Exception as e:
                    record={'repeat':repeat,'case':name,'status':'INFRASTRUCTURE_ERROR','error':repr(e)}
                finally:
                    if probe is not None:probe.destroy_node()
                    record['shutdown']=owned_shutdown(proc,stream)
                records.append(record)
                (trial/'result.json').write_text(json.dumps(record,indent=2))
                (folder/'results.json').write_text(json.dumps(records,indent=2))
                print('RESULT',repeat,name,record['status'],
                      'truth_distance',record.get('truth_endpoint_distance_m'),flush=True)
                if record['status']=='INFRASTRUCTURE_ERROR':
                    raise RuntimeError('Infrastructure failure; stopped, evidence preserved')
                time.sleep(2)
    finally:rclpy.shutdown()
    print('COMPLETE',folder,flush=True)


if __name__=='__main__':main()
