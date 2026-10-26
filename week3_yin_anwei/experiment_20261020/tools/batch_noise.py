import os
import csv
import json
import subprocess
from pathlib import Path

import numpy as np

base = Path(os.environ["RUN_DIR"])
tools = Path("/home/yaw/fastlio_week3/tools")
maps = Path("/home/yaw/fastlio_week3/maps")
runs = Path("/home/yaw/fastlio_week3/fixed_runs")
query = Path("/home/yaw/fastlio_week3/fixed_query_v1")

python = "/usr/bin/python3"
eval_python = "/home/yaw/week1_validation_20261010/venv-eval/bin/python"

sigmas = [0.05, 0.1, 0.2, 0.4]
seeds = [11, 22, 33]

logs = runs / "batch_logs"
logs.mkdir(parents=True, exist_ok=True)

env = os.environ.copy()
env["OMP_NUM_THREADS"] = "2"
env["OPENBLAS_NUM_THREADS"] = "1"

schedule = json.loads((query / "schedule.json").read_text())
expected_ns = schedule["selected_stamp_ns"]
expected_pairs = json.loads(
    (runs / "clean_v1/ate_report.json").read_text()
)["pairs"]

records = []
fields = [
    "sigma_m", "seed", "status",
    "attempts", "accepted", "ate_rmse_m", "message"
]

def execute(command, logfile, description):
    print("  " + description, flush=True)
    with logfile.open("a") as f:
        f.write("\nCOMMAND: " + " ".join(map(str, command)) + "\n")
        f.flush()
        result = subprocess.run(
            list(map(str, command)),
            stdout=f,
            stderr=subprocess.STDOUT,
            env=env,
        )
    if result.returncode != 0:
        raise RuntimeError(f"{description}失败，查看日志：{logfile}")

def save_status():
    with (runs / "batch_noise_status.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

for sigma in sigmas:
    for seed in seeds:
        label = f"{sigma:.2f}".replace(".", "p")
        name = f"noise_sigma{label}_seed{seed}"
        map_dir = maps / name
        output = runs / f"{name}_v1"
        logfile = logs / f"{name}.log"

        row = dict.fromkeys(fields, "")
        row.update(sigma_m=sigma, seed=seed)

        print(f"\n=== σ={sigma:g}米，种子{seed} ===", flush=True)

        try:
            # 地图已存在时检查参数，不覆盖。
            if map_dir.exists():
                metadata = json.loads((map_dir / "report.json").read_text())
                assert metadata["sigma_per_axis_m"] == sigma
                assert metadata["seed"] == seed
                assert (map_dir / "map.pcd").is_file()
                print("  复用已有地图", flush=True)
            else:
                execute(
                    [python, "-s", tools / "generate_noisy_map.py",
                     "--sigma", sigma, "--seed", seed],
                    logfile, "生成地图",
                )

            # 匹配目录不存在时才运行匹配。
            if not output.exists():
                execute(
                    [python, "-s", tools / "run_fixed_matching.py",
                     "--map", map_dir / "map.pcd", "--out", output],
                    logfile, "执行固定查询匹配",
                )

            # 检查已有结果是否完整且使用同一套输入、代码和参数。
            for filename in ["attempts.csv", "corrections.npz"]:
                if not (output / filename).is_file():
                    raise RuntimeError(
                        f"已有匹配目录不完整，保留现场待检查：{output}"
                    )

            assert (output / "schedule.json").read_bytes() == (
                query / "schedule.json"
            ).read_bytes(), "查询时间表不同"

            assert (output / "localization.yaml").read_bytes() == (
                base / "localization.yaml"
            ).read_bytes(), "匹配参数不同"

            assert (output / "frozen_matcher.py").read_bytes() == (
                base / "scripts/global_localization_synced.py"
            ).read_bytes(), "冻结定位代码不同"

            assert Path((output / "map_path.txt").read_text().strip()) == (
                map_dir / "map.pcd"
            ), "地图路径不符"

            with (output / "attempts.csv").open() as f:
                attempts = list(csv.DictReader(f))

            assert [int(x["stamp_ns"]) for x in attempts] == expected_ns
            accepted = sum(int(x["accepted"]) for x in attempts)

            with np.load(output / "corrections.npz") as data:
                assert len(data["stamp_ns"]) == accepted
                assert len(data["transforms"]) == accepted

            row.update(attempts=len(attempts), accepted=accepted)

            if accepted == 0:
                row.update(
                    status="no_initialization",
                    message="没有成功修正，不生成或伪造ATE",
                )
            else:
                if not (output / "trajectory_tum.txt").exists():
                    execute(
                        [python, "-s", tools / "fuse_fixed_trajectory.py",
                         "--run", output],
                        logfile, "生成定位轨迹",
                    )

                if not (output / "ate_report.json").exists():
                    execute(
                        [eval_python, tools / "evaluate_fixed_trajectory.py",
                         "--run", output],
                        logfile, "计算ATE",
                    )

                report = json.loads(
                    (output / "ate_report.json").read_text()
                )
                assert report["pairs"] == expected_pairs
                assert (output / "errors.csv").is_file()

                row.update(
                    status="complete",
                    ate_rmse_m=report["ATE_m"]["rmse"],
                )
                print(
                    f"  完成：接受{accepted}/{len(attempts)}次，"
                    f"ATE RMSE={report['ATE_m']['rmse']:.6f}米",
                    flush=True,
                )

        except Exception as error:
            row.update(
                status="error",
                message=f"{type(error).__name__}: {error}",
            )
            print("  未完成：" + row["message"], flush=True)

        records.append(row)
        save_status()

complete = sum(r["status"] == "complete" for r in records)
print(f"\n噪声实验完成：{complete}/{len(records)}组", flush=True)
print("状态表：", runs / "batch_noise_status.csv", flush=True)

if complete == len(records):
    execute(
        [python, "-s", tools / "summarize_noise.py"],
        logs / "summary.log", "更新汇总表",
    )
    execute(
        [eval_python, tools / "plot_noise_levels.py"],
        logs / "plot.log", "更新噪声曲线",
    )
    print("全部完成，图片：", runs / "noise_levels.png", flush=True)
else:
    print("存在未完成组，先检查状态表；暂不更新汇总图。", flush=True)
