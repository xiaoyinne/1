"""Batch repeated scene preparation; do not launch ROS or move the robot.

Candidate routes establish grid connectivity under the artificial-floor demo
assumption. They are not Nav2 navigation results or verified real walkways.
"""
import csv
from collections import deque
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from project_slice import read_xyz

ROOT = Path(__file__).resolve().parent
DEST = ROOT / 'candidates_v1'
SOURCE = Path('/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd')
REGIONS = [
    ('r0_exercise', 'R0: existing exercise', [-2.2, 1.4, -1.8, 3.8]),
    ('r1_near_origin', 'R1: near-origin structure', [-5.0, 1.5, -4.0, 7.0]),
    ('r2_arc_right', 'R2: right-hand arc region', [-7.0, 1.5, -8.0, 8.0]),
    ('r3_arc_upper', 'R3: upper arc region', [-14.0, 1.5, 2.0, 10.0]),
]
BANDS = [('band_a', [-1.5, -0.8]), ('band_b', [-0.3, 0.3])]
RESOLUTION = 0.1
MIN_POINTS = 5
ROBOT_RADIUS = 0.22
CLEARANCE = 0.28


def farthest(mask, start):
    distance = np.full(mask.shape, -1, dtype=np.int32)
    distance[start] = 0
    parent = {}
    queue = deque([start])
    last = start
    while queue:
        r, c = queue.popleft()
        last = (r, c)
        for nxt in ((r-1, c), (r+1, c), (r, c-1), (r, c+1)):
            if (0 <= nxt[0] < mask.shape[0] and 0 <= nxt[1] < mask.shape[1]
                    and mask[nxt] and distance[nxt] < 0):
                distance[nxt] = distance[r, c] + 1
                parent[nxt] = (r, c)
                queue.append(nxt)
    return last, distance, parent


def reference_route(occupied, bounds):
    # Outside the crop is blocked for this clearance calculation only;
    # no artificial perimeter wall is added to the exported map/world.
    clearance = ndi.distance_transform_edt(~np.pad(occupied, 1, constant_values=True))[1:-1, 1:-1]
    clearance = clearance * RESOLUTION - RESOLUTION * math.sqrt(2) / 2
    components, _ = ndi.label(clearance >= CLEARANCE)
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    if sizes.max() == 0:
        return np.empty((0, 2)), clearance, sizes, components, None
    main_label = int(sizes.argmax())
    mask = components == main_label
    seed = tuple(int(v) for v in np.argwhere(mask)[0])
    start, _, _ = farthest(mask, seed)
    goal, dist, parent = farthest(mask, start)
    cells = [goal]
    while cells[-1] != start:
        cells.append(parent[cells[-1]])
    cells.reverse()
    xmin, _, ymin, _ = bounds
    xy = np.array([[xmin+(c+.5)*RESOLUTION, ymin+(r+.5)*RESOLUTION] for r, c in cells])
    return xy, clearance, sizes, components, main_label


def verify_world(folder, occupied):
    tree = ET.parse(folder / 'hilti_cells.world')
    boxes = tree.findall('.//model[@name="hilti_projected_cells"]/link/collision')
    config = __import__('yaml').safe_load((folder / 'map.yaml').read_text())
    xmin, ymin, _ = config['origin']
    rebuilt = np.zeros_like(occupied)
    for box in boxes:
        x, y, z, roll, pitch, yaw = map(float, box.findtext('pose').split())
        sx, sy, sz = map(float, box.findtext('geometry/box/size').split())
        c = round((x-xmin)/RESOLUTION-.5)
        r = round((y-ymin)/RESOLUTION-.5)
        if not (0 <= r < rebuilt.shape[0] and 0 <= c < rebuilt.shape[1]):
            raise ValueError('World box lies outside the map')
        if rebuilt[r, c]:
            raise ValueError('Duplicate collision box at a grid cell')
        if not np.allclose([x, y, z, sx, sy, sz, roll, pitch, yaw],
                           [xmin+(c+.5)*RESOLUTION, ymin+(r+.5)*RESOLUTION,
                            .5, RESOLUTION, RESOLUTION, 1, 0, 0, 0], atol=1e-7, rtol=0):
            raise ValueError('World geometry differs from its map cell')
        rebuilt[r, c] = True
    if not np.array_equal(rebuilt, occupied):
        raise ValueError('Map and world occupancy differ')
    return len(boxes)


def plot_case(ax, record, occupied, route, main_component=None):
    xmin, xmax, ymin, ymax = record['bounds_xy_m']
    ax.imshow(~occupied, origin='lower', extent=[xmin, xmax, ymin, ymax],
              cmap='gray', vmin=0, vmax=1, interpolation='nearest')
    if len(route):
        ax.plot(route[:, 0], route[:, 1], color='#1976d2', lw=1.2,
                label='Grid-connectivity route (not Nav2)')
        ax.scatter(*route[0], c='#25a244', s=20, zorder=4)
        ax.scatter(*route[-1], c='#e53e3e', s=20, zorder=4)
    ax.set_title(f"{record['title']} / {record['band_id']}\n"
                 f"{record['obstacle_cells']} black cells; "
                 f"largest safe component {record['largest_safe_area_m2']:.2f} m²", fontsize=10)
    ax.set(xlabel='Source X (m)', ylabel='Source Y (m)')
    ax.set_aspect('equal')
    if len(route):
        ax.legend(fontsize=6, loc='best')


def main():
    import yaml
    DEST.mkdir(exist_ok=True)
    x, y, z = read_xyz(SOURCE)
    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    hasher = hashlib.sha256()
    with SOURCE.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            hasher.update(chunk)
    source_hash = hasher.hexdigest()
    records, pictures = [], {}
    for region_id, title, bounds in REGIONS:
        xmin, xmax, ymin, ymax = bounds
        crop = finite & (x >= xmin) & (x < xmax) & (y >= ymin) & (y < ymax)
        px, py, pz = [a[crop].astype(np.float64) for a in (x, y, z)]
        inside = (px >= xmin) & (px < xmax) & (py >= ymin) & (py < ymax)
        px, py, pz = px[inside], py[inside], pz[inside]
        for band_id, height_band in BANDS:
            lo, hi = height_band
            selected = (pz >= lo) & (pz <= hi)
            count = np.zeros((round((ymax-ymin)/RESOLUTION), round((xmax-xmin)/RESOLUTION)), dtype=np.int64)
            col = np.floor((px[selected]-xmin)/RESOLUTION).astype(int)
            row = np.floor((py[selected]-ymin)/RESOLUTION).astype(int)
            np.add.at(count, (row, col), 1)
            occupied = count >= MIN_POINTS
            route, clearance, sizes, labels, main_label = reference_route(occupied, bounds)
            folder = DEST / region_id / band_id
            folder.mkdir(parents=True, exist_ok=True)
            Image.fromarray(np.flipud(np.where(occupied, 0, 254).astype(np.uint8))).save(folder / 'map.pgm')
            config = {'image':'map.pgm', 'mode':'trinary', 'resolution':RESOLUTION,
                      'origin':[xmin, ymin, 0.0], 'negate':0, 'occupied_thresh':.65, 'free_thresh':.196}
            (folder / 'map.yaml').write_text(yaml.safe_dump(config, sort_keys=False))
            np.savez_compressed(folder / 'projection.npz', point_count=count, occupied=occupied,
                                bounds=np.array(bounds), resolution=RESOLUTION, height_band=np.array(height_band),
                                clearance_m=clearance, safe_component_labels=labels, reference_route_xy=route)
            run = subprocess.run([sys.executable, '-s', str(ROOT/'build_world.py'),
                                  '--map', str(folder/'map.yaml'), '--height', '1.0'],
                                 capture_output=True, text=True)
            (folder/'build_log.txt').write_text(run.stdout+run.stderr)
            if run.returncode:
                raise RuntimeError(run.stderr)
            box_count = verify_world(folder, occupied)
            record = {
                'region_id':region_id, 'title':title, 'band_id':band_id,
                'bounds_xy_m':bounds, 'height_band_m':height_band,
                'source_pcd':str(SOURCE), 'source_sha256':source_hash,
                'roi_points':len(px), 'roi_z_percentiles_10_50_90':np.percentile(pz,[10,50,90]).tolist(),
                'selected_points':int(selected.sum()), 'resolution_m':RESOLUTION, 'min_points_per_cell':MIN_POINTS,
                'grid_cols_rows':[occupied.shape[1],occupied.shape[0]],
                'obstacle_cells':int(occupied.sum()), 'obstacle_fraction':float(occupied.mean()),
                'world_collision_boxes':box_count, 'map_world_geometry_checked':True,
                'robot_radius_m':ROBOT_RADIUS, 'clearance_cutoff_m':CLEARANCE,
                'safe_components':int((sizes>0).sum()), 'largest_safe_cells':int(sizes.max()),
                'largest_safe_area_m2':float(sizes.max()*RESOLUTION**2),
                'reference_grid_route_length_m':float((len(route)-1)*RESOLUTION) if len(route) else None,
                'reference_start_xy':route[0].tolist() if len(route) else None,
                'reference_goal_xy':route[-1].tolist() if len(route) else None,
                'navigation_tested':False,
                'status':'generated candidate; no floor validation or ROS navigation trial',
                'route_note':'BFS route in the largest grid component with conservative clearance; not a Nav2 result or physical traversability proof.',
                'clearance_boundary_assumption':'Outside crop treated as blocked for analysis only; no perimeter wall added.',
                'vertical_geometry':'Artificial flat floor at Z=0 and unit-height columns; source height variation is not reconstructed.',
            }
            (folder/'candidate_info.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
            fig,ax=plt.subplots(figsize=(7,7))
            plot_case(ax, record, occupied, route)
            fig.text(.5,.02,'White cells were below the point threshold, not verified free space.\nThe route is a geometric candidate and has not been executed.',ha='center',fontsize=8)
            fig.tight_layout(rect=(0,.08,1,1));fig.savefig(folder/'candidate.png',dpi=150);plt.close(fig)
            records.append(record)
            pictures[(region_id,band_id)] = (record, occupied, route)
            print(f"{region_id}/{band_id}: {int(selected.sum())} points; {box_count} boxes; "
                  f"{record['safe_components']} safe components; largest={record['largest_safe_area_m2']:.2f} m2; geometry checked",flush=True)
    for band_id,_ in BANDS:
        fig,axes=plt.subplots(2,2,figsize=(12,12))
        for ax,(region_id,_,_) in zip(axes.ravel(),REGIONS):
            plot_case(ax,*pictures[(region_id,band_id)])
        fig.suptitle(f'Candidate regions / {band_id}: connectivity under the demo assumption',fontsize=14)
        fig.text(.5,.025,'Green/red = reference endpoints. Blue = grid-connectivity route, not an executed Nav2 path.\nAll candidates use 0.1 m cells, >=5 points/cell and artificial flat ground. No scene has replaced the running exercise.',ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.08,1,.95));fig.savefig(DEST/f'overview_{band_id}.png',dpi=150);plt.close(fig)
    (DEST/'candidate_summary.json').write_text(json.dumps(records,ensure_ascii=False,indent=2))
    columns=['region_id','band_id','selected_points','obstacle_cells','safe_components','largest_safe_area_m2','reference_grid_route_length_m','map_world_geometry_checked','navigation_tested']
    with (DEST/'candidate_summary.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    readme=['# 第四周正式候选的自动准备结果','',
            '这里只完成重复的数据准备与静态检查；尚未选定正式场景，也未启动这些候选或发送导航目标。',
            '原练习场景和正在运行的窗口保持不变。候选的白格未验证真实自由空间，人工地面不代表原始地面重建。','',
            '## 固定条件','',f'- 分辨率 {RESOLUTION} 米；每格至少 {MIN_POINTS} 点；圆形机器人半径参考 {ROBOT_RADIUS} 米。',
            f'- 连通性分析要求保守间隙至少 {CLEARANCE} 米；这是本例的分析设置，不是通用标准。',
            '- 图中蓝线由网格BFS产生，只说明上述假设下的连通性；不是Nav2规划结果、实际导航记录或路线可通行的真值。',
            '- 每份候选都导出PGM/YAML/world，并从生成的SDF碰撞体反算网格核对位置、尺寸和占据一致性。',
            '- 目前每个黑格仍生成一个长方体，较大场景的运行负担尚未评估。','',
            '## 候选汇总','',
            '| 区域 | 高度段 | 点数 | 障碍格/碰撞体 | 安全连通区数 | 最大安全连通区面积(m²) | 参考网格路长(m) |',
            '|---|---|---:|---:|---:|---:|---:|']
    for r in records:
        length = r['reference_grid_route_length_m']
        length_text = f'{length:.1f}' if length is not None else '无连通路线'
        readme.append(f"| {r['region_id']} | {r['height_band_m']} | {r['selected_points']} | {r['obstacle_cells']} | {r['safe_components']} | {r['largest_safe_area_m2']:.2f} | {length_text} |")
    readme += ['', '## 接下来需要讲解和判断的部分','',
               '1. 对照原点云和高度分布，判断候选能否解释为合理的局部平地演示，哪些结构被省略。',
               '2. 区分白格与机器人有余量的安全连通区；较大面积不等于更有代表性或更真实。',
               '3. 选择包含实际转向或绕行意义的参考起终点，之后再做ROS实测。',
               '4. 大场景可能需要合并连续黑格以降低碰撞体数量；任何合并都必须保留几何一致性，不能通过删障碍换成功率。',
               '5. 正式验证表应记录真实action结果、用时和恢复次数，包括失败；当前所有候选的navigation_tested均为false。']
    (DEST/'README.md').write_text('\n'.join(readme))


if __name__=='__main__':
    main()
