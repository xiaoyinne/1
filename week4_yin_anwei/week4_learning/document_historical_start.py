"""Describe all trials reconstructing the historical successful estimated start."""
import argparse
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import yaml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve()
    root = Path(__file__).resolve().parent
    p = json.loads((folder/'protocol.json').read_text())
    rows = json.loads((folder/'results.json').read_text())
    assert p['scenario'] == 'historical_start'
    assert len(rows) == p['repeats'] == 3, 'Wait for all three trials'
    old_folder = root/'validation'/p['historical_reference']
    old = json.loads((old_folder/'results.json').read_text())[0]
    reference = root/'validation/repeated_20261030_194814'
    baseline = json.loads((reference/'protocol.json').read_text())
    assert p['map_sha256'] == baseline['map_sha256']
    assert p['world_sha256'] == baseline['world_sha256']
    assert (folder/'installed_nav2_params.yaml').read_bytes() == (reference/'installed_nav2_params.yaml').read_bytes()
    assert p['cases'][0][1] == old['goal_xy_yaw']
    success = [r for r in rows if r['status'] == 'SUCCEEDED']
    summary = {
        'historical_reference': p['historical_reference'],
        'reconstruction_limits': p['reconstruction_limits'],
        'nominal_start': p['nominal_spawn_xy_yaw'], 'goal': p['cases'][0][1],
        'completed': len(rows), 'action_success_count': len(success),
        'distance_pass_count': sum(r.get('stopped_verified', False) and r.get('truth_endpoint_distance_m', math.inf) <= .25 for r in rows),
        'trials': [{k: r.get(k) for k in ['repeat','status','wall_action_s','sim_action_s','max_recoveries',
                    'truth_endpoint_distance_m','estimated_endpoint_distance_m','truth_endpoint_yaw_error_rad',
                    'truth_before','estimate_before','truth_after_settle','estimate_after_settle']} for r in rows]
    }
    (folder/'historical_start_summary.json').write_text(json.dumps(summary, indent=2))
    cfg = yaml.safe_load((root/'scene_learning/map.yaml').read_text())
    pixels = np.asarray(Image.open(root/'scene_learning/map.pgm'))
    x,y,_ = cfg['origin']; res = cfg['resolution']; h,w = pixels.shape
    goal = p['cases'][0][1]; start = p['nominal_spawn_xy_yaw']
    fig, axes = plt.subplots(1,2,figsize=(10,7),constrained_layout=True)
    for ax in axes:
        ax.imshow(pixels,cmap='gray',vmin=0,vmax=254,
                  extent=[x,x+w*res,y,y+h*res],origin='upper')
        ax.scatter(*goal[:2],c='#C44335',marker='*',s=130,zorder=5,label='Requested goal')
        ax.set_xlabel('X (m)'); ax.set_ylabel('Y (m)'); ax.grid(alpha=.15)
    old_xy = np.asarray(old['estimated_feedback_xy_samples'])
    axes[0].plot(old_xy[:,0],old_xy[:,1],color='#7653A0',lw=2,label='Historical TF/AMCL estimate')
    axes[0].scatter(*old['before_estimated_pose_xyz'][:2],c='black',s=40,label='Estimated start')
    axes[0].scatter(*old['after_estimated_pose_xyz'][:2],c='#7653A0',marker='s',s=40,label='Estimated endpoint')
    axes[0].set_title('Old run: SUCCEEDED, 40.89 wall s\nEstimated trajectory; physical state not recorded')
    for r,col in zip(rows,['#087F8C','#CF7B2E','#7653A0']):
        if not r.get('truth_trajectory'): continue
        pts = [r['truth_before']['xy_yaw'][:2]]+[t['xy_yaw'][:2] for t in r['truth_trajectory']]+[r['truth_after_settle']['xy_yaw'][:2]]
        a = np.asarray(pts)
        axes[1].plot(a[:,0],a[:,1],c=col,lw=1.7,label=f'Run {r["repeat"]}: {r["status"]}')
        axes[1].scatter(*a[-1],c=col,marker='s',s=35)
    axes[1].scatter(*start[:2],c='black',s=40,zorder=6,label='Reconstructed nominal start')
    axes[1].set_title(f'Fresh reconstruction: {len(success)}/3 Action success\nSampled Gazebo physical trajectories')
    for ax in axes: ax.legend(fontsize=7,loc='upper right')
    fig.savefig(folder/'historical_start_comparison.png',dpi=160)
    plt.close(fig)
    lines = ['# 旧成功起点的三轮近似复现','',
        '## 为什么做这次复测','',
        '旧表中的绕障成功确实存在：Action返回SUCCEEDED，墙钟40.89秒，3次恢复。近期默认启动点的6轮超时并非该成功起点的重复试验，不能据此否定旧成功记录。','',
        '## 本次条件','',
        f'- 参照旧TF日志，将起点重建为({start[0]:.3f},{start[1]:.3f})米，朝向{math.degrees(start[2]):.2f}°。',
        '- 目标仍为(0.45,-1.45)米，朝向0°。地图、world原几何与近期默认启动点批次哈希一致；Nav2参数文件逐字节一致。',
        '- 每轮新启动Gazebo和Nav2，已知初值初始化，准备好激光、时钟、TF后发送目标；墙钟上限120秒。',
        '- 旧起点是AMCL/TF估计，旧仿真真实位置、粒子分布和代价地图历史未保存。因此本次是近似重建，不能称为全部状态相同的精确重放。',
        '- 新试验以Gazebo状态测量停稳后终点；旧记录只有估计位置，两个来源分别说明。','',
        '## 逐轮结果','',
        '|记录|Action状态|墙钟(s)|恢复次数|仿真真实终点距目标(m)|定位估计终点距目标(m)|',
        '|---|---|---:|---:|---:|---:|',
        f'|旧成功记录|{old["action_status"]}|{old["wall_action_elapsed_s"]:.2f}|{old["max_feedback_recoveries"]}|未测|{old["after_estimated_goal_distance_m"]:.3f}|']
    fmt = lambda value: '未测' if value is None else f'{value:.3f}'
    for r in rows:
        lines.append(f'|本次第{r["repeat"]}轮|{r["status"]}|{fmt(r.get("wall_action_s"))}|{r.get("max_recoveries","未测")}|{fmt(r.get("truth_endpoint_distance_m"))}|{fmt(r.get("estimated_endpoint_distance_m"))}|')
    lines += ['',f'本次Action成功：{len(success)}/3；停稳后仿真位置距离≤0.25米：{summary["distance_pass_count"]}/3。','',
        'ABORTED表示Nav2自行返回任务失败；TIMEOUT_CANCELED表示达到本次120秒墙钟上限后由试验脚本取消，两者分别记录。','',
        '## 可得出的结论','']
    if success:
        lines += ['旧估计起点的近似重建出现了新的成功记录，说明该任务在本次条件下可完成；仍需结合全部3轮结果讨论重复性，不能只用最快的一轮代表稳定性能。']
    else:
        lines += ['本次3轮未复现旧成功。旧成功记录仍保留；近似重建未成功不能证明旧结果无效，也不能把它描述为已稳定复现。需要进一步区分真实起点、定位状态和执行过程的影响。']
    offsets = [r['estimate_to_truth_distance_m'] for r in rows if r.get('estimate_to_truth_distance_m') is not None]
    if offsets:
        lines += ['', '## 失败日志与排查线索','',
            '本次三轮日志均出现规划器无法生成有效路径的提示；第三轮还反复出现Failed to make progress。它们说明失败发生在规划/执行过程中，但尚不足以单独确认根因。',
            f'停稳后AMCL/TF估计与Gazebo实际位置的距离为'+ '、'.join(f'{v:.3f}米' for v in offsets)+'。该差异值得进一步检查，不能仅凭超时或失败就断定障碍间距不够。']
    lines += ['', '![旧估计轨迹与本次仿真真实轨迹](historical_start_comparison.png)','',
        '## 证据','',
        '- protocol.json保存起终点、条件、哈希和重建限制；installed_nav2_params.yaml保存参数文件。',
        '- 每轮result.json与launch.log保存状态、位姿、轨迹和程序日志；results.json合并全部三轮。',
        '- 历史记录目录：'+str(old_folder),'',
        '没有测量真实硬件精度或碰撞接触事件；不将恢复次数解释为碰撞次数。']
    report = '\n'.join(lines)
    (folder/'HISTORICAL_START_REPORT.md').write_text(report,encoding='utf8')
    output = root.parent/'week4_presentation/旧成功起点_三轮复测.md'
    # Delivery copy links directly to the evidence plot from its own directory.
    plot = '../week4_learning/validation/'+folder.name+'/historical_start_comparison.png'
    output.write_text(report.replace('](historical_start_comparison.png)',']('+plot+')'),encoding='utf8')
    print(json.dumps(summary,indent=2))


if __name__ == '__main__':
    main()
