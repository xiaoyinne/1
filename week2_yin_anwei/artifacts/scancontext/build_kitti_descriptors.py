from pathlib import Path
import sys
import json
import hashlib
import time
import numpy as np

base = Path("/home/yaw/fastlio_week2/scancontext")
repo = base / "vendor/PyICP-SLAM-master"
sys.path.insert(0, str(repo))
from utils.ScanContextManager import ptcloud2sc, sc2rk

reference_path = base / "runs/kitti0020_reference_v2/reference.npz"
reference = np.load(reference_path, allow_pickle=False)
out = base / "runs/kitti0020_descriptors_v1"

if out.exists():
    raise RuntimeError(f"输出目录已存在，未覆盖：{out}")

# 在参考位姿有效范围内，按固定帧号间隔采样。
selected = np.flatnonzero(
    reference["valid"] & (reference["ids"] % 5 == 0)
)
assert len(selected) > 0

descriptors = []
ring_keys = []
counts = []
sectors = []
valid = []
start = time.perf_counter()

for number, i in enumerate(selected, 1):
    path = Path(str(reference["lidar_files"][i]))
    raw = np.fromfile(path, dtype="<f4")
    assert raw.size % 4 == 0, f"点云格式异常：{path}"
    points = raw.reshape(-1, 4)[:, :3].copy()
    radius = np.linalg.norm(points[:, :2], axis=1)
    points = points[
        np.isfinite(points).all(axis=1)
        & (radius > 1.0)
        & (radius < 80.0)
    ]

    sc = ptcloud2sc(points.copy(), [20, 60], 80)
    rk = sc2rk(sc)
    assert sc.shape == (20, 60)
    assert rk.shape == (20,)
    assert np.isfinite(sc).all() and np.isfinite(rk).all()

    active = int(np.sum(np.linalg.norm(sc, axis=0) > 0))
    descriptors.append(sc)
    ring_keys.append(rk)
    counts.append(len(points))
    sectors.append(active)
    valid.append(active > 0)

    if number % 20 == 0 or number == len(selected):
        print(f"已处理 {number}/{len(selected)} 帧", flush=True)

def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

ids = reference["ids"][selected]
valid = np.array(valid, dtype=bool)
report = {
    "sequence": "2011_09_30_drive_0020_sync",
    "frames": len(selected),
    "sampling": "frame_id % 5 == 0, within reference time support",
    "rings": 20,
    "sectors": 60,
    "radial_filter_m": "1 < horizontal radius < 80",
    "height_offset_m": 2.0,
    "height_offset_note": "Inherited from upstream implementation",
    "input_frame": "Velodyne lidar",
    "valid_descriptors": int(valid.sum()),
    "invalid_ids": ids[~valid].tolist(),
    "used_points_min": int(min(counts)),
    "used_points_max": int(max(counts)),
    "active_sectors_min": int(min(sectors)),
    "active_sectors_max": int(max(sectors)),
    "elapsed_s": round(time.perf_counter() - start, 3),
    "module_sha256": sha256(repo / "utils/ScanContextManager.py"),
    "reference_sha256": sha256(reference_path),
    "script_sha256": sha256(Path(__file__)),
}

out.mkdir(parents=True, exist_ok=False)
np.savez_compressed(
    out / "descriptors.npz",
    ids=ids,
    stamps_ns=reference["scan_stamps_ns"][selected],
    descriptors=np.array(descriptors),
    ring_keys=np.array(ring_keys),
    valid=valid,
    used_points=np.array(counts),
    active_sectors=np.array(sectors),
)
(out / "manifest.json").write_text(json.dumps(report, indent=2))
print("\n输出目录：", out)
print(json.dumps(report, indent=2))
