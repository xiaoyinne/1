"""Document the selected illustrative route and all its exploration attempts."""
import argparse
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
import numpy as np
import yaml


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('confirmation',type=Path)
    args=parser.parse_args()
    folder=args.confirmation.resolve()
    root=Path(__file__).resolve().parent
    rows=json.loads((folder/'results.json').read_text())
    protocol=json.loads((folder/'protocol.json').read_text())
    if len(rows)!=3:raise RuntimeError('Three confirmation trials required')
    start=protocol['nominal_spawn_xy_yaw'];goal=protocol['cases'][0][1]
    cfg=yaml.safe_load((root/'scene_learning/map.yaml').read_text())
    pixels=np.asarray(Image.open(root/'scene_learning/map.pgm'))
    occ=np.flipud(pixels==0);res=cfg['resolution'];x,y,_=cfg['origin']
    pts=np.linspace(start[:2],goal[:2],5000)
    cc=np.floor((pts[:,0]-x)/res).astype(int);rr=np.floor((pts[:,1]-y)/res).astype(int)
    hit=sorted(set((int(r),int(c)) for r,c in zip(rr,cc) if occ[r,c]))
    if not hit:raise RuntimeError('Direct centre line does not intersect obstacle')
    known_explorations=['repeated_exploration_20261030_205056','repeated_exploration_20261030_205355']
    exploratory=[]
    for name in known_explorations:
        evidence=root/'validation'/name
        p=json.loads((evidence/'protocol.json').read_text())
        for r in json.loads((evidence/'results.json').read_text()):
            exploratory.append({'folder':name,'scenario':p['scenario'],'start':p['nominal_spawn_xy_yaw'],
                                'goal':r.get('goal'),'status':r['status'],
                                'distance_m':r.get('truth_endpoint_distance_m'),
                                'wall_s':r.get('wall_action_s'),'recoveries':r.get('max_recoveries')})
    valid=[r for r in rows if r['status']!='INFRASTRUCTURE_ERROR']
    success=[r for r in valid if r['status']=='SUCCEEDED']
    def describe(key):
        vals=[r[key] for r in valid]
        return {'mean':statistics.mean(vals),'min':min(vals),'max':max(vals)}
    summary={'start':start,'goal':goal,'confirmation_count':len(rows),'action_success_count':len(success),
             'distance_only_pass_count':sum(r['stopped_verified'] and r['truth_endpoint_distance_m']<=.25 for r in valid),
             'combined_pass_count':sum(r['status']=='SUCCEEDED' and r['stopped_verified'] and r['truth_endpoint_distance_m']<=.25 and r['truth_endpoint_yaw_error_rad']<=.25 for r in valid),
             'distance':describe('truth_endpoint_distance_m'),'wall':describe('wall_action_s'),
             'recoveries':[r['max_recoveries'] for r in valid],
             'direct_line_occupied_cells':hit,'explorations':exploratory,
             'scope':'Case selected after exploration; 3 new fresh-start confirmation trials. Not pooled with original complex detour.'}
    (folder/'case_summary.json').write_text(json.dumps(summary,indent=2))
    h,w=pixels.shape
    fig,axes=plt.subplots(1,2,figsize=(10,6),constrained_layout=True)
    colors=['#087F8C','#CF7B2E','#7653A0']
    for ax in axes:
        ax.imshow(pixels,cmap='gray',vmin=0,vmax=254,extent=[x,x+w*res,y,y+h*res],origin='upper')
        ax.plot([start[0],goal[0]],[start[1],goal[1]],ls='--',color='#B64F4F',lw=1.5,label='Direct segment crosses pillar')
        for r in rows:
            if not r.get('truth_trajectory'):continue
            a=np.array([r['truth_before']['xy_yaw'][:2]]+[t['xy_yaw'][:2] for t in r['truth_trajectory']]+[r['truth_after_settle']['xy_yaw'][:2]])
            col=colors[r['repeat']-1]
            ax.plot(a[:,0],a[:,1],color=col,lw=1.7,label=f'Run {r["repeat"]}: {r["status"]}')
            ax.scatter(*a[-1],color=col,marker='s',s=30)
        ax.scatter(*start[:2],color='black',s=45,label='Start',zorder=5)
        ax.scatter(*goal[:2],color='#D43D35',marker='*',s=120,label='Goal',zorder=5)
        ax.set_xlabel('world X (m)');ax.set_ylabel('world Y (m)');ax.grid(alpha=.15)
    axes[0].set_title('Unchanged Hilti slice world')
    axes[1].set_title('Single-pillar route: Gazebo state trajectories')
    axes[1].set_xlim(-.25,1.35);axes[1].set_ylim(.25,2.55)
    axes[1].legend(fontsize=7,loc='lower left')
    fig.savefig(folder/'single_pillar_trajectories.png',dpi=160);plt.close(fig)
    if success:
        selected=min(success,key=lambda r:(r['max_recoveries'],r['wall_action_s']))
        (folder/'illustrated_success.json').write_text(json.dumps({
            'selection':'Among successful confirmation runs, minimum recoveries then shortest wall time; illustrative only',
            'repeat':selected['repeat'],'wall_s':selected['wall_action_s'],
            'recoveries':selected['max_recoveries'],'distance_m':selected['truth_endpoint_distance_m']},indent=2))
        a=np.array([selected['truth_before']['xy_yaw'][:2]]+[t['xy_yaw'][:2] for t in selected['truth_trajectory']]+[selected['truth_after_settle']['xy_yaw'][:2]])
        fig,ax=plt.subplots(figsize=(6,6),constrained_layout=True)
        ax.imshow(pixels,cmap='gray',vmin=0,vmax=254,extent=[x,x+w*res,y,y+h*res],origin='upper')
        ax.plot([start[0],goal[0]],[start[1],goal[1]],ls='--',color='#B64F4F',label='Blocked direct segment')
        ax.plot(a[:,0],a[:,1],color='#087F8C',lw=2,label='Sampled Gazebo state')
        ax.scatter(*start[:2],color='black',s=50,label='Start')
        ax.scatter(*goal[:2],color='#D43D35',marker='*',s=150,label='Goal',zorder=6)
        ax.scatter(*a[-1],color='#087F8C',marker='s',s=60,label='Settled endpoint',zorder=6)
        ax.set_xlim(-.25,1.35);ax.set_ylim(.25,2.55)
        ax.set_xlabel('world X (m)');ax.set_ylabel('world Y (m)');ax.grid(alpha=.15)
        ax.set_title(f'Confirmation run {selected["repeat"]}: SUCCEEDED')
        ax.legend(fontsize=8,loc='lower left')
        fig.savefig(folder/'single_pillar_success.png',dpi=160);plt.close(fig)
    lines=['# 第四周补充案例：单柱绕行','',
           '## 为什么增加这个案例','',
           '为展示可解释的成功绕行过程，另外选择更简单的静态单柱场景。原来复杂绕障3轮超时的记录不修改、不删除；本案例不作为复杂场景性能改进。','',
           '## 路线和固定条件','',
           f'- 起点：{start[:2]}米，初始朝向π/2；目标：{goal[:2]}米，目标朝向π/2。',
           '- 保持原地图、393个障碍几何、导航参数、初值协方差和120秒时限。只改变起终点与初始朝向。',
           '- 直达中心线穿过地图中中心约(0.65,1.35)米的占据格，需要绕行。该孤立格被建模为0.1×0.1×1米柱体，并不代表已识别原场地物体类别。',
           '- 探索选定路线后，另做3轮从新启动仿真开始的确认；探索轮次不混入3轮确认成功率。',
           '- 终点距离与朝向来自Gazebo状态，结束后至少等待2个仿真秒并核实停稳；与AMCL估计分开。','',
           '## 路线探索记录（全部保留）','',
           '|候选|起点XY(m)|目标XY(m)|结果|墙钟(s)|恢复|终点距目标(m)|',
           '|---|---|---|---|---:|---:|---:|']
    for r in exploratory:
        lines.append(f'|{r["scenario"]}|{r["start"][:2]}|{r["goal"][:2]}|{r["status"]}|{r["wall_s"]:.2f}|{r["recoveries"]}|{r["distance_m"]:.3f}|')
    lines+=['','这是探索后选定的演示案例，不是随机抽取的场景样本。不能据此概括所有绕障任务。','',
            '## 选定路线后的独立确认','',
            '|轮次|Action状态|墙钟(s)|恢复|实际终点距离(m)|估计终点距离(m)|实际朝向差(°)|采样路程(m)|',
            '|---:|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        lines.append(f'|{r["repeat"]}|{r["status"]}|{r["wall_action_s"]:.2f}|{r["max_recoveries"]}|{r["truth_endpoint_distance_m"]:.3f}|{r["estimated_endpoint_distance_m"]:.3f}|{math.degrees(r["truth_endpoint_yaw_error_rad"]):.1f}|{r["sampled_truth_path_length_m"]:.2f}|')
    lines+=['',f'Action成功：{len(success)}/3；位置距离≤0.25米且停稳：{summary["distance_only_pass_count"]}/3；Action成功且位置/朝向同时达标：{summary["combined_pass_count"]}/3。',
            f'全部确认轮次终点距离均值{summary["distance"]["mean"]:.3f}米，范围{summary["distance"]["min"]:.3f}～{summary["distance"]["max"]:.3f}米。',
            '', '![完整场景与单柱局部轨迹](single_pillar_trajectories.png)','',
            '## 汇报应该怎样说','',
            '> 我另外设计了较简单的单柱绕行案例，起终点直线穿过障碍。探索选定后进行了3轮独立确认，并分别记录任务状态、终点距离和恢复次数。它用于展示这套仿真环境中的绕行过程；复杂起点的3轮超时仍保留，不能说所有绕障都稳定。','',
            '## 证据与限制','',
            '- protocol.json、script_snapshot.py、installed_nav2_params.yaml保存条件、脚本和参数；results.json保存逐轮Gazebo轨迹、定位估计和Action反馈。',
            '- 两次探索记录见case_summary.json中的目录；旧固定条件基线见repeated_20261030_194814。',
            '- 未测量实际碰撞接触事件，不宣称无碰撞。恢复次数不等于碰撞次数。',
            '- 本案例保持人工平地和统一柱高假设，不证明真实Hilti环境可通行。']
    (folder/'CASE_REPORT.md').write_text('\n'.join(lines),encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
