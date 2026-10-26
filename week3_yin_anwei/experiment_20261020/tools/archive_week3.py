"""Archive the student's completed week-3 tutorial without running experiments."""
import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np

ROOT = Path("/home/yaw/fastlio_week3")
LICENSE_TEXT = "                    GNU GENERAL PUBLIC LICENSE\n                       Version 2, June 1991\n\n Copyright (C) 1989, 1991 Free Software Foundation, Inc.,\n 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA\n Everyone is permitted to copy and distribute verbatim copies\n of this license document, but changing it is not allowed.\n\n                            Preamble\n\n  The licenses for most software are designed to take away your\nfreedom to share and change it.  By contrast, the GNU General Public\nLicense is intended to guarantee your freedom to share and change free\nsoftware--to make sure the software is free for all its users.  This\nGeneral Public License applies to most of the Free Software\nFoundation's software and to any other program whose authors commit to\nusing it.  (Some other Free Software Foundation software is covered by\nthe GNU Lesser General Public License instead.)  You can apply it to\nyour programs, too.\n\n  When we speak of free software, we are referring to freedom, not\nprice.  Our General Public Licenses are designed to make sure that you\nhave the freedom to distribute copies of free software (and charge for\nthis service if you wish), that you receive source code or can get it\nif you want it, that you can change the software or use pieces of it\nin new free programs; and that you know you can do these things.\n\n  To protect your rights, we need to make restrictions that forbid\nanyone to deny you these rights or to ask you to surrender the rights.\nThese restrictions translate to certain responsibilities for you if you\ndistribute copies of the software, or if you modify it.\n\n  For example, if you distribute copies of such a program, whether\ngratis or for a fee, you must give the recipients all the rights that\nyou have.  You must make sure that they, too, receive or can get the\nsource code.  And you must show them these terms so they know their\nrights.\n\n  We protect your rights with two steps: (1) copyright the software, and\n(2) offer you this license which gives you legal permission to copy,\ndistribute and/or modify the software.\n\n  Also, for each author's protection and ours, we want to make certain\nthat everyone understands that there is no warranty for this free\nsoftware.  If the software is modified by someone else and passed on, we\nwant its recipients to know that what they have is not the original, so\nthat any problems introduced by others will not reflect on the original\nauthors' reputations.\n\n  Finally, any free program is threatened constantly by software\npatents.  We wish to avoid the danger that redistributors of a free\nprogram will individually obtain patent licenses, in effect making the\nprogram proprietary.  To prevent this, we have made it clear that any\npatent must be licensed for everyone's free use or not licensed at all.\n\n  The precise terms and conditions for copying, distribution and\nmodification follow.\n\n                    GNU GENERAL PUBLIC LICENSE\n   TERMS AND CONDITIONS FOR COPYING, DISTRIBUTION AND MODIFICATION\n\n  0. This License applies to any program or other work which contains\na notice placed by the copyright holder saying it may be distributed\nunder the terms of this General Public License.  The \"Program\", below,\nrefers to any such program or work, and a \"work based on the Program\"\nmeans either the Program or any derivative work under copyright law:\nthat is to say, a work containing the Program or a portion of it,\neither verbatim or with modifications and/or translated into another\nlanguage.  (Hereinafter, translation is included without limitation in\nthe term \"modification\".)  Each licensee is addressed as \"you\".\n\nActivities other than copying, distribution and modification are not\ncovered by this License; they are outside its scope.  The act of\nrunning the Program is not restricted, and the output from the Program\nis covered only if its contents constitute a work based on the\nProgram (independent of having been made by running the Program).\nWhether that is true depends on what the Program does.\n\n  1. You may copy and distribute verbatim copies of the Program's\nsource code as you receive it, in any medium, provided that you\nconspicuously and appropriately publish on each copy an appropriate\ncopyright notice and disclaimer of warranty; keep intact all the\nnotices that refer to this License and to the absence of any warranty;\nand give any other recipients of the Program a copy of this License\nalong with the Program.\n\nYou may charge a fee for the physical act of transferring a copy, and\nyou may at your option offer warranty protection in exchange for a fee.\n\n  2. You may modify your copy or copies of the Program or any portion\nof it, thus forming a work based on the Program, and copy and\ndistribute such modifications or work under the terms of Section 1\nabove, provided that you also meet all of these conditions:\n\n    a) You must cause the modified files to carry prominent notices\n    stating that you changed the files and the date of any change.\n\n    b) You must cause any work that you distribute or publish, that in\n    whole or in part contains or is derived from the Program or any\n    part thereof, to be licensed as a whole at no charge to all third\n    parties under the terms of this License.\n\n    c) If the modified program normally reads commands interactively\n    when run, you must cause it, when started running for such\n    interactive use in the most ordinary way, to print or display an\n    announcement including an appropriate copyright notice and a\n    notice that there is no warranty (or else, saying that you provide\n    a warranty) and that users may redistribute the program under\n    these conditions, and telling the user how to view a copy of this\n    License.  (Exception: if the Program itself is interactive but\n    does not normally print such an announcement, your work based on\n    the Program is not required to print an announcement.)\n\nThese requirements apply to the modified work as a whole.  If\nidentifiable sections of that work are not derived from the Program,\nand can be reasonably considered independent and separate works in\nthemselves, then this License, and its terms, do not apply to those\nsections when you distribute them as separate works.  But when you\ndistribute the same sections as part of a whole which is a work based\non the Program, the distribution of the whole must be on the terms of\nthis License, whose permissions for other licensees extend to the\nentire whole, and thus to each and every part regardless of who wrote it.\n\nThus, it is not the intent of this section to claim rights or contest\nyour rights to work written entirely by you; rather, the intent is to\nexercise the right to control the distribution of derivative or\ncollective works based on the Program.\n\nIn addition, mere aggregation of another work not based on the Program\nwith the Program (or with a work based on the Program) on a volume of\na storage or distribution medium does not bring the other work under\nthe scope of this License.\n\n  3. You may copy and distribute the Program (or a work based on it,\nunder Section 2) in object code or executable form under the terms of\nSections 1 and 2 above provided that you also do one of the following:\n\n    a) Accompany it with the complete corresponding machine-readable\n    source code, which must be distributed under the terms of Sections\n    1 and 2 above on a medium customarily used for software interchange; or,\n\n    b) Accompany it with a written offer, valid for at least three\n    years, to give any third party, for a charge no more than your\n    cost of physically performing source distribution, a complete\n    machine-readable copy of the corresponding source code, to be\n    distributed under the terms of Sections 1 and 2 above on a medium\n    customarily used for software interchange; or,\n\n    c) Accompany it with the information you received as to the offer\n    to distribute corresponding source code.  (This alternative is\n    allowed only for noncommercial distribution and only if you\n    received the program in object code or executable form with such\n    an offer, in accord with Subsection b above.)\n\nThe source code for a work means the preferred form of the work for\nmaking modifications to it.  For an executable work, complete source\ncode means all the source code for all modules it contains, plus any\nassociated interface definition files, plus the scripts used to\ncontrol compilation and installation of the executable.  However, as a\nspecial exception, the source code distributed need not include\nanything that is normally distributed (in either source or binary\nform) with the major components (compiler, kernel, and so on) of the\noperating system on which the executable runs, unless that component\nitself accompanies the executable.\n\nIf distribution of executable or object code is made by offering\naccess to copy from a designated place, then offering equivalent\naccess to copy the source code from the same place counts as\ndistribution of the source code, even though third parties are not\ncompelled to copy the source along with the object code.\n\n  4. You may not copy, modify, sublicense, or distribute the Program\nexcept as expressly provided under this License.  Any attempt\notherwise to copy, modify, sublicense or distribute the Program is\nvoid, and will automatically terminate your rights under this License.\nHowever, parties who have received copies, or rights, from you under\nthis License will not have their licenses terminated so long as such\nparties remain in full compliance.\n\n  5. You are not required to accept this License, since you have not\nsigned it.  However, nothing else grants you permission to modify or\ndistribute the Program or its derivative works.  These actions are\nprohibited by law if you do not accept this License.  Therefore, by\nmodifying or distributing the Program (or any work based on the\nProgram), you indicate your acceptance of this License to do so, and\nall its terms and conditions for copying, distributing or modifying\nthe Program or works based on it.\n\n  6. Each time you redistribute the Program (or any work based on the\nProgram), the recipient automatically receives a license from the\noriginal licensor to copy, distribute or modify the Program subject to\nthese terms and conditions.  You may not impose any further\nrestrictions on the recipients' exercise of the rights granted herein.\nYou are not responsible for enforcing compliance by third parties to\nthis License.\n\n  7. If, as a consequence of a court judgment or allegation of patent\ninfringement or for any other reason (not limited to patent issues),\nconditions are imposed on you (whether by court order, agreement or\notherwise) that contradict the conditions of this License, they do not\nexcuse you from the conditions of this License.  If you cannot\ndistribute so as to satisfy simultaneously your obligations under this\nLicense and any other pertinent obligations, then as a consequence you\nmay not distribute the Program at all.  For example, if a patent\nlicense would not permit royalty-free redistribution of the Program by\nall those who receive copies directly or indirectly through you, then\nthe only way you could satisfy both it and this License would be to\nrefrain entirely from distribution of the Program.\n\nIf any portion of this section is held invalid or unenforceable under\nany particular circumstance, the balance of the section is intended to\napply and the section as a whole is intended to apply in other\ncircumstances.\n\nIt is not the purpose of this section to induce you to infringe any\npatents or other property right claims or to contest validity of any\nsuch claims; this section has the sole purpose of protecting the\nintegrity of the free software distribution system, which is\nimplemented by public license practices.  Many people have made\ngenerous contributions to the wide range of software distributed\nthrough that system in reliance on consistent application of that\nsystem; it is up to the author/donor to decide if he or she is willing\nto distribute software through any other system and a licensee cannot\nimpose that choice.\n\nThis section is intended to make thoroughly clear what is believed to\nbe a consequence of the rest of this License.\n\n  8. If the distribution and/or use of the Program is restricted in\ncertain countries either by patents or by copyrighted interfaces, the\noriginal copyright holder who places the Program under this License\nmay add an explicit geographical distribution limitation excluding\nthose countries, so that distribution is permitted only in or among\ncountries not thus excluded.  In such case, this License incorporates\nthe limitation as if written in the body of this License.\n\n  9. The Free Software Foundation may publish revised and/or new versions\nof the General Public License from time to time.  Such new versions will\nbe similar in spirit to the present version, but may differ in detail to\naddress new problems or concerns.\n\nEach version is given a distinguishing version number.  If the Program\nspecifies a version number of this License which applies to it and \"any\nlater version\", you have the option of following the terms and conditions\neither of that version or of any later version published by the Free\nSoftware Foundation.  If the Program does not specify a version number of\nthis License, you may choose any version ever published by the Free Software\nFoundation.\n\n  10. If you wish to incorporate parts of the Program into other free\nprograms whose distribution conditions are different, write to the author\nto ask for permission.  For software which is copyrighted by the Free\nSoftware Foundation, write to the Free Software Foundation; we sometimes\nmake exceptions for this.  Our decision will be guided by the two goals\nof preserving the free status of all derivatives of our free software and\nof promoting the sharing and reuse of software generally.\n\n                            NO WARRANTY\n\n  11. BECAUSE THE PROGRAM IS LICENSED FREE OF CHARGE, THERE IS NO WARRANTY\nFOR THE PROGRAM, TO THE EXTENT PERMITTED BY APPLICABLE LAW.  EXCEPT WHEN\nOTHERWISE STATED IN WRITING THE COPYRIGHT HOLDERS AND/OR OTHER PARTIES\nPROVIDE THE PROGRAM \"AS IS\" WITHOUT WARRANTY OF ANY KIND, EITHER EXPRESSED\nOR IMPLIED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF\nMERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.  THE ENTIRE RISK AS\nTO THE QUALITY AND PERFORMANCE OF THE PROGRAM IS WITH YOU.  SHOULD THE\nPROGRAM PROVE DEFECTIVE, YOU ASSUME THE COST OF ALL NECESSARY SERVICING,\nREPAIR OR CORRECTION.\n\n  12. IN NO EVENT UNLESS REQUIRED BY APPLICABLE LAW OR AGREED TO IN WRITING\nWILL ANY COPYRIGHT HOLDER, OR ANY OTHER PARTY WHO MAY MODIFY AND/OR\nREDISTRIBUTE THE PROGRAM AS PERMITTED ABOVE, BE LIABLE TO YOU FOR DAMAGES,\nINCLUDING ANY GENERAL, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES ARISING\nOUT OF THE USE OR INABILITY TO USE THE PROGRAM (INCLUDING BUT NOT LIMITED\nTO LOSS OF DATA OR DATA BEING RENDERED INACCURATE OR LOSSES SUSTAINED BY\nYOU OR THIRD PARTIES OR A FAILURE OF THE PROGRAM TO OPERATE WITH ANY OTHER\nPROGRAMS), EVEN IF SUCH HOLDER OR OTHER PARTY HAS BEEN ADVISED OF THE\nPOSSIBILITY OF SUCH DAMAGES.\n\n                     END OF TERMS AND CONDITIONS\n\n            How to Apply These Terms to Your New Programs\n\n  If you develop a new program, and you want it to be of the greatest\npossible use to the public, the best way to achieve this is to make it\nfree software which everyone can redistribute and change under these terms.\n\n  To do so, attach the following notices to the program.  It is safest\nto attach them to the start of each source file to most effectively\nconvey the exclusion of warranty; and each file should have at least\nthe \"copyright\" line and a pointer to where the full notice is found.\n\n    <one line to give the program's name and a brief idea of what it does.>\n    Copyright (C) <year>  <name of author>\n\n    This program is free software; you can redistribute it and/or modify\n    it under the terms of the GNU General Public License as published by\n    the Free Software Foundation; either version 2 of the License, or\n    (at your option) any later version.\n\n    This program is distributed in the hope that it will be useful,\n    but WITHOUT ANY WARRANTY; without even the implied warranty of\n    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the\n    GNU General Public License for more details.\n\n    You should have received a copy of the GNU General Public License along\n    with this program; if not, write to the Free Software Foundation, Inc.,\n    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.\n\nAlso add information on how to contact you by electronic and paper mail.\n\nIf the program is interactive, make it output a short notice like this\nwhen it starts in an interactive mode:\n\n    Gnomovision version 69, Copyright (C) year name of author\n    Gnomovision comes with ABSOLUTELY NO WARRANTY; for details type `show w'.\n    This is free software, and you are welcome to redistribute it\n    under certain conditions; type `show c' for details.\n\nThe hypothetical commands `show w' and `show c' should show the appropriate\nparts of the General Public License.  Of course, the commands you use may\nbe called something other than `show w' and `show c'; they could even be\nmouse-clicks or menu items--whatever suits your program.\n\nYou should also get your employer (if you work as a programmer) or your\nschool, if any, to sign a \"copyright disclaimer\" for the program, if\nnecessary.  Here is a sample; alter the names:\n\n  Yoyodyne, Inc., hereby disclaims all copyright interest in the program\n  `Gnomovision' (which makes passes at compilers) written by James Hacker.\n\n  <signature of Ty Coon>, 1 April 1989\n  Ty Coon, President of Vice\n\nThis General Public License does not permit incorporating your program into\nproprietary programs.  If your program is a subroutine library, you may\nconsider it more useful to permit linking proprietary applications with the\nlibrary.  If this is what you want to do, use the GNU Lesser General\nPublic License instead of this License.\n"
SOURCES_TEXT = "# 来源与许可记录\n\n本文件保留组仓库提交 f3aa975ead356cbe8b72c3568739ac9c3bb62974 的来源记录。\n本教程的地图、查询和评价均为Hilti同一采集序列的处理结果，不构成新增独立跨日期验证。\n\n## 组仓库来源记录\n\n# 代码与数据来源\n\n## FAST-LIO 源码\n\n- 上游：https://github.com/Ericsii/FAST_LIO\n- 本机基准提交：`2fffc570a25d0df172720bac034fbdb6a13d2162`\n- `week1_yin_anwei/fastlio_changes.patch` 相对该提交生成，包含本次修改及此前对 Hesai 字段的修改；配置文件独立提供。\n- `week1_yin_anwei/fastlio_runtime_diagnostics.patch` 在上一个补丁之后应用，增加本次 PointCloud2 回放的接收/处理计数、可配置输入 QoS 和耗时摘要；不改几何、外参或时间计算。原默认 QoS 保留，新推荐命令显式选择 RELIABLE。\n- 原始源码保留其原有版权和许可。应用补丁前应在该基准版本检查 `git apply --check`。\n\n固定构建依赖：\n\n| 仓库 | 提交 |\n|---|---|\n| [Livox-SDK2](https://github.com/Livox-SDK/Livox-SDK2) | `c0796f04c143143899c87a773d9f6b7136453c0b` |\n| [livox_ros_driver2](https://github.com/Livox-SDK/livox_ros_driver2) | `21445540f0d100dc86a7e6df312dd70bbdb4afdf` |\n| [ikd-Tree](https://github.com/hku-mars/ikd-Tree)（FAST-LIO 子模块） | `e2e3f4e9d3b95a9e66b1ba83dc98d4a05ed8a3c4` |\n\nPython 直接依赖及验证后的完整版本分别见根目录 `requirements-*.txt` 和 `requirements-*.lock.txt`。evo 来源：[MichaelGrupp/evo](https://github.com/MichaelGrupp/evo)；rosbags 来源：[官方文档](https://ternaris.gitlab.io/rosbags/)。\n\n## Hilti 数据集\n\n来源：[Hilti-Research 官方 Hilti SLAM Challenge 2022 数据集](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022)。\n\n- [标定文件](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/calibration/calibration_files/lidar_calibration.yaml)\n- [exp18 IMU 真值](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/ground_truth/exp18_corridor_lower_gallery_2_imu.txt)\n- [exp18 原始 ROS1 bag](https://huggingface.co/datasets/Hilti-Research/hilti-slam-challenge-2022/blob/main/rosbags/exp18_corridor_lower_gallery_2.bag)\n- 数据集许可：CC BY-NC-SA 3.0；数据与地图的使用和再分发应遵守其非商业、署名及相同方式共享条款。\n- 引用：Lintong Zhang 等，*Hilti-Oxford Dataset: A Millimeter-Accurate Benchmark for Simultaneous Localization and Mapping*，IEEE RA-L 8(1)，2023，408–415，DOI: 10.1109/LRA.2022.3226077。\n\n`groundtruth_imu.txt` 是同序列官方真值；PCD 和估计轨迹是使用该数据集生成的运行结果。\n\n2026-10-10 从上述官方真值地址重新下载，文件与归档逐字节 SHA256 一致：`138def6a40884a87372a4f18938cce5180d6aa7ad4e705349abf47ac4ec9fa32`，88,743 字节、789 位姿。时间范围 1649856227.723471–1649856314.319139 秒。尾段未评估由所用官方真值覆盖范围决定，并非本地文件截断。\n\n\n## ROS2定位器来源记录\n\n# 第二周来源与版本说明\n\n## 定位器\n\n- 上游：[myeongw002/FAST_LIO_LOCALIZATION_ROS2](https://github.com/myeongw002/FAST_LIO_LOCALIZATION_ROS2)。本地来自 `main` ZIP，未记录 Git commit，不能声称按提交固定。\n- 归档 `global_localization_debug.py`、`global_localization_guarded.py`、`global_localization_synced.py`、`transform_fusion_checked.py`、`transform_fusion_event.py` 为本次调试修改版。修改内容：日志、原始点云时间戳保留、时间差保护、精确时间配对、事件触发输出与历史修正选择。\n- `upstream/global_map_publisher.py` 和 `upstream/publish_initial_pose.py` 为本机下载的上游辅助脚本。\n- 上游 GPL-2.0 许可全文见 [FAST_LIO_LOCALIZATION_LICENSE](upstream/FAST_LIO_LOCALIZATION_LICENSE)，以上衍生源码沿用其许可；不把上游代码声明为本项目原创。\n- FAST-LIO 及 Hesai/QoS 修改来源沿用根目录 [SOURCES.md](../SOURCES.md)。\n\n\n本包不含Scan Context、NCLT或KITTI实验输入。GPL-2.0原许可文本见 licenses/FAST_LIO_LOCALIZATION_LICENSE。固定查询点云、地图派生结果和参考位姿的数据来源及许可沿用上述Hilti记录。\n\n原始组仓库：https://github.com/xiaoyinne/1\n原PCD下载：https://github.com/xiaoyinne/1/releases/download/week1-hilti-exp18-v1/fastlio_hilti_fixed_20261008.pcd\n原PCD SHA256：5513e08a55e7c9cc7187a5abd468157df86466151a0c1f27ace781384f49d52f\n\n本包新增教程脚本与冻结上游定位器分别保存。归档不声称冻结了原先未记录的上游Git提交。\n"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def require(condition, description):
    if not condition:
        raise RuntimeError(description)


def check_run(run, schedule, odom_ns, poses, sample_times, is_deletion):
    attempts = read_csv(run / "attempts.csv")
    require([int(row["stamp_ns"]) for row in attempts] == schedule,
            f"匹配时间表不符：{run}")
    accepted = [row for row in attempts if int(row["accepted"]) == 1]
    require(all(float(row["fitness"]) > 0.9 for row in accepted),
            f"接受标志与fitness阈值不符：{run}")
    with np.load(run / "corrections.npz") as data:
        ns = data["stamp_ns"].copy()
        transforms = data["transforms"].copy()
    require(ns.tolist() == [int(row["stamp_ns"]) for row in accepted],
            f"修正时间戳与接受记录不符：{run}")
    require(len(transforms) == len(ns), f"修正矩阵数量不符：{run}")
    require(np.all(np.diff(ns) > 0), f"修正时间未严格递增：{run}")
    require(np.isfinite(transforms).all(), f"修正矩阵存在非有限值：{run}")

    report_name = "deletion_report.json" if is_deletion else "ate_report.json"
    report = json.loads((run / report_name).read_text())
    available_times = np.array([], dtype=float)
    output_count = 0
    if len(ns):
        trajectory = np.loadtxt(run / "trajectory_tum.txt", ndmin=2)
        require(trajectory.shape[1] == 8 and np.isfinite(trajectory).all(),
                f"轨迹格式或数值有误：{run}")
        require(np.all(np.diff(trajectory[:, 0]) > 0), f"轨迹时间未严格递增：{run}")
        mask = odom_ns >= ns[0]
        stamps = odom_ns[mask]
        require(len(trajectory) == len(stamps), f"轨迹输出数量不符：{run}")
        require(np.allclose(trajectory[:, 0], stamps / 1e9, rtol=0, atol=1e-6),
                f"轨迹时间与前端不符：{run}")
        indices = np.searchsorted(ns, stamps, side="right") - 1
        require(np.all(indices >= 0) and np.all(ns[indices] <= stamps),
                f"轨迹使用了未来修正：{run}")
        used = transforms[indices]
        expected_xyz = np.einsum("nij,nj->ni", used[:, :3, :3], poses[mask, :3]) + used[:, :3, 3]
        require(np.allclose(trajectory[:, 1:4], expected_xyz, rtol=0, atol=1e-7),
                f"轨迹平移与历史修正融合结果不符：{run}")
        require(np.allclose(np.linalg.norm(trajectory[:, 4:8], axis=1), 1, atol=1e-6),
                f"轨迹四元数未归一：{run}")
        available_times = trajectory[:, 0]
        output_count = len(trajectory)

    indices = np.searchsorted(available_times, sample_times)
    present = indices < len(available_times)
    present[present] = available_times[indices[present]] == sample_times[present]
    count = int(present.sum())
    if is_deletion:
        require(report["fixed_pairs"] == len(sample_times), f"评价总样本数不同：{run}")
        require(report["evaluated_pairs"] == count, f"评价覆盖数与轨迹不符：{run}")
        require(abs(report["coverage"] - count / len(sample_times)) < 1e-12,
                f"评价覆盖率不符：{run}")
        require(report["output_poses"] == output_count, f"报告中的输出数量不符：{run}")
        if not np.all(present):
            require(report["ATE_m"] is None, f"覆盖不足却给出了主ATE：{run}")
        error_file = run / "deletion_errors.csv"
    else:
        require(np.all(present) and report["pairs"] == len(sample_times),
                f"噪声/原图评价样本不完整：{run}")
        error_file = run / "errors.csv"

    if report["ATE_m"] is not None:
        errors = np.loadtxt(error_file, delimiter=",", skiprows=1, ndmin=2)
        require(len(errors) == len(sample_times) and np.isfinite(errors).all(),
                f"逐样本误差有误：{run}")
        require(np.allclose(errors[:, 0], sample_times, rtol=0, atol=1e-6),
                f"逐样本误差的时间表不同：{run}")
        rmse = float(np.sqrt(np.mean(errors[:, 1] ** 2)))
        require(abs(rmse - report["ATE_m"]["rmse"]) < 1e-8,
                f"逐样本误差与报告RMSE不符：{run}")

    if is_deletion:
        anchors = np.concatenate((odom_ns[:1], ns, odom_ns[-1:]))
        gap = float(np.diff(anchors).max() / 1e9)
        require(abs(gap - report["max_correction_gap_s"]) < 1e-8,
                f"修正间隔报告不符：{run}")
    return dict(run=run.name, accepted=len(ns), evaluated_pairs=count,
                output_poses=output_count,
                status=report.get("status", "complete"))


def main():
    require("RUN_DIR" in os.environ, "请先设置RUN_DIR")
    base = Path(os.environ["RUN_DIR"]).resolve()
    require(base.parent == ROOT / "runs", "RUN_DIR不在本教程的runs目录中")
    report_file = ROOT / "report/WEEK3_REPORT.md"
    text = report_file.read_text(encoding="utf-8")
    expected_headings = [
        "## 一、研究问题", "## 二、实验方法", "## 三、评价范围与判据",
        "## 四、实验结果", "## 五、结果解释与局限", "## 六、结果与复现入口",
        "## 七、汇报提纲",
    ]
    for heading in expected_headings:
        require(text.splitlines().count(heading) == 1, f"章节缺失或重复：{heading}")
    linked_files = []
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
        if target.startswith(("https://", "http://", "#")):
            continue
        path = (report_file.parent / target.strip("<>")).resolve()
        require(path.is_relative_to(ROOT), f"报告链接超出本次目录：{target}")
        require(path.is_file(), f"报告链接目标不存在：{target}")
        linked_files.append(path)
    print("[1/5] 报告章节、图片和文件链接检查通过", flush=True)

    query = ROOT / "fixed_query_v1"
    schedule = json.loads((query / "schedule.json").read_text())["selected_stamp_ns"]
    require(len(schedule) == 53, "固定时间表不再是53次")
    require(len(list((query / "scans").glob("scan_*.npy"))) == 53, "查询扫描缓存数量不符")
    with np.load(query / "odometry.npz") as data:
        odom_ns, poses = data["stamp_ns"].copy(), data["xyz_quat"].copy()
    require(len(odom_ns) == 1091 and poses.shape == (1091, 7), "前端缓存数量或格式不同")
    sample = np.loadtxt(base / "common_eval/localization_matched.txt", ndmin=2)
    require(len(sample) == 753, "共同评价样本不再是753对")
    sample_times = sample[:, 0]
    schedule_bytes = (query / "schedule.json").read_bytes()
    config_bytes = (base / "localization.yaml").read_bytes()
    matcher_bytes = (base / "scripts/global_localization_synced.py").read_bytes()

    noise_rows = read_csv(ROOT / "fixed_runs/noise_summary.csv")
    expected_noise = {"clean_v1"} | {
        f"noise_sigma{sigma}_seed{seed}_v1"
        for sigma in ["0p05", "0p10", "0p20", "0p40"] for seed in [11, 22, 33]
    }
    require(len(noise_rows) == 13 and {r["run"] for r in noise_rows} == expected_noise,
            "加噪汇总不是本轮预定的13组")
    deletion_rows = read_csv(ROOT / "delete_runs/deletion_summary.csv")
    expected_deletion = {
        f"delete_block3m_ratio{ratio}_seed{seed}_v1"
        for ratio in ["0p10", "0p25", "0p50", "0p75", "0p90"] for seed in [11, 22, 33]
    }
    require(len(deletion_rows) == 15 and {r["run"] for r in deletion_rows} == expected_deletion,
            "删块汇总不是本轮预定的15组")
    require(not any(r["status"] == "error" for r in deletion_rows), "删块仍存在执行错误")
    criteria = json.loads((ROOT / "delete_runs/posthoc_criteria.json").read_text())
    require(criteria["analysis_type"] == "post_hoc_working_criteria", "事后判据标签不同")
    require(criteria["summary_sha256"] == sha(ROOT / "delete_runs/deletion_summary.csv"),
            "事后分类所依据的汇总表已变化")
    classified = read_csv(ROOT / "delete_runs/deletion_classified.csv")
    require(len(classified) == len(deletion_rows), "事后分类行数不符")
    classified_by_run = {row["run"]: row for row in classified}
    require(set(classified_by_run) == expected_deletion, "事后分类的运行列表不符")
    for row in deletion_rows:
        flags = classified_by_run[row["run"]]
        ate_flag = "" if row["ate_rmse_m"] == "" else str(int(
            float(row["ate_rmse_m"]) > criteria["ate_degraded_if_above_m"]
        ))
        require(flags["ate_degraded"] == ate_flag, "ATE事后分类不符：" + row["run"])
        require(flags["map_interrupted"] == str(int(
            float(row["max_correction_gap_s"]) > criteria["map_interrupted_if_gap_above_s"]
        )), "地图中断分类不符：" + row["run"])
        require(flags["coverage_incomplete"] == str(int(
            float(row["coverage"]) < criteria["required_coverage"]
        )), "覆盖率分类不符：" + row["run"])
    print("[2/5] 矩阵、固定输入与事后判据记录检查通过", flush=True)

    checks, map_inputs = [], {}
    for is_deletion, table, dirname in [
        (False, noise_rows, "fixed_runs"), (True, deletion_rows, "delete_runs")
    ]:
        for row in table:
            run = ROOT / dirname / row["run"]
            require((run / "schedule.json").read_bytes() == schedule_bytes, f"时间表不同：{run}")
            require((run / "localization.yaml").read_bytes() == config_bytes, f"参数不同：{run}")
            require((run / "frozen_matcher.py").read_bytes() == matcher_bytes, f"代码不同：{run}")
            check = check_run(run, schedule, odom_ns, poses, sample_times, is_deletion)
            require(int(row["accepted"]) == check["accepted"], f"汇总接受数量不同：{run}")
            if is_deletion:
                require(check["status"] == row["status"], f"删块汇总状态不同：{run}")
                require(int(row["evaluated_pairs"]) == check["evaluated_pairs"],
                        f"汇总评价覆盖数不同：{run}")
            saved_report = json.loads((run / (
                "deletion_report.json" if is_deletion else "ate_report.json"
            )).read_text())
            if saved_report["ATE_m"] is not None:
                require(abs(float(row["ate_rmse_m"]) - saved_report["ATE_m"]["rmse"]) < 1e-10,
                        f"汇总ATE不同：{run}")
            else:
                require(row["ate_rmse_m"] == "", f"无主ATE的运行在汇总中有数字：{run}")
            checks.append(check)
            map_file = Path((run / "map_path.txt").read_text().strip())
            require(map_file.is_file(), f"归档时地图文件不存在：{map_file}")
            digest = sha(map_file)
            metadata = map_file.parent / "report.json" if run.name != "clean_v1" else None
            map_inputs[run.name] = {
                "path": str(map_file), "sha256_at_archive_time": digest,
                "bytes": map_file.stat().st_size,
                "metadata_path": str(metadata) if metadata else None,
            }
            if is_deletion:
                saved = json.loads((run / "deletion_report.json").read_text())
                require(saved["map_sha256"] == digest, f"删块地图在评价后发生变化：{map_file}")
            if run.name == "clean_v1":
                expected_hash = (base / "map_sha256.txt").read_text().split()[0]
                require(digest == expected_hash, "原地图在实验后发生变化")
            print(f"  已核验 {len(checks)}/28：{run.name}", flush=True)
    print("[3/5] 28组修正、融合平移、覆盖率、误差算术及当前地图哈希检查通过", flush=True)

    deliverables = ROOT / "deliverables"
    deliverables.mkdir(exist_ok=True)
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d_%H%M%S")
    package = Path(tempfile.mkdtemp(prefix=f"week3_{stamp}_", dir=deliverables))
    print("归档目录：", package, flush=True)
    excluded = {".bag", ".db3", ".pcd", ".ply", ".mcap", ".pyc"}

    def copy_file(source, destination):
        require(not source.is_symlink(), f"归档暂不处理符号链接：{source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        require(sha(source) == sha(destination), f"复制后哈希不一致：{source}")

    def copy_tree(source, destination):
        for path in sorted(source.rglob("*")):
            relative = path.relative_to(source)
            if "__pycache__" in relative.parts or ".git" in relative.parts:
                continue
            if path.is_file() and path.suffix.lower() not in excluded:
                copy_file(path, destination / relative)

    for dirname in ["report", "fixed_query_v1", "fixed_runs", "delete_runs"]:
        copy_tree(ROOT / dirname, package / dirname)
    for script in sorted((ROOT / "tools").glob("*.py")):
        copy_file(script, package / "tools" / script.name)
    target_base = package / "runs" / base.name
    for path in sorted(base.iterdir()):
        if path.is_file() and path.suffix in {".py", ".txt", ".yaml", ".json", ".log"}:
            copy_file(path, target_base / path.name)
    for dirname in ["scripts", "common_eval"]:
        copy_tree(base / dirname, target_base / dirname)
    full_gt = Path("/home/yaw/fastlio_week2/data/exp18_corridor_lower_gallery_2_imu.txt")
    copy_file(full_gt, package / "sources" / full_gt.name)
    save_json(package / "sources/map_inputs.json", map_inputs)
    for name, value in map_inputs.items():
        if value["metadata_path"]:
            copy_file(Path(value["metadata_path"]), package / "sources/map_metadata" / (name + ".json"))
    for path in linked_files:
        require((package / path.relative_to(ROOT)).is_file(), f"归档后链接缺失：{path}")

    licenses = package / "licenses"
    licenses.mkdir()
    (licenses / "FAST_LIO_LOCALIZATION_LICENSE").write_text(LICENSE_TEXT, encoding="utf-8")
    (package / "SOURCES.md").write_text(SOURCES_TEXT, encoding="utf-8")
    (package / "README.md").write_text(
        "# 学生三第三周实验归档\n\n"
        "先读 [第三周周报](report/WEEK3_REPORT.md)。\n\n"
        "本包包括原图1组、加噪12组、删块15组固定查询实验。"
        "包含报告、曲线、配置、脚本、固定查询缓存和逐组证据。\n\n"
        "- [加噪汇总](fixed_runs/noise_summary.csv)\n"
        "- [删块汇总](delete_runs/deletion_summary.csv)\n"
        "- [删块事后分类](delete_runs/deletion_classified.csv)\n"
        "- [核验记录](validation.json)\n"
        "- [逐文件SHA256](FILE_SHA256.json)\n"
        "- [来源与许可记录](SOURCES.md)\n\n"
        "原始11GB传感器bag、408MB查询录制数据库、完整PCD和各破坏PCD未重复打包。"
        "本包包含派生的53帧固定查询缓存及1091条里程计。"
        "地图重建需要取得原PCD，再按metadata和生成脚本恢复；其他环境须恢复目录或修改脚本绝对路径。\n\n"
        "本次归档未重新运行ICP或evo对齐；核验了已保存结果的内部一致性，"
        "不能把这些检查解释为新机器端到端复现或全新独立精度验证。"
        "噪声地图哈希为归档时记录，不能反向证明历史运行时未记录的字节状态。\n\n"
        "未自动提交或推送GitHub。\n",
        encoding="utf-8",
    )
    result = {
        "passed": True, "fixed_query_runs": len(checks),
        "noise_plus_baseline_runs": len(noise_rows), "deletion_runs": len(deletion_rows),
        "deletion_status_counts": {
            status: sum(r["status"] == status for r in deletion_rows)
            for status in ["complete", "incomplete_coverage", "no_localization", "error"]
        },
        "report_sections": 7, "report_links_checked": len(linked_files),
        "checks": [
            "fixed timestamps, configuration and frozen matcher bytes",
            "accepted flags and saved correction timestamps",
            "causal fusion translation for all output poses",
            "quaternion normalization, finite values and increasing timestamps",
            "fixed GT sample coverage and reported RMSE arithmetic",
            "full-query correction-gap arithmetic",
            "copied file hashes and relative report links",
        ],
        "runs": checks,
    }
    save_json(package / "validation.json", result)
    hashes = {
        path.relative_to(package).as_posix(): sha(path)
        for path in sorted(package.rglob("*")) if path.is_file()
    }
    save_json(package / "FILE_SHA256.json", hashes)
    print("[4/5] 已复制文件，并核对归档中的相对链接及文件哈希", flush=True)

    archive = package.with_suffix(".zip")
    with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as stream:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                stream.write(path, (Path(package.name) / path.relative_to(package)).as_posix())
    with zipfile.ZipFile(archive) as stream:
        require(stream.testzip() is None, "ZIP完整性检查失败")
    archive_info = {
        "archive": str(archive), "bytes": archive.stat().st_size,
        "sha256": sha(archive), "zip_integrity": True,
    }
    save_json(archive.with_suffix(".zip.sha256.json"), archive_info)
    print("[5/5] ZIP完整性检查通过", flush=True)
    print("\n归档完成；未重新运行实验。", flush=True)
    print("报告：", package / "report/WEEK3_REPORT.md", flush=True)
    print("ZIP：", archive, flush=True)
    print("ZIP大小：", round(archive.stat().st_size / 1024**2, 2), "MiB", flush=True)
    print("ZIP SHA256：", archive_info["sha256"], flush=True)


if __name__ == "__main__":
    main()
