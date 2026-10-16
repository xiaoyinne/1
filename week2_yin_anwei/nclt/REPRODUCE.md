# 运行顺序与验证范围

本包保留实测脚本原字节，不擅自替换运行路径或源码版本。原环境为 Windows + WSL Ubuntu 22.04，`/usr/bin/python3 -s` 使用系统 NumPy 1.21.5、SciPy 1.8.0、Open3D 0.14.1，绘图使用 Matplotlib。`-s` 避免用户目录 NumPy 与系统扩展冲突。

## 路径和输入

- Windows `D:/nclt_student3` 对应 WSL `/mnt/d/nclt_student3`。
- 原始下载位于 `D:/chromeDownload`，包含两个日期激光包和各自 GT/协方差 CSV。
- PyICP-SLAM 位于 `/home/yaw/fastlio_week2/scancontext/vendor/PyICP-SLAM-master`，来源与补丁见 SOURCES.md。
- 如换机器，先按脚本中常量配置这些路径，并使用新的输出目录。原始实测脚本不覆盖既有结果；不得为方便复跑删除已有证据。

## 从原始数据重跑

1. Windows Python 执行 `evidence/scripts/prepare_downloads.py`，该脚本使用 Windows 路径，按实际 `(1).gz` 文件名读取；提取同步点云、校验 CRC、记录哈希。
2. WSL `/usr/bin/python3 -s` 执行 `audit_reference.py`、`validate_scans.py`、可选 `plot_reference.py` 和 `check_descriptor_input.py`。
3. 执行 `build_database_v1.py` 和 `build_query_v1.py`，生成两个日期的描述子。
4. 执行 `retrieve_cross_date_v1.py`，先完成不含参考位置的检索，再做参考位置评价。
5. 执行 `verify_cross_date_icp_v1.py`，全部 ICP 完成后加载参考位姿评价。保留所有366个候选，包括被拒绝者。
6. 执行 `audit_degenerate_matches_v1.py`，只做事后诊断；`plot_alignment_cases_v1.py` 生成说明性案例图。

命令形式：`/usr/bin/python3 -s <脚本绝对路径>`。上述文件均在 `evidence/scripts/`；运行时数据/输出根目录仍由脚本中的绝对路径决定，并不是仓库中的 evidence 目录。

## 仅验证已归档结果

在安装有 NumPy 的环境中执行 `python verify_archive.py`。无需点云、SciPy、Open3D 或上游 SC 模块。该脚本检查文件哈希、脚本语法、描述子与时间戳形状、重新汇总查询/几何/退化统计，并利用归档参考位姿与ICP矩阵复算全部366对变换误差。

这项验证没有重跑候选搜索或 ICP，没有验证原始点云语义，也不能证明参考位姿完全准确。原始数据仍需从官方获取；本包不是无需外部输入的一键系统。

## 报告对应关系

- `evidence/retrieval_cross_date_v1/`：1306次查询与候选信息。
- `evidence/geometry_cross_date_v1/`：366对ICP输出、矩阵和事后误差。
- `evidence/degeneracy_audit_v1/`：退化标记及假设拒绝后的统计。
- `evidence/reference_audit/`：参考帧清单、位姿和协方差子集，含覆盖诊断。
- `evidence/descriptors_v1/`：两天描述子及构建报告。
- `evidence/demo_cases_v1/`：两个明确选择的案例图与数值。

Hilti 的轨迹 ATE 见上级目录周报，不能将这里的帧间误差替换成 ATE。第三周实验必须另存版本，不能覆盖此基线。
