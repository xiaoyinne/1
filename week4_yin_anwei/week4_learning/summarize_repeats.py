"""Summarize measured repeated baselines; never infer missing endpoints or collisions."""
import argparse
import json
import math
from pathlib import Path
import statistics as stats

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import yaml


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('folder',type=Path)
    args=parser.parse_args()
    folder=args.folder.resolve()
    rows=json.loads((folder/'results.json').read_text())
    protocol=json.loads((folder/'protocol.json').read_text())
    threshold=protocol['supplementary_endpoint_thresholds']
    keys=['truth_endpoint_distance_m','truth_endpoint_yaw_error_rad','wall_action_s',
          'sim_action_s','max_recoveries','sampled_truth_path_length_m','estimated_endpoint_distance_m']
    groups={}
    for case,goal in protocol['cases']:
        trials=[r for r in rows if r['case']==case]
        usable=[r for r in trials if r['status']!='INFRASTRUCTURE_ERROR']
        good=[r for r in usable if r['status']=='SUCCEEDED']
        def passed(r):
            return r.get('stopped_verified',False) and r['truth_endpoint_distance_m']<=threshold['distance_m'] and r['truth_endpoint_yaw_error_rad']<=threshold['yaw_rad']
        data={'completed_trials':len(usable),'planned_trials':protocol['repeats'],
              'action_success_count':len(good),'geometric_endpoint_pass_count':sum(passed(r) for r in usable),
              'distance_only_pass_count':sum(r.get('stopped_verified',False) and r['truth_endpoint_distance_m']<=threshold['distance_m'] for r in usable),
              'action_success_and_geometry_pass_count':sum(passed(r) for r in good),'metrics':{}}
        for key in keys:
            values=[r[key] for r in usable if r.get(key) is not None]
            successful=[r[key] for r in good if r.get(key) is not None]
            def describe(v):
                return {'n':len(v),'mean':stats.mean(v),'median':stats.median(v),
                        'min':min(v),'max':max(v),'sample_sd':stats.stdev(v) if len(v)>1 else None} if v else None
            data['metrics'][key]={'all_terminal_trials':describe(values),'action_successes_only':describe(successful)}
        groups[case]=data
    (folder/'summary.json').write_text(json.dumps(groups,indent=2))
    cn={'short':'短程','cross':'跨区域','detour':'绕障'}
    lines=['# 第四周补充验证：固定起点的三类任务重复实验','',
           '## 验证目的','',
           '补充整套仿真导航流程的重复性与终点位置检查，不比较不同算法，不宣称精度改进。',
           'Gazebo状态是仿真内部参考真值；不是真实硬件实验或外部实测真值。','',
           '## 预先固定的条件','',
           '- 短程、跨区域、绕障各计划3轮；每轮重启Gazebo与Nav2，名义起点为(0.05, -0.05)米，朝向π/2。',
           '- 使用相同原始地图、393个障碍几何和安装的Nav2参数；不调导航容差或规划器换取成功。',
           '- 为获取仿真位置，仅给world副本加入状态读取插件，已通过XML比对确认原场景几何未改。',
           '- 无Gazebo图形客户端、无RViz；头less运行减少显示负载。因此耗时不宜直接与旧轮次比较。',
           '- 每轮提供相同初始位姿与协方差，核实激光、时钟、生命周期和TF后，按脚本规则准备并发送目标。',
           '- 每次任务墙钟时限120秒；达到时限时取消自己发送的目标。失败、超时保留，基础设施错误单独记录。',
           '- 结束后至少等待2个仿真秒，并检查平移速度<0.01米/秒、角速度<0.03弧度/秒，再读终点。',
           '- 单独检查终点距离≤0.25米且朝向误差≤0.25弧度。该补充几何检查不改写Action状态。','',
           '## 指标怎样计算','',
           '位置距离：`sqrt((x_end-x_goal)^2+(y_end-y_goal)^2)`。此处使用world中的base_footprint位置；地图障碍由相同XY坐标生成，map与world名义几何对齐。',
           '朝向误差：将终点与目标偏航角之差折回[-π,π]后取绝对值。',
           '估计终点距离：使用map到base_footprint的TF估计位置；它与仿真实际终点距离分列。',
           '轨迹长度：对约5Hz的仿真状态采样点累加相邻XY距离，属于采样折线长度，不是高精度里程。',
           '耗时分别记录墙钟与仿真时间；恢复次数来自Action反馈，不等于碰撞次数。','',
           '## 逐轮结果','',
           '|任务|轮次|Action状态|实际终点距目标(m)|估计终点距目标(m)|实际朝向差(°)|墙钟(s)|仿真(s)|恢复|采样路程(m)|停稳核实|',
           '|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---|']
    fmt=lambda v: '缺测' if v is None else f'{v:.3f}'
    for r in rows:
        if r['status']=='INFRASTRUCTURE_ERROR':
            lines.append(f'|{cn[r["case"]]}|{r["repeat"]}|基础设施错误||||||||')
            continue
        lines.append(f'|{cn[r["case"]]}|{r["repeat"]}|{r["status"]}|{fmt(r["truth_endpoint_distance_m"])}|{fmt(r["estimated_endpoint_distance_m"])}|{fmt(math.degrees(r["truth_endpoint_yaw_error_rad"]))}|{r["wall_action_s"]:.2f}|{r["sim_action_s"]:.2f}|{r["max_recoveries"]}|{r["sampled_truth_path_length_m"]:.2f}|{r["stopped_verified"]}|')
    lines+=['','## 每类汇总','','|任务|完成轮数/计划|Action成功|成功且几何达标|所有终止轮次位置距离均值与范围(m)|成功轮次墙钟均值(s)|',
            '|---|---:|---:|---:|---|---:|']
    for case,g in groups.items():
        d=g['metrics']['truth_endpoint_distance_m']['all_terminal_trials']
        t=g['metrics']['wall_action_s']['action_successes_only']
        ds=f'{d["mean"]:.3f} [{d["min"]:.3f}, {d["max"]:.3f}]' if d else '缺测'
        ts=f'{t["mean"]:.2f}' if t else '无成功轮次'
        n=g['completed_trials']
        lines.append(f'|{cn[case]}|{n}/{g["planned_trials"]}|{g["action_success_count"]}/{n}|{g["action_success_and_geometry_pass_count"]}/{n}|{ds}|{ts}|')
    lines+=['','“成功且几何达标”同时要求Action成功、终点停稳、距离和朝向均达标。统计时区分成功轮次与所有终止轮次；超时不当作成功混入成功耗时。',
            '每类仅3轮，结果用于发现问题和观察波动，不能作为长期稳定性或算法优越性的统计证明。','',
            '## 图与原始证据','',
            '![仿真实际轨迹](truth_trajectories.png)','',
            '![仿真实际终点距离与定位估计终点距离](endpoint_distances.png)','',
            '- protocol.json：实验条件、阈值和地图/世界哈希。',
            '- results.json及各子目录result.json：逐轮位姿、状态、时序、轨迹与规划记录。',
            '- 各子目录launch.log：完整启动、导航、恢复和退出日志。',
            '- installed_nav2_params.yaml、versions.txt、script_snapshot.py：实际参数文件、版本和采集脚本。','',
            '## 尚未回答的问题','',
            '- 未安装并校验接触事件测量，不能报告无碰撞率；轨迹贴近或轨迹评分碰障碍不等于实际发生接触。',
            '- 未进行地图加噪/删块导航对比，也未切换算法；未验证地图更新阈值。',
            '- 人工平地、统一障碍高度、白格通行假设继续成立；不证明真实Hilti场地可通行。',
            '- 旧失败记录与本轮起点和采集方式不同，保留旧记录，不拼成同条件实验。']
    (folder/'REPORT.md').write_text('\n'.join(lines),encoding='utf8')
    root=Path(__file__).resolve().parent
    cfg=yaml.safe_load((root/'scene_learning/map.yaml').read_text())
    image=np.array(Image.open(root/'scene_learning/map.pgm'))
    h,w=image.shape;res=cfg['resolution'];x,y,_=cfg['origin']
    colors=['#007C91','#DB7C26','#754DA9']
    fig,axes=plt.subplots(1,3,figsize=(13,6),constrained_layout=True)
    for ax,(case,goal) in zip(axes,protocol['cases']):
        ax.imshow(image,cmap='gray',vmin=0,vmax=254,extent=[x,x+w*res,y,y+h*res],origin='upper')
        for r in rows:
            if r['case']!=case or not r.get('truth_trajectory'):continue
            pts=np.array([r['truth_before']['xy_yaw'][:2]]+[t['xy_yaw'][:2] for t in r['truth_trajectory']]+[r['truth_after_settle']['xy_yaw'][:2]])
            c=colors[r['repeat']-1]
            ax.plot(pts[:,0],pts[:,1],color=c,lw=1.6,label=f'Run {r["repeat"]}: {r["status"]}')
            ax.scatter(*pts[-1],s=28,color=c,marker='s')
        ax.scatter(*goal[:2],marker='*',s=120,color='#CE3C36',label='Requested goal',zorder=6)
        ax.scatter(*protocol['nominal_spawn_xy_yaw'][:2],marker='o',s=35,color='black',label='Nominal start')
        ax.set_title(case);ax.set_xlabel('world X (m)');ax.set_ylabel('world Y (m)')
        ax.legend(fontsize=7,loc='upper left');ax.grid(alpha=.15)
    fig.suptitle('Fresh simulation each run; lines are sampled Gazebo state, squares are settled endpoints',fontsize=11)
    fig.savefig(folder/'truth_trajectories.png',dpi=160);plt.close(fig)
    valid=[r for r in rows if r.get('truth_endpoint_distance_m') is not None]
    if valid:
        fig,ax=plt.subplots(figsize=(10,4.5),constrained_layout=True)
        indices=np.arange(len(valid))
        bars1=ax.bar(indices-.18,[r['truth_endpoint_distance_m'] for r in valid],.35,label='Gazebo state to goal',color='#087F8C')
        bars2=ax.bar(indices+.18,[r.get('estimated_endpoint_distance_m',float('nan')) for r in valid],.35,label='Localization estimate to goal',color='#C4843F')
        ax.bar_label(bars1,fmt='%.2f',padding=2,fontsize=7)
        ax.bar_label(bars2,fmt='%.2f',padding=2,fontsize=7)
        ax.axhline(.25,color='#9B3333',ls='--',label='0.25 m distance check')
        ax.set_xticks(indices,[r['case']+' '+str(r['repeat']) for r in valid],rotation=25)
        ax.set_ylabel('Settled endpoint distance to requested goal (m)')
        ax.set_title('Action status and endpoint distance are separate observations')
        ax.legend(fontsize=9);ax.grid(axis='y',alpha=.2)
        fig.savefig(folder/'endpoint_distances.png',dpi=160);plt.close(fig)
    print(json.dumps(groups,indent=2))
    print('REPORT',folder/'REPORT.md')


if __name__=='__main__':main()
