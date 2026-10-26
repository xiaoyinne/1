"""Student 3 tutorial: run the fixed-query block-deletion experiment matrix.

Run with the existing venv-eval Python after sourcing ROS2 and exporting RUN_DIR.
This script prepares data through the user's existing helpers. It never starts
bag playback or FAST-LIO. Missing evaluation poses are reported, not discarded.
"""
import argparse
import copy
import csv
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from statistics import median

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from evo.core import metrics
from evo.tools import file_interface


ROOT = Path("/home/yaw/fastlio_week3")
SYSTEM_PYTHON = "/usr/bin/python3"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def save_json(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )


def run_command(command, log, description, environment):
    print("  " + description, flush=True)
    with log.open("a", encoding="utf-8") as stream:
        stream.write("\nCOMMAND: " + " ".join(map(str, command)) + "\n")
        stream.flush()
        result = subprocess.run(
            list(map(str, command)), stdout=stream,
            stderr=subprocess.STDOUT, env=environment,
        )
    if result.returncode:
        raise RuntimeError(f"{description}失败；详细日志：{log}")


def longest_gap(stamps, start, end):
    stamps = np.asarray(stamps, dtype=np.int64)
    if np.any(np.diff(stamps) <= 0):
        raise ValueError("成功修正的时间戳没有严格递增")
    if np.any((stamps < start) | (stamps > end)):
        raise ValueError("成功修正时间戳超出完整前端范围")
    anchors = np.concatenate((
        np.array([start], dtype=np.int64), stamps,
        np.array([end], dtype=np.int64),
    ))
    return float(np.diff(anchors).max() / 1e9)


def evaluate(run, gt, sample):
    """Report coverage first; only compute main ATE on ALL fixed samples."""
    trajectory = file_interface.read_tum_trajectory_file(
        str(run / "trajectory_tum.txt")
    )
    if np.any(np.diff(trajectory.timestamps) <= 0):
        raise ValueError("定位轨迹时间戳未严格递增")
    indices = np.searchsorted(trajectory.timestamps, sample.timestamps)
    present = indices < trajectory.num_poses
    present[present] = (
        trajectory.timestamps[indices[present]] == sample.timestamps[present]
    )
    count = int(present.sum())
    result = {
        "fixed_pairs": int(sample.num_poses),
        "evaluated_pairs": count,
        "coverage": count / sample.num_poses,
        "output_poses": int(trajectory.num_poses),
        "ATE_m": None,
    }
    if not np.all(present):
        result["status"] = "incomplete_coverage"
        return result

    matched = copy.deepcopy(trajectory)
    matched.reduce_to_ids(indices.tolist())
    rotation, translation, scale = matched.align(gt, correct_scale=False)
    ape = metrics.APE(metrics.PoseRelation.translation_part)
    ape.process_data((gt, matched))
    result.update(
        status="complete",
        ATE_m={key: float(value) for key, value in ape.get_all_statistics().items()},
        alignment_rotation=rotation.tolist(),
        alignment_translation=translation.tolist(),
        alignment_scale=float(scale),
    )
    # Existing results stay untouched; this is a derived deletion-specific file.
    np.savetxt(
        run / "deletion_errors.csv",
        np.column_stack((matched.timestamps, ape.error)), delimiter=",",
        header="timestamp,translation_error_m", comments="",
        fmt=["%.9f", "%.9f"],
    )
    old_report = run / "ate_report.json"
    if old_report.exists():
        old = json.loads(old_report.read_text())
        if old["pairs"] != sample.num_poses or abs(
            old["ATE_m"]["rmse"] - result["ATE_m"]["rmse"]
        ) > 1e-8:
            raise ValueError("重新计算与已有ATE不一致，保留文件待检查")
    return result


FIELDS = [
    "run", "deleted_block_fraction", "actual_deleted_point_fraction", "seed",
    "status", "attempts", "accepted", "acceptance", "output_poses",
    "fixed_pairs", "evaluated_pairs", "coverage", "ate_rmse_m",
    "max_correction_gap_s", "message",
]


def save_table(root, rows):
    with (root / "deletion_summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def plot_results(root, rows, ratios, baseline):
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
    panels = [
        ("ate_rmse_m", "Aligned translation ATE RMSE (m)"),
        ("acceptance", "Accepted corrections / 53 attempts"),
        ("coverage", "Fixed GT sample coverage"),
        ("max_correction_gap_s", "Longest correction gap, full query (s)"),
    ]
    for ax, (key, label) in zip(axes.flat, panels):
        xs = [0.0] + ratios
        centers, minima, maxima = [baseline[key]], [baseline[key]], [baseline[key]]
        for ratio in ratios:
            values = [
                float(row[key]) for row in rows
                if row["deleted_block_fraction"] == ratio and row[key] != ""
            ]
            centers.append(median(values) if values else np.nan)
            minima.append(min(values) if values else np.nan)
            maxima.append(max(values) if values else np.nan)
        ax.plot(xs, centers, "ko-", label="Median; clean map at zero")
        ax.fill_between(xs, minima, maxima, alpha=0.18, label="Seed min-max range")
        for seed in sorted({row["seed"] for row in rows}):
            subset = [row for row in rows if row["seed"] == seed and row[key] != ""]
            ax.scatter(
                [row["deleted_block_fraction"] for row in subset],
                [float(row[key]) for row in subset], s=25, label=f"Seed {seed}",
            )
        if key == "ate_rmse_m":
            lines = ["ATE requires all fixed samples; valid runs:"]
            for ratio in ratios:
                group = [row for row in rows if row["deleted_block_fraction"] == ratio]
                valid = sum(row["ate_rmse_m"] != "" for row in group)
                lines.append(f"p={ratio:g}: {valid}/{len(group)}")
            ax.text(
                0.02, 0.97, "\n".join(lines), transform=ax.transAxes,
                va="top", fontsize=8,
                bbox=dict(facecolor="white", alpha=0.8, edgecolor="none"),
            )
        if key in ("coverage", "acceptance"):
            ax.set_ylim(-0.04, 1.06)
        ax.set_xlabel("Deleted occupied 3D block fraction")
        ax.set_ylabel(label)
        ax.set_xticks(xs)
        ax.grid(alpha=0.25)
        if key == "acceptance":
            ax.legend(fontsize=8, loc="best")
    fig.suptitle(
        "Fixed-query block deletion | median and observed seed range, not confidence intervals\n"
        "Missing ATE is not zero; full-query correction gaps and GT-window ATE differ in scope"
    )
    fig.savefig(root / "deletion_curves.png", dpi=180)
    fig.savefig(root / "deletion_curves.svg")
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ratios", nargs="+", type=float, default=[0.1, 0.25, 0.5, 0.75, 0.9])
    parser.add_argument("--seeds", nargs="+", type=int, default=[11, 22, 33])
    args = parser.parse_args()
    ratios = sorted(set(args.ratios))
    seeds = sorted(set(args.seeds))
    if any(not np.isfinite(p) or not 0 < p < 1 or abs(p-round(p, 2)) > 1e-9 for p in ratios):
        parser.error("删除比例须在0与1之间，最多两位小数；本脚本不生成空地图")
    if any(seed < 0 for seed in seeds):
        parser.error("随机种子不能为负数")
    if "RUN_DIR" not in os.environ:
        parser.error("请先export RUN_DIR为原在线基线目录")

    base = Path(os.environ["RUN_DIR"])
    root = ROOT / "delete_runs"
    logs = root / "batch_logs"
    logs.mkdir(parents=True, exist_ok=True)
    tools = ROOT / "tools"
    frozen = root / "batch_sources"
    frozen.mkdir(exist_ok=True)
    helper_names = ["generate_deleted_map.py", "run_fixed_matching.py", "fuse_fixed_trajectory.py"]
    query = ROOT / "fixed_query_v1"
    clean = ROOT / "fixed_runs/clean_v1"
    original_map = Path("/mnt/d/chromeDownload/fastlio_hilti_fixed_20261008.pcd")
    original_hash = sha(original_map)
    if original_hash != (base / "map_sha256.txt").read_text().split()[0]:
        raise ValueError("原地图哈希与基线不一致，请先检查")

    # Prevent reuse after changing cached inputs, algorithm or configuration.
    manifest = {
        "original_map_sha256": original_hash,
        "config_sha256": sha(base / "localization.yaml"),
        "matcher_sha256": sha(base / "scripts/global_localization_synced.py"),
        "schedule_sha256": sha(query / "schedule.json"),
        "odometry_sha256": sha(query / "odometry.npz"),
        "sample_sha256": sha(base / "common_eval/localization_matched.txt"),
        "gt_sha256": sha(base / "common_eval/gt_matched.txt"),
        "scan_sha256": {p.name: sha(p) for p in sorted((query / "scans").glob("*.npy"))},
        "helper_sha256": {name: sha(tools / name) for name in helper_names},
        "block_size_m": 3.0,
    }
    manifest_file = root / "batch_inputs.json"
    if manifest_file.exists() and json.loads(manifest_file.read_text()) != manifest:
        raise ValueError("输入或工具与之前批处理不同，停止复用；请保留结果后检查差异")
    save_json(manifest_file, manifest)
    for name in helper_names:
        shutil.copy2(tools / name, frozen / name)

    schedule = json.loads((query / "schedule.json").read_text())["selected_stamp_ns"]
    if len(schedule) != 53:
        raise ValueError("本教程预期53次固定匹配，时间表已变化")
    gt = file_interface.read_tum_trajectory_file(str(base / "common_eval/gt_matched.txt"))
    sample = file_interface.read_tum_trajectory_file(str(base / "common_eval/localization_matched.txt"))
    if gt.num_poses != sample.num_poses:
        raise ValueError("共同评价文件长度不一致")
    with np.load(query / "odometry.npz") as data:
        start, end = int(data["stamp_ns"][0]), int(data["stamp_ns"][-1])
    with np.load(clean / "corrections.npz") as data:
        clean_stamps = data["stamp_ns"].copy()
    clean_ate = json.loads((clean / "ate_report.json").read_text())
    baseline = {
        "ate_rmse_m": clean_ate["ATE_m"]["rmse"],
        "acceptance": len(clean_stamps) / len(schedule), "coverage": 1.0,
        "max_correction_gap_s": longest_gap(clean_stamps, start, end),
    }
    environment = os.environ.copy()
    environment.update(OMP_NUM_THREADS="2", OPENBLAS_NUM_THREADS="1")
    records = []

    for ratio in ratios:
        for seed in seeds:
            name = f"delete_block3m_ratio{ratio:.2f}_seed{seed}".replace(".", "p")
            map_dir = ROOT / "maps" / name
            run = root / (name + "_v1")
            log = logs / (name + ".log")
            row = dict.fromkeys(FIELDS, "")
            row.update(run=run.name, deleted_block_fraction=ratio, seed=seed,
                       fixed_pairs=int(sample.num_poses))
            print(f"\n=== 删除{ratio:.0%}空间块，种子{seed} ===", flush=True)
            try:
                if not map_dir.exists():
                    run_command(
                        [SYSTEM_PYTHON, "-s", frozen / "generate_deleted_map.py",
                         "--ratio", ratio, "--seed", seed, "--block", 3],
                        log, "生成删块地图", environment,
                    )
                metadata = json.loads((map_dir / "report.json").read_text())
                if (metadata["requested_deleted_block_fraction"] != ratio
                    or metadata["seed"] != seed or metadata["block_size_m"] != 3
                    or not (map_dir / "map.pcd").is_file()):
                    raise ValueError("已有地图缺失或参数不符")
                row["actual_deleted_point_fraction"] = metadata["actual_deleted_point_fraction"]
                map_hash = sha(map_dir / "map.pcd")

                if not run.exists():
                    run_command(
                        [SYSTEM_PYTHON, "-s", frozen / "run_fixed_matching.py",
                         "--map", map_dir / "map.pcd", "--out", run],
                        log, "执行固定匹配", environment,
                    )
                if (run / "schedule.json").read_bytes() != (query / "schedule.json").read_bytes():
                    raise ValueError("运行的时间表不同")
                if (run / "localization.yaml").read_bytes() != (base / "localization.yaml").read_bytes():
                    raise ValueError("运行的定位参数不同")
                if sha(run / "frozen_matcher.py") != manifest["matcher_sha256"]:
                    raise ValueError("冻结定位代码不同")
                if Path((run / "map_path.txt").read_text().strip()) != map_dir / "map.pcd":
                    raise ValueError("匹配地图路径不同")
                with (run / "attempts.csv").open() as stream:
                    attempts = list(csv.DictReader(stream))
                if [int(x["stamp_ns"]) for x in attempts] != schedule:
                    raise ValueError("实际尝试时间戳与固定时间表不同")
                accepted = sum(int(x["accepted"]) for x in attempts)
                with np.load(run / "corrections.npz") as data:
                    stamps = data["stamp_ns"].copy()
                    if len(stamps) != accepted or len(data["transforms"]) != accepted:
                        raise ValueError("接受数量与保存的修正数量不同")
                if stamps.tolist() != [int(x["stamp_ns"]) for x in attempts if int(x["accepted"]) == 1]:
                    raise ValueError("接受标志与修正时间戳不一致")
                row.update(
                    attempts=len(attempts), accepted=accepted,
                    acceptance=accepted/len(attempts),
                    max_correction_gap_s=longest_gap(stamps, start, end),
                )
                if accepted:
                    if not (run / "trajectory_tum.txt").exists():
                        run_command(
                            [SYSTEM_PYTHON, "-s", frozen / "fuse_fixed_trajectory.py", "--run", run],
                            log, "生成定位轨迹", environment,
                        )
                    report = evaluate(run, gt, sample)
                else:
                    report = dict(
                        status="no_localization", fixed_pairs=int(sample.num_poses),
                        evaluated_pairs=0, coverage=0.0, output_poses=0, ATE_m=None,
                    )
                report.update(
                    actual_deleted_point_fraction=metadata["actual_deleted_point_fraction"],
                    requested_deleted_block_fraction=ratio, seed=seed,
                    map_sha256=map_hash, attempts=len(attempts), accepted=accepted,
                    max_correction_gap_s=row["max_correction_gap_s"],
                    query_span_s=(end-start)/1e9,
                )
                previous = run / "deletion_report.json"
                if previous.exists() and json.loads(previous.read_text())["map_sha256"] != map_hash:
                    raise ValueError("地图哈希与此前评价记录不同，停止复用")
                save_json(previous, report)
                row.update(
                    status=report["status"], output_poses=report["output_poses"],
                    evaluated_pairs=report["evaluated_pairs"], coverage=report["coverage"],
                )
                if report["ATE_m"] is not None:
                    row["ate_rmse_m"] = report["ATE_m"]["rmse"]
                    print(f"  完整评价：ATE={row['ate_rmse_m']:.6f}米", flush=True)
                else:
                    print(f"  {row['status']}：覆盖{report['evaluated_pairs']}/{sample.num_poses}，ATE留空", flush=True)
                print(f"  接受{accepted}/53，最长修正间隔{row['max_correction_gap_s']:.3f}秒", flush=True)
            except Exception as error:
                row.update(status="error", message=f"{type(error).__name__}: {error}")
                print("  处理出错：" + row["message"], flush=True)
            records.append(row)
            save_table(root, records)

    save_json(root / "deletion_baseline.json", baseline)
    plot_results(root, records, ratios, baseline)
    print("\n=== 处理结束 ===", flush=True)
    for status in ["complete", "incomplete_coverage", "no_localization", "error"]:
        print(f"{status}: {sum(row['status'] == status for row in records)}组", flush=True)
    print("汇总表：", root / "deletion_summary.csv", flush=True)
    print("曲线：", root / "deletion_curves.png", flush=True)
    print("ATE空白不等于误差为零；error状态须检查日志。", flush=True)


if __name__ == "__main__":
    main()
