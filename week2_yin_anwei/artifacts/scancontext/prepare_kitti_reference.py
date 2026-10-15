from pathlib import Path
import json
import numpy as np
from scipy.spatial.transform import Rotation

base = Path("/home/yaw/fastlio_week2/scancontext")
day = base / "data/kitti_raw/2011_09_30"
seq = day / "2011_09_30_drive_0020_sync"
out = base / "runs/kitti0020_reference_v1"

lidar = sorted((seq / "velodyne_points/data").glob("*.bin"))
oxts = sorted((seq / "oxts/data").glob("*.txt"))
assert len(lidar) == len(oxts) == 1104
assert [p.stem for p in lidar] == [p.stem for p in oxts]

def timestamps(path):
    lines = path.read_text().splitlines()
    return np.array([
        np.datetime64(s.strip().replace(" ", "T"), "ns").astype(np.int64)
        for s in lines if s.strip()
    ], dtype=np.int64)

scan_ns = timestamps(seq / "velodyne_points/timestamps.txt")
oxts_ns = timestamps(seq / "oxts/timestamps.txt")
assert len(scan_ns) == len(oxts_ns) == len(lidar)
assert np.all(np.diff(scan_ns) > 0)
assert np.all(np.diff(oxts_ns) > 0)

packets = np.array([np.loadtxt(p).reshape(-1) for p in oxts])
assert packets.shape == (1104, 30)
assert np.isfinite(packets).all()

calib = {}
for line in (day / "calib_imu_to_velo.txt").read_text().splitlines():
    key, value = line.split(":", 1)
    if key in ("R", "T"):
        calib[key] = np.array([float(x) for x in value.split()])

# T_velo_imu 将 IMU 坐标中的点变换到雷达坐标。
T_velo_imu = np.eye(4)
T_velo_imu[:3, :3] = calib["R"].reshape(3, 3)
T_velo_imu[:3, 3] = calib["T"]
assert np.allclose(
    T_velo_imu[:3, :3].T @ T_velo_imu[:3, :3],
    np.eye(3), atol=1e-5
)

lat, lon, alt = packets[:, 0], packets[:, 1], packets[:, 2]
scale = np.cos(np.deg2rad(lat[0]))
earth_radius = 6378137.0
xyz = np.column_stack([
    scale * earth_radius * np.deg2rad(lon),
    scale * earth_radius * np.log(np.tan(np.deg2rad(90 + lat) / 2)),
    alt,
])
xyz -= xyz[0].copy()

T_world_imu = np.repeat(np.eye(4)[None], len(packets), axis=0)
# 小写 xyz 为外禀旋转，对应 Rz(yaw) @ Ry(pitch) @ Rx(roll)。
T_world_imu[:, :3, :3] = Rotation.from_euler(
    "xyz", packets[:, 3:6]
).as_matrix()
T_world_imu[:, :3, 3] = xyz

T_world_velo = T_world_imu @ np.linalg.inv(T_velo_imu)
poses = np.linalg.inv(T_world_velo[0]) @ T_world_velo
assert np.allclose(poses[0], np.eye(4), atol=1e-8)

positions = poses[:, :3, 3]
elapsed = (scan_ns - scan_ns[0]) / 1e9
nearest = []
for q in range(len(lidar)):
    history = np.flatnonzero((scan_ns[q] - scan_ns) >= 30_000_000_000)
    if not len(history):
        continue
    distances = np.linalg.norm(positions[history] - positions[q], axis=1)
    k = int(np.argmin(distances))
    c = int(history[k])
    nearest.append({
        "query_id": q,
        "candidate_id": c,
        "distance_m": float(distances[k]),
        "time_gap_s": float((scan_ns[q] - scan_ns[c]) / 1e9),
    })

near = [r for r in nearest if r["distance_m"] <= 5.0]
near.sort(key=lambda r: r["distance_m"])
time_gaps = np.abs(scan_ns - oxts_ns) / 1e6

report = {
    "sequence": str(seq),
    "frames": len(lidar),
    "duration_s": float(elapsed[-1]),
    "reference": "OXTS pose at same-index packet; expressed in first lidar frame",
    "pose_interpolated_to_scan_time": False,
    "scan_oxts_time_gap_ms_median": float(np.median(time_gaps)),
    "scan_oxts_time_gap_ms_max": float(time_gaps.max()),
    "queries_with_history_after_30s": len(nearest),
    "queries_with_history_within_5m": len(near),
    "near_examples": near[:20],
    "note": "Position proximity is diagnostic, not a verified loop closure.",
}

# 防止意外覆盖之前的结果。
out.mkdir(parents=True, exist_ok=False)
np.savez_compressed(
    out / "reference.npz",
    ids=np.arange(len(lidar)),
    scan_stamps_ns=scan_ns,
    oxts_stamps_ns=oxts_ns,
    T_reference_velo=poses,
    lidar_files=np.array([str(p) for p in lidar]),
)
(out / "report.json").write_text(json.dumps(report, indent=2))

print("输出目录：", out)
print("帧数：", len(lidar))
print("扫描时间跨度：", round(elapsed[-1], 3), "秒")
print("同编号扫描/OXTS 时间差中位数/最大值：",
      round(float(np.median(time_gaps)), 3),
      round(float(time_gaps.max()), 3), "毫秒")
print("有 30 秒前历史帧的查询数：", len(nearest))
print("其中存在 5 米内历史帧的查询数：", len(near))
print("\n位置最近的 10 组：")
for r in near[:10]:
    print(
        f'{r["query_id"]}->{r["candidate_id"]}：'
        f'距离={r["distance_m"]:.3f}m，'
        f'时间差={r["time_gap_s"]:.1f}s'
    )
