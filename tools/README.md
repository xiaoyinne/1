# 工具入口

所有工具都可用 `--help` 查看参数。完整执行顺序和样例见根目录 [REPRODUCE.md](../REPRODUCE.md)。

| 工具 | Python 环境 | 输入 → 输出 |
|---|---|---|
| `convert_bag.py` | venv-bag | ROS1 bag → ROS2 bag、Humble QoS 兼容 metadata、转换记录 |
| `verify_fastlio_save.py` | source ROS 后 `/usr/bin/python3 -s` | 工作区、配置、bag → 独立运行目录中的地图、轨迹、配置和日志 |
| `export_trajectory.py` | venv-eval | TUM → KITTI 12 列矩阵、对应时间戳 |
| `run_evo.py` | venv-eval | 标准 evo APE 命令行 → 误差统计、ZIP、图 |
| `evaluation_scope.py` | venv-eval | 真值和估计 TUM → 匹配范围/尾段/ATE JSON、标注图 |
| `check_results.py` | venv-eval | PCD、TUM、可选 KITTI/时间戳/日志 → 文件一致性报告 |
| `render_map.py` | venv-eval | PCD → 俯视和局部 XY 投影、显示参数 |
| `runtime_report.py` | venv-eval 或 Python 3 标准库 | 带节点计数的运行清单 → 输入、处理、输出采集的计数对账 |
| `common.py` | venv-eval | 供其他脚本调用的 PCD/TUM 只读解析及 SHA256 |

运行轻量测试：

```bash
"$EVAL_PY" -m unittest discover -s "$REPO/tools/tests" -v
```

6 项测试覆盖已知旋转/平移的 KITTI 导出、拒绝覆盖、重复时间戳、无效四元数、任意 PCD 字段顺序和损坏的 PCD 数据长度，以及输入/处理/输出计数的区分和缺少计数时拒绝误报。实际回放与下载验证见 [VALIDATION.md](../VALIDATION.md)。

`verify_fastlio_save.py` 还会记录进程采样 CPU/RSS。应用额外的运行诊断补丁后，可设置 `--lidar-depth`、`--imu-depth`、`--lidar-reliability`，并提取节点计数到运行清单。补丁默认保留旧 QoS；使用步骤、兼容性和各计数的限制见 [RUNTIME_DIAGNOSTICS.md](../RUNTIME_DIAGNOSTICS.md)。
