"""Repeat known single-goal checks in the existing exercise scene.

Requires --run because execution moves the simulated robot. No new candidate is
launched. Stops on the first failed/rejected/timed-out goal and preserves logs.
"""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import subprocess
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
SCENE = ROOT/'scene_learning'
CASES = [
    ('short_after_restart', .05, .65, math.pi/2),
    ('cross_region', .85, 3.25, math.pi/2),
    ('around_diagonal_obstacle', .45, -1.45, 0.0),
]


def call(args, timeout=10):
    p = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError(p.stdout+p.stderr)
    return p.stdout


def pose_probe(folder, name):
    p = subprocess.run(['timeout','8s','ros2','run','tf2_ros','tf2_echo',
                        'map','base_footprint','--ros-args','-p','use_sim_time:=true'],
                       capture_output=True,text=True,timeout=12)
    text = p.stdout+p.stderr
    (folder/f'{name}_tf_probe.txt').write_text(text)
    values = re.findall(r'Translation:\s*\[([^]]+)\]',text)
    return list(map(float,values[-1].split(','))) if values else None


def cancel_owned_goal(text, folder):
    m=re.search(r'Goal accepted with ID:\s*([0-9a-fA-F]{32})',text)
    request={}
    if m:
        request={'goal_info':{'goal_id':{'uuid':list(bytes.fromhex(m.group(1)))}}}
    response=call(['ros2','service','call','/navigate_to_pose/_action/cancel_goal',
                   'action_msgs/srv/CancelGoal',json.dumps(request)],timeout=12)
    (folder/'cancellation.txt').write_text(response)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--timeout',type=float,default=120)
    parser.add_argument('--cases',nargs='+',choices=[case[0] for case in CASES],
                        help='Run only selected existing cases, in the original order')
    args=parser.parse_args()
    if not args.run:
        parser.error('Use --run only when this exercise is running and no other goal is active')
    map_value=call(['ros2','param','get','/map_server','yaml_filename'])
    if str(SCENE/'map.yaml') not in map_value:
        raise RuntimeError('Running map differs from the intended exercise scene')
    servers=[]
    for d in Path('/proc').glob('[0-9]*'):
        try:
            if (d/'comm').read_text().strip()=='gzserver':
                servers.append((d/'cmdline').read_bytes().replace(b'\0',b' ').decode())
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    if len(servers)!=1 or str(SCENE/'hilti_cells.world') not in servers[0]:
        raise RuntimeError('Gazebo world is ambiguous or differs from the intended exercise')
    for name in ('amcl','bt_navigator','controller_server'):
        if 'active [3]' not in call(['ros2','lifecycle','get',f'/{name}']):
            raise RuntimeError(f'{name} is not active')
    stamp=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d_%H%M%S')
    folder=ROOT/'validation'/f'automatic_v0_{stamp}'
    folder.mkdir(parents=True,exist_ok=False)
    records=[]
    print('Evidence directory:',folder,flush=True)
    (folder/'run_context.json').write_text(json.dumps({
        'selected_cases': args.cases or [case[0] for case in CASES],
        'versions': call(['dpkg-query','-W','ros-humble-tf2','ros-humble-tf2-ros',
                          'ros-humble-tf2-ros-py','ros-humble-tf2-geometry-msgs']),
        'map_parameter': map_value,
    },indent=2))
    number=r'[-+0-9.eE]+'
    for name,x,y,yaw in CASES:
        if args.cases and name not in args.cases:
            continue
        goal={'pose':{'header':{'frame_id':'map'},'pose':{
            'position':{'x':x,'y':y,'z':0.0},
            'orientation':{'x':0.0,'y':0.0,'z':math.sin(yaw/2),'w':math.cos(yaw/2)}}}}
        (folder/f'{name}_request.json').write_text(json.dumps(goal,indent=2))
        before=pose_probe(folder,name+'_before')
        started=time.monotonic()
        log=folder/f'{name}_action.txt'
        print(f'RUN {name}: goal=({x},{y}), yaw={yaw:.3f}',flush=True)
        timed_out=False
        cancellation_error=None
        with log.open('w') as stream:
            proc=subprocess.Popen(['ros2','action','send_goal','/navigate_to_pose',
                                   'nav2_msgs/action/NavigateToPose',json.dumps(goal),'--feedback'],
                                  stdout=stream,stderr=subprocess.STDOUT,text=True)
            try:proc.wait(timeout=args.timeout)
            except (subprocess.TimeoutExpired,KeyboardInterrupt):
                timed_out=True
                text=log.read_text(errors='replace')
                try:cancel_owned_goal(text,folder)
                except Exception as exc:cancellation_error=str(exc)
                finally:
                    proc.terminate()
                    try:proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:proc.kill();proc.wait()
        wall_elapsed=time.monotonic()-started
        text=log.read_text(errors='replace')
        status_match=re.findall(r'Goal finished with status:\s*(\w+)',text)
        status='TIMEOUT_OR_INTERRUPTED' if timed_out else (status_match[-1] if status_match else 'NO_TERMINAL_STATUS')
        recoveries=re.findall(r'number_of_recoveries:\s*(\d+)',text)
        times=re.findall(r'navigation_time:\s*sec:\s*(\d+)\s*nanosec:\s*(\d+)',text)
        poses=[]
        for block in re.split(r'Feedback:\s*\n',text)[1:]:
            match=re.search(r'position:\s*x:\s*('+number+r')\s*y:\s*('+number+r')',block)
            if match:
                pos=list(map(float,match.groups()))
                if not poses or math.dist(pos,poses[-1])>1e-5:poses.append(pos)
        after=pose_probe(folder,name+'_after')
        record={'case':name,'goal_xy_yaw':[x,y,yaw],'action_status':status,
                'wall_action_elapsed_s':wall_elapsed,
                'last_feedback_navigation_time_s':float(times[-1][0])+float(times[-1][1])*1e-9 if times else None,
                'max_feedback_recoveries':max(map(int,recoveries)) if recoveries else None,
                'before_estimated_pose_xyz':before,'after_estimated_pose_xyz':after,
                'after_estimated_goal_distance_m':math.hypot(after[0]-x,after[1]-y) if after else None,
                'cancellation_error':cancellation_error,
                'estimated_feedback_xy_samples':poses,
                'note':'Queried map-frame pose is an estimate, not external ground truth or ATE. Goal checking is stateful and permits 0.25 m XY tolerance.'}
        records.append(record)
        (folder/'results.json').write_text(json.dumps(records,indent=2))
        print(f'RESULT {name}: {status}, recoveries={record["max_feedback_recoveries"]}, wall={wall_elapsed:.2f}s',flush=True)
        if status!='SUCCEEDED':
            print('Stopping at first unsuccessful goal; no later goal sent.',flush=True)
            break
    lines=['# 练习版v0自动复核结果','',
           '本轮只使用已经运行的 scene_learning，未测试新候选。结果按实际action返回保存，失败后停止。','',
           '| 场景目标 | Action状态 | Action墙钟耗时(s) | 最后反馈中的仿真导航时间(s) | 最大反馈恢复次数 |',
           '|---|---|---:|---:|---:|']
    for r in records:
        lines.append(f'| {r["case"]} | {r["action_status"]} | {r["wall_action_elapsed_s"]:.2f} | {r["last_feedback_navigation_time_s"]} | {r["max_feedback_recoveries"]} |')
    lines+=['','耗时不包含每次目标前后的只读TF查询。反馈中的导航时间可能早于最终结束时刻。',
             '终点TF查询与目标的距离是估计位置距离，不是外部真值误差。原始action日志和前后TF查询保留在同目录。']
    (folder/'SUMMARY.md').write_text('\n'.join(lines))
    print('SUMMARY:',folder/'SUMMARY.md',flush=True)


if __name__=='__main__':main()
