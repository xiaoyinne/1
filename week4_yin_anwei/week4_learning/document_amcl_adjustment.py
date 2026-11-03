"""Report a complete before/after AMCL profile check without pooling exploration."""
import argparse
import json
import math
from pathlib import Path
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import yaml


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('confirmation',type=Path)
    parser.add_argument('--pilot',type=Path)
    parser.add_argument('--output-stem',default='绕障改善_调整前后验证')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    before=root/'validation/repeated_confirmation_20261030_212801'
    pilot=root/'validation/repeated_tuning_20261030_225835'
    if args.pilot:pilot=args.pilot.resolve()
    after=args.confirmation.resolve()
    pre=json.loads((before/'results.json').read_text())
    post=json.loads((after/'results.json').read_text())
    exploratory=json.loads((pilot/'results.json').read_text())
    bp=json.loads((before/'protocol.json').read_text());ap=json.loads((after/'protocol.json').read_text())
    assert len(pre)==len(post)==3
    for key in ['nominal_spawn_xy_yaw','cases','timeout_wall_s','map_sha256','world_sha256']:
        assert bp[key]==ap[key],key
    assert (pilot/'installed_nav2_params.yaml').read_bytes()==(after/'installed_nav2_params.yaml').read_bytes()
    prior_std=bp.get('initial_pose_standard_deviation',{'xy_m':.5,'yaw_rad':math.sqrt(.0685)})
    final_std=ap.get('initial_pose_standard_deviation',{'xy_m':.5,'yaw_rad':math.sqrt(.0685)})
    initial_changed=prior_std!=final_std
    startup_changed=bp.get('staged_startup',False)!=ap.get('staged_startup',False)
    assert json.loads((pilot/'protocol.json').read_text()).get('initial_pose_standard_deviation',prior_std)==final_std
    oldcfg=yaml.safe_load((before/'installed_nav2_params.yaml').read_text())
    newcfg=yaml.safe_load((after/'installed_nav2_params.yaml').read_text())
    def flatten(v,prefix=''):
        out={}
        for key,value in v.items():
            name=prefix+'.'+key if prefix else key
            if isinstance(value,dict):out.update(flatten(value,name))
            else:out[name]=value
        return out
    a=flatten(oldcfg);b=flatten(newcfg)
    changes={key:{'before':a[key],'after':b[key]} for key in a if a[key]!=b[key]}
    assert len(changes)==6 and all(key.startswith('amcl.') for key in changes)
    def group(rows):
        valid=[r for r in rows if r['status']!='INFRASTRUCTURE_ERROR']
        successful=[r for r in valid if r['status']=='SUCCEEDED']
        return {'n':len(valid),'action_successes':len(successful),
                'distance_passes':sum(r['stopped_verified'] and r['truth_endpoint_distance_m']<=.25 for r in valid),
                'full_endpoint_passes':sum(r['status']=='SUCCEEDED' and r['stopped_verified'] and r['truth_endpoint_distance_m']<=.25 and r['truth_endpoint_yaw_error_rad']<=.25 for r in valid),
                'truth_distances':[r['truth_endpoint_distance_m'] for r in valid],
                'localization_endpoint_offsets':[r['estimate_to_truth_distance_m'] for r in valid],
                'success_mean_wall_s':statistics.mean(r['wall_action_s'] for r in successful) if successful else None}
    summary={'before':group(pre),'after_confirmation':group(post),'parameter_changes':changes,
             'initial_standard_deviation_before':prior_std,'initial_standard_deviation_after':final_std,
             'startup_procedure_changed':startup_changed,
             'pilot':group(exploratory),'pilot_not_pooled':True,
             'limits':'One combined AMCL profile change, only three fresh-start confirmations, approximate historical estimated start.'}
    (after/'amcl_comparison_summary.json').write_text(json.dumps(summary,indent=2))
    cfg=yaml.safe_load((root/'scene_learning/map.yaml').read_text())
    pixels=np.asarray(Image.open(root/'scene_learning/map.pgm'))
    x,y,_=cfg['origin'];res=cfg['resolution'];h,w=pixels.shape
    start=ap['nominal_spawn_xy_yaw'];goal=ap['cases'][0][1]
    fig,axes=plt.subplots(1,2,figsize=(10,7),constrained_layout=True)
    colors=['#087F8C','#CF7B2E','#7653A0']
    after_label='Adjusted AMCL + known-start initialization' if initial_changed else 'Adjusted AMCL profile'
    for ax,rows,label in zip(axes,[pre,post],['Default AMCL',after_label]):
        ax.imshow(pixels,cmap='gray',vmin=0,vmax=254,extent=[x,x+w*res,y,y+h*res],origin='upper')
        for r,col in zip(rows,colors):
            pts=[r['truth_before']['xy_yaw'][:2]]+[t['xy_yaw'][:2] for t in r['truth_trajectory']]+[r['truth_after_settle']['xy_yaw'][:2]]
            a=np.asarray(pts)
            ax.plot(a[:,0],a[:,1],c=col,lw=1.7,label=f'Run {r["repeat"]}: {r["status"]}')
            ax.scatter(*a[-1],c=col,marker='s',s=35)
        ax.scatter(*start[:2],c='black',s=45,zorder=5,label='Same nominal start')
        ax.scatter(*goal[:2],c='#C44335',marker='*',s=130,zorder=5,label='Same requested goal')
        ax.set_title(label+f'\n{sum(r["status"]=="SUCCEEDED" for r in rows)}/3 success',fontsize=11)
        ax.set_xlabel('world X (m)');ax.set_ylabel('world Y (m)');ax.grid(alpha=.15)
        ax.legend(fontsize=7,loc='upper right')
    fig.savefig(after/'amcl_before_after_trajectories.png',dpi=160);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4),constrained_layout=True)
    labels=['Before 1','Before 2','Before 3','After 1','After 2','After 3'];allrows=pre+post
    for ax,key,title in zip(axes,['truth_endpoint_distance_m','estimate_to_truth_distance_m'],
                             ['Physical endpoint distance to goal','Estimated vs physical endpoint offset']):
        ax.bar(labels,[r[key] for r in allrows],color=['#B67B61']*3+['#087F8C']*3)
        for i,r in enumerate(allrows):ax.text(i,r[key]+.025,f'{r[key]:.3f}',ha='center',fontsize=8)
        ax.set_title(title);ax.set_ylabel('m');ax.tick_params(axis='x',rotation=35);ax.grid(axis='y',alpha=.2)
    axes[0].axhline(.25,ls='--',color='#C44335',lw=1,label='Supplementary distance criterion: 0.25 m')
    axes[0].legend(fontsize=7)
    fig.savefig(after/'amcl_before_after_distances.png',dpi=160);plt.close(fig)
    successful=[r for r in post if r['status']=='SUCCEEDED']
    if successful:
        selected=min(successful,key=lambda r:(r['max_recoveries'],r['wall_action_s']))
        (after/'illustrated_success.json').write_text(json.dumps({
            'selection_rule':'Among successful confirmation trials: minimum recoveries, then shortest wall time; illustration only',
            'repeat':selected['repeat'],'wall_s':selected['wall_action_s'],
            'recoveries':selected['max_recoveries'],'physical_endpoint_distance_m':selected['truth_endpoint_distance_m']},indent=2))
        fig,ax=plt.subplots(figsize=(6,7),constrained_layout=True)
        ax.imshow(pixels,cmap='gray',vmin=0,vmax=254,extent=[x,x+w*res,y,y+h*res],origin='upper')
        pts=[selected['truth_before']['xy_yaw'][:2]]+[t['xy_yaw'][:2] for t in selected['truth_trajectory']]+[selected['truth_after_settle']['xy_yaw'][:2]]
        a=np.asarray(pts)
        ax.plot(a[:,0],a[:,1],c='#087F8C',lw=2,label='Sampled physical trajectory')
        ax.scatter(*start[:2],c='black',s=50,label='Known nominal start')
        ax.scatter(*goal[:2],c='#C44335',marker='*',s=150,label='Requested goal')
        ax.scatter(*a[-1],c='#087F8C',marker='s',s=50,label='Settled physical endpoint')
        ax.set_title(f'Confirmation run {selected["repeat"]}: SUCCEEDED\n{selected["wall_action_s"]:.2f} wall s, {selected["max_recoveries"]} recoveries, {selected["truth_endpoint_distance_m"]:.3f} m to goal')
        ax.set_xlabel('world X (m)');ax.set_ylabel('world Y (m)');ax.grid(alpha=.15);ax.legend(fontsize=8)
        fig.savefig(after/'illustrated_success.png',dpi=160);plt.close(fig)
    lines=['# 绕障定位参数调整与重复验证','',
           '## 本次做了什么','',
           '在旧成功起点的近似重建任务中，保持地图、障碍几何、起终点、控制器、规划器和120秒上限一致，调整一组AMCL参数'+('和已知初始位姿的不确定度。' if initial_changed else '，初始位姿协方差保持一致。')+'先做1轮探索，再冻结设置做3轮独立确认。','',
           '## 为什么先检查定位','',
           '静止审计中，按仿真真实位姿和雷达安装位置对原始障碍几何进行射线计算，256条有限有效激光距离的RMSE约0.0105米，全部在0.05米以内。它支持该静止位置处激光与障碍几何一致，不能概括所有位置。',
           '同一时刻里程计位置与Gazebo位置相符，AMCL/TF位置约偏0.106米。默认参数绕障结束时估计与仿真位置约差0.40～0.47米，因此先尝试调整激光匹配。','',
           '## 参数与通俗解释','',
           '|参数|调整前|调整后|含义|','|---|---:|---:|---|']
    meaning={'max_beams':'使用更多激光束参与匹配','sigma_hit':'减小匹配模型中命中距离的宽度',
             'z_hit':'提高命中模型权重','z_rand':'降低随机测量模型权重',
             'update_min_d':'移动更短距离后允许更新定位','update_min_a':'转动更小角度后允许更新定位'}
    for key,value in changes.items():
        simple=key.split('.')[-1]
        lines.append(f'|{simple}|{value["before"]}|{value["after"]}|{meaning[simple]}|')
    if initial_changed:
        lines += [f'|初始XY标准差(m)|{prior_std["xy_m"]:.3f}|{final_std["xy_m"]:.3f}|已知仿真起点采用较小初始不确定度|',
                  f'|初始朝向标准差(°)|{math.degrees(prior_std["yaw_rad"]):.2f}|{math.degrees(final_std["yaw_rad"]):.2f}|同一朝向初值，减少其初始分散范围|']
        lines += ['', '这个设置利用了实验中已知的仿真起点。运行期间不使用仿真真值修正导航，仅由观察器读位置作评价。它验证已知起点下的导航，不是未知起点的全局重定位实验。']
    if startup_changed:
        lines += ['', '确认阶段还采用分阶段启动：先确认时钟与激光，再通过生命周期管理器启动定位，发布初值后再启动导航。之前出现过地图服务配置挂起，因此这是一次准备流程修正。导航耗时仍从发送目标开始，不包含启动准备时间。该变化一并披露，不能把前后差异全部归因于某一个AMCL参数。']
    lines+=['','地图分辨率仍为0.1米，规划容差仍为0.5米，到达位置容差仍为0.25米，朝向容差仍为0.25弧度。该组参数按当前简化场景探索，不是所有真实环境的通用推荐。','',
            '## 全部导航试验','',
            '|阶段|轮次|Action状态|墙钟(s)|恢复|实际终点距目标(m)|定位估计与实际终点差(m)|朝向误差(°)|',
            '|---|---:|---|---:|---:|---:|---:|---:|']
    for label,rows in [('调整前',pre),('探索轮',exploratory),('调整后确认',post)]:
        for r in rows:
            lines.append(f'|{label}|{r["repeat"]}|{r["status"]}|{r["wall_action_s"]:.2f}|{r["max_recoveries"]}|{r["truth_endpoint_distance_m"]:.3f}|{r["estimate_to_truth_distance_m"]:.3f}|{math.degrees(r["truth_endpoint_yaw_error_rad"]):.1f}|')
    lines+=['','探索轮不计入后续3轮确认的成功率。启动检查未通过且未发送导航目标的记录独立保留，不计入导航任务结果。','',
            '## 怎样讲这个结果','',
            f'调整前，当前重建起点下3轮Action成功{summary["before"]["action_successes"]}/3。调整后独立确认成功{summary["after_confirmation"]["action_successes"]}/3，停稳后位置距离≤0.25米{summary["after_confirmation"]["distance_passes"]}/3，同时满足Action、位置和朝向检查{summary["after_confirmation"]["full_endpoint_passes"]}/3。',
            '这是当前场景下的一组初步对照。一次修改了6个AMCL参数'+('和初始不确定度' if initial_changed else '')+'，不能把变化归功于某一个参数；每组仅3轮，也不能据此宣称长期稳定或优于其他导航算法。',
            '旧40.89秒成功记录保留。其起点来自当时的定位估计，本次重建无法恢复旧粒子分布或代价地图历史。','',
            '![实际轨迹对照](amcl_before_after_trajectories.png)','',
            '![终点距离与定位偏差](amcl_before_after_distances.png)','',
            '## 所有其他结果如何保留','',
            '- 默认启动点6轮超时仍保留在原目录，不与本次历史估计起点任务合并。',
            '- 单柱绕行2/3成功属于另一条任务，保留为补充案例，不冒充本次绕障路线。',
            '- 调整前证据：'+str(before),'- 探索轮证据：'+str(pilot),'- 调整后确认：'+str(after),
            '- 静止传感器审计：'+str(root/'validation/diagnostic_20261030_214829'),
            '- 初次参数探索启动未通过：'+str(root/'validation/repeated_tuning_20261030_215103'),'',
            '来源：[Nav2 Humble激光似然场实现](https://raw.githubusercontent.com/ros-navigation/navigation2/humble/nav2_amcl/src/sensors/laser/likelihood_field_model.cpp)。',
            '本次没有测量碰撞接触事件，不把恢复次数作为碰撞次数。']
    if initial_changed:
        previous=root/'validation/repeated_confirmation_20261030_230038'
        lines += ['', '## 中间配置也完整保留','',
                  '只调整激光匹配、保留原先较大初始不确定度的中间配置，先有1次探索成功，独立3轮确认是1/3成功。该组不与本次较小初始不确定度的确认合并。',
                  str(previous)]
        if startup_changed:
            lines += ['', '较小初始不确定度的首个确认批次在启动检查阶段失败，未发送导航目标，记录见：'+str(root/'validation/repeated_confirmation_20261030_230908')+'。随后才使用分阶段启动重新确认，启动故障不当作导航成功或失败混入3轮。']
    if successful:
        lines += ['', '## 供汇报展示的一次确认成功过程','',
                  f'选择规则：在确认成功轮中先选恢复次数最少者，再选墙钟耗时最短者。本图选第{selected["repeat"]}轮；全部确认轮仍在上表中报告。','',
                  '![一次确认成功轨迹](illustrated_success.png)']
    report='\n'.join(lines)
    (after/'AMCL_ADJUSTMENT_REPORT.md').write_text(report,encoding='utf8')
    for name in ['amcl_before_after_trajectories.png','amcl_before_after_distances.png','illustrated_success.png']:
        report=report.replace(']('+name+')','](../week4_learning/validation/'+after.name+'/'+name+')')
    output=root.parent/'week4_presentation'/(args.output_stem+'.md')
    output.write_text(report,encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
