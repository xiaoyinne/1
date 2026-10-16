from pathlib import Path
import sys
import json
import hashlib
import time
import numpy as np

root = Path("/mnt/d/nclt_student3")
date = "2012-01-08"

repo = Path(
    "/home/yaw/fastlio_week2/scancontext/vendor/PyICP-SLAM-master"
)
sys.path.insert(0, str(repo))
from utils.ScanContextManager import ptcloud2sc, sc2rk

# 1. 读取已核验的帧清单，只使用时间戳。
reference_path = (
    root / "reference_audit" / f"{date}_scan_reference.npz"
)
with np.load(reference_path, allow_pickle=False) as reference:
    stamps = reference["stamps_us"].astype(np.int64).copy()

assert len(stamps) > 0
assert np.all(np.diff(stamps) > 0), "时间戳不严格递增"

out = root / "descriptors_v1" / date
if out.exists():
    raise SystemExit(f"输出目录已存在，未覆盖：{out}")

# 先检查输入文件齐全，再开始计算。
files = [
    root / date / "velodyne_sync" / f"{int(t)}.bin"
    for t in stamps
]
missing = [str(p) for p in files if not p.is_file()]
if missing:
    raise SystemExit(f"缺少点云文件，例如：{missing[0]}")

out.mkdir(parents=True)

dtype = np.dtype([
    ("x", "<u2"),
    ("y", "<u2"),
    ("z", "<u2"),
    ("intensity", "u1"),
    ("laser", "u1"),
])

descriptors = []
ring_keys = []
point_counts = []
active_sectors = []
started = time.perf_counter()

print("建库日期：", date, flush=True)
print("待处理帧数：", len(files), flush=True)

# 2. 对每帧重复刚才已经理解的处理过程。
for number, file in enumerate(files, start=1):
    assert file.stat().st_size % 8 == 0, f"文件长度异常：{file}"
    raw = np.fromfile(file, dtype=dtype)

    xyz = np.column_stack([
        raw["x"], raw["y"], raw["z"]
    ]).astype(np.float64)

    xyz = xyz * 0.005 - 100.0
    xyz *= np.array([1.0, -1.0, -1.0])

    radius = np.linalg.norm(xyz[:, :2], axis=1)
    points = xyz[
        np.isfinite(xyz).all(axis=1)
        & (radius > 1.0)
        & (radius < 80.0)
    ]
    assert len(points) > 0, f"筛选后为空：{file}"

    sc = ptcloud2sc(points.copy(), [20, 60], 80)
    rk = sc2rk(sc)
    active = int(np.sum(np.linalg.norm(sc, axis=0) > 0))

    assert sc.shape == (20, 60)
    assert rk.shape == (20,)
    assert np.isfinite(sc).all()
    assert np.isfinite(rk).all()
    assert active > 0, f"描述子没有有效扇区：{file}"

    descriptors.append(sc)
    ring_keys.append(rk)
    point_counts.append(len(points))
    active_sectors.append(active)

    if number % 50 == 0 or number == len(files):
        elapsed = time.perf_counter() - started
        print(
            f"已处理 {number}/{len(files)} 帧，"
            f"已用时 {elapsed:.1f} 秒",
            flush=True,
        )

# 3. 按相同顺序保存，确保时间戳与描述子一一对应。
descriptors = np.stack(descriptors)
ring_keys = np.stack(ring_keys)

np.savez_compressed(
    out / "descriptors.npz",
    stamps_us=stamps,
    descriptors=descriptors,
    ring_keys=ring_keys,
    point_counts=np.asarray(point_counts, dtype=np.int64),
    active_sectors=np.asarray(active_sectors, dtype=np.int64),
)

report = {
    "date": date,
    "role": "historical database",
    "frames": len(stamps),
    "descriptor_shape": list(descriptors.shape),
    "ring_key_shape": list(ring_keys.shape),
    "input_frame": "body FRD converted to body FLU",
    "horizontal_range_m": [1.0, 80.0],
    "height_offset_m": 2.0,
    "upstream_max_points_per_cell": 500,
    "used_points_min": min(point_counts),
    "used_points_max": max(point_counts),
    "active_sectors_min": min(active_sectors),
    "active_sectors_max": max(active_sectors),
    "elapsed_s": round(time.perf_counter() - started, 2),
    "selection": "Previously validated reference-node scan timestamps",
    "reference_positions_used_in_descriptor": False,
    "reference_file_sha256": hashlib.sha256(
        reference_path.read_bytes()
    ).hexdigest(),
    "module_sha256": hashlib.sha256(
        (repo / "utils/ScanContextManager.py").read_bytes()
    ).hexdigest(),
    "script_sha256": hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest(),
}

(out / "report.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False),
    encoding="utf-8",
)

print("\n建库完成：", out)
print(json.dumps(report, indent=2, ensure_ascii=False))
