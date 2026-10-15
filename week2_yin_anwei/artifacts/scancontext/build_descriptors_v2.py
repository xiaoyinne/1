from pathlib import Path
import sys
import csv
import json
import hashlib
import time
import numpy as np
import open3d as o3d

base = Path("/home/yaw/fastlio_week2/scancontext")
repo = base / "vendor/PyICP-SLAM-master"
root = base / "runs/raw_20261013_193630/keyframes_v1"
out = root / "descriptors_v2"

sys.path.insert(0, str(repo))
from utils.ScanContextManager import ptcloud2sc, sc2rk

source = repo / "utils/ScanContextManager.py"
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
expected = "956938ea658270e7908a9e047e69bb0010d0a0f8efa70cb50e46ec44e1f24c72"
assert source_hash == expected, "模块版本与刚才测试的版本不一致"

with (root / "index.csv").open() as f:
    rows = list(csv.DictReader(f))
assert rows, "索引为空"
out.mkdir(exist_ok=False)

descriptors = []
ring_keys = []
valid = []
used_points = []
active_sectors = []
started = time.perf_counter()

for i, row in enumerate(rows):
    points = np.asarray(
        o3d.io.read_point_cloud(str(root / row["pcd"])).points
    )
    assert len(points) == int(row["points"]), "点数与索引不一致"
    radius = np.linalg.norm(points[:, :2], axis=1)
    mask = np.isfinite(points).all(axis=1) & (radius > 0) & (radius < 25)
    selected = points[mask]

    sc = ptcloud2sc(selected, [20, 60], 25)
    rk = sc2rk(sc)
    assert sc.shape == (20, 60) and rk.shape == (20,)
    assert np.isfinite(sc).all() and np.isfinite(rk).all()

    descriptors.append(sc)
    ring_keys.append(rk)
    valid.append(bool(np.any(sc)))
    used_points.append(len(selected))
    active_sectors.append(int(np.count_nonzero(np.linalg.norm(sc, axis=0))))

    if (i + 1) % 20 == 0 or i + 1 == len(rows):
        print(f"已处理 {i + 1}/{len(rows)} 帧", flush=True)

np.savez_compressed(
    out / "descriptors.npz",
    ids=np.array([int(r["id"]) for r in rows], dtype=np.int64),
    stamps_ns=np.array([int(r["stamp_ns"]) for r in rows], dtype=np.int64),
    descriptors=np.stack(descriptors),
    ring_keys=np.stack(ring_keys),
    valid=np.array(valid, dtype=bool),
    used_points=np.array(used_points),
    active_sectors=np.array(active_sectors),
)

report = {
    "frames": len(rows),
    "valid_descriptors": sum(valid),
    "invalid_ids": [int(r["id"]) for r, ok in zip(rows, valid) if not ok],
    "descriptor_shape": [len(rows), 20, 60],
    "rings": 20,
    "sectors": 60,
    "radial_filter_m": "0 < radius < 25",
    "height_offset_m": 2.0,
    "input_frame": "body",
    "used_points_min": min(used_points),
    "used_points_max": max(used_points),
    "active_sectors_min": min(active_sectors),
    "active_sectors_max": max(active_sectors),
    "elapsed_s": round(time.perf_counter() - started, 3),
    "module_sha256": source_hash,
    "index_sha256": hashlib.sha256((root / "index.csv").read_bytes()).hexdigest(),
    "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
}
(out / "manifest.json").write_text(json.dumps(report, indent=2))
print("输出目录：", out)
print(json.dumps(report, indent=2))
