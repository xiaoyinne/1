"""Shared, read-only checks for TUM trajectories and uncompressed binary PCD."""
import hashlib
import json
from pathlib import Path
import numpy as np


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def load_tum(path):
    values = np.loadtxt(path, ndmin=2)
    if values.shape[1] != 8 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError('TUM must contain >=2 finite rows of timestamp xyz qx qy qz qw')
    if np.any(np.diff(values[:, 0]) <= 0):
        raise ValueError('Trajectory timestamps must be strictly increasing; do not loop the bag')
    if not np.allclose(np.linalg.norm(values[:, 4:8], axis=1), 1, atol=1e-4):
        raise ValueError('Non-unit quaternion in trajectory')
    return values


def read_pcd(path):
    header = {}
    with Path(path).open('rb') as stream:
        for _ in range(100):
            line = stream.readline().decode('ascii').strip()
            if not line or line.startswith('#'):
                continue
            key, *values = line.split()
            header[key] = values
            if key == 'DATA':
                break
        else:
            raise ValueError('Missing PCD DATA header')
        if header['DATA'] != ['binary']:
            raise ValueError('This check supports uncompressed binary PCD only')
        fields = header['FIELDS']
        sizes = list(map(int, header['SIZE']))
        counts = list(map(int, header.get('COUNT', ['1'] * len(fields))))
        if not len(fields) == len(sizes) == len(counts) == len(header['TYPE']):
            raise ValueError('Inconsistent PCD field metadata')
        kinds = {'F': 'f', 'I': 'i', 'U': 'u'}
        dtype = np.dtype([(name, '<' + kinds[kind] + str(size), (count,))
                          for name, kind, size, count in zip(fields, header['TYPE'], sizes, counts)])
        points = int(header['POINTS'][0])
        if points <= 0 or int(header['WIDTH'][0]) * int(header['HEIGHT'][0]) != points:
            raise ValueError('Empty PCD or inconsistent point count')
        offset = stream.tell()
    if Path(path).stat().st_size - offset != points * dtype.itemsize:
        raise ValueError('PCD payload length does not match header')
    data = np.memmap(path, dtype=dtype, mode='r', offset=offset, shape=(points,))
    xyz = np.column_stack([data[key][:, 0] for key in ('x', 'y', 'z')])
    if not np.isfinite(xyz).all():
        raise ValueError('PCD contains non-finite XYZ')
    return header, xyz
