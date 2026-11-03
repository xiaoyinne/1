"""Turn the exercise's binary Nav2 map into matching static Gazebo boxes.

XY comes from map.yaml. Ground is an artificial plane at simulation Z=0;
all black cells become uniform-height columns. Original vertical geometry and
measured ground support are not reconstructed. This file contains no robot.
"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from PIL import Image
import yaml


def child(parent, tag, value, **attributes):
    item = ET.SubElement(parent, tag, **attributes)
    item.text = str(value)
    return item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map', type=Path, default=Path(__file__).resolve().parent / 'scene_learning/map.yaml')
    parser.add_argument('--height', type=float, default=1.0, help='Artificial obstacle height in metres')
    args = parser.parse_args()
    if not np.isfinite(args.height) or args.height <= 0:
        parser.error('Height must be finite and positive')
    config = yaml.safe_load(args.map.read_text())
    resolution = float(config['resolution'])
    xmin, ymin, yaw = map(float, config['origin'])
    if not np.isfinite([resolution, xmin, ymin, yaw]).all() or resolution <= 0 or abs(yaw) > 1e-9:
        parser.error('This exercise requires positive resolution and a finite, zero-yaw map origin')
    if config.get('negate', 0) != 0:
        parser.error('This exercise expects negate=0')
    image_path = args.map.parent / config['image']
    pixels = np.asarray(Image.open(image_path).convert('L'))
    if not np.isin(pixels, [0, 254]).all():
        parser.error('This exercise expects the exported binary map with only values 0 and 254')
    # Image rows start at the top; our geometry rows start at minimum Y.
    occupied = np.flipud(pixels == 0)
    rows, cols = occupied.shape

    sdf = ET.Element('sdf', version='1.6')
    world = ET.SubElement(sdf, 'world', name='default')
    child(world, 'gravity', '0 0 -9.81')
    physics = ET.SubElement(world, 'physics', name='default_physics', type='ode')
    child(physics, 'max_step_size', '0.001')
    child(physics, 'real_time_update_rate', '1000')
    scene = ET.SubElement(world, 'scene')
    child(scene, 'ambient', '0.6 0.6 0.6 1')
    child(scene, 'shadows', 'false')
    light = ET.SubElement(world, 'light', name='sun', type='directional')
    child(light, 'pose', '0 0 10 0 0 0')
    child(light, 'diffuse', '0.8 0.8 0.8 1')
    child(light, 'direction', '-0.5 0.1 -1')

    floor = ET.SubElement(world, 'model', name='artificial_flat_ground')
    child(floor, 'static', 'true')
    floor_link = ET.SubElement(floor, 'link', name='ground')
    for kind in ('collision', 'visual'):
        item = ET.SubElement(floor_link, kind, name=f'floor_{kind}')
        plane = ET.SubElement(ET.SubElement(item, 'geometry'), 'plane')
        child(plane, 'normal', '0 0 1')
        child(plane, 'size', '100 100')
        if kind == 'visual':
            material = ET.SubElement(item, 'material')
            child(material, 'ambient', '0.65 0.65 0.65 1')
            child(material, 'diffuse', '0.65 0.65 0.65 1')

    obstacles = ET.SubElement(world, 'model', name='hilti_projected_cells')
    child(obstacles, 'static', 'true')
    link = ET.SubElement(obstacles, 'link', name='obstacles')
    for row, col in zip(*np.where(occupied)):
        # A grid index identifies a cell; geometry must use its centre.
        cx = xmin + (int(col) + 0.5) * resolution
        cy = ymin + (int(row) + 0.5) * resolution
        cz = args.height / 2
        for kind in ('collision', 'visual'):
            item = ET.SubElement(link, kind, name=f'cell_{row}_{col}_{kind}')
            child(item, 'pose', f'{cx:.8f} {cy:.8f} {cz:.8f} 0 0 0')
            box = ET.SubElement(ET.SubElement(item, 'geometry'), 'box')
            child(box, 'size', f'{resolution:.8f} {resolution:.8f} {args.height:.8f}')
            if kind == 'visual':
                material = ET.SubElement(item, 'material')
                child(material, 'ambient', '0.3 0.4 0.5 1')
                child(material, 'diffuse', '0.3 0.4 0.5 1')

    gui = ET.SubElement(world, 'gui', fullscreen='0')
    camera = ET.SubElement(gui, 'camera', name='user_camera')
    cx = xmin + cols * resolution / 2
    cy = ymin + rows * resolution / 2
    child(camera, 'pose', f'{cx:g} {cy-4:g} 7 0 1.05 1.5708')
    child(camera, 'view_controller', 'orbit')

    destination = args.map.parent / 'hilti_cells.world'
    ET.indent(sdf)
    ET.ElementTree(sdf).write(destination, encoding='utf-8', xml_declaration=True)
    info = {
        'map_yaml': str(args.map.resolve()),
        'map_image_sha256': hashlib.sha256(image_path.read_bytes()).hexdigest(),
        'world_sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
        'resolution_m': resolution, 'map_shape_rows_cols': [rows, cols],
        'map_origin_xy_yaw': [xmin, ymin, yaw],
        'obstacle_box_count': int(occupied.sum()), 'obstacle_height_m': args.height,
        'artificial_ground_simulation_z_m': 0.0,
        'construction': 'One matching visual and collision box per black map cell; no added perimeter wall.',
        'limitations': ['Ground is artificial, not detected or fitted to the point cloud.',
                        'Original heights, floors, stairs and slopes are not reconstructed.',
                        'White cells were below the slice-density threshold, not ray-verified free space.']}
    (args.map.parent / 'world_info.json').write_text(json.dumps(info, indent=2))
    print(f'Obstacle boxes: {int(occupied.sum())}')
    print(f'Each box: {resolution:g} x {resolution:g} x {args.height:g} m')
    print(f'Artificial ground: simulation Z=0')
    print(f'World: {destination}')
    print(f'Metadata: {args.map.parent / "world_info.json"}')


if __name__ == '__main__':
    main()
