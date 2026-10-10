# 完整地图下载

[下载 fastlio_hilti_fixed_20261008.pcd](https://github.com/xiaoyinne/1/releases/download/week1-hilti-exp18-v1/fastlio_hilti_fixed_20261008.pcd) · [Release 页面](https://github.com/xiaoyinne/1/releases/tag/week1-hilti-exp18-v1)

| 项目 | 内容 |
|---|---|
| 对应运行 | 2026-10-08 Hilti `exp18_corridor_lower_gallery_2`，0.5 倍速 |
| 格式 | PCD v0.7，uncompressed binary |
| 点数 | 7,042,489 |
| 字节数 | 225,359,901（约 215 MiB） |
| SHA256 | `5513e08a55e7c9cc7187a5abd468157df86466151a0c1f27ace781384f49d52f` |
| 配置 | [hesai.yaml](week1_yin_anwei/hesai.yaml) |
| 轨迹 | [TUM](week1_yin_anwei/trajectory_tum.txt)、[KITTI](week1_yin_anwei/trajectory_kitti.txt)、[时间戳](week1_yin_anwei/trajectory_times.txt) |
| 坐标 | `camera_init` 世界坐标，单位米 |
| 字段 | `x y z intensity normal_x normal_y normal_z curvature` |
| 共享许可 | CC BY-NC-SA 3.0，数据来源与引用见 [SOURCES.md](SOURCES.md) |

Linux 下载及校验（在新的保存目录中执行）：

```bash
curl -fL --retry 3 -o fastlio_hilti_fixed_20261008.pcd \
  https://github.com/xiaoyinne/1/releases/download/week1-hilti-exp18-v1/fastlio_hilti_fixed_20261008.pcd
sha256sum fastlio_hilti_fixed_20261008.pcd
```

Windows PowerShell 校验：

```powershell
Get-FileHash .\fastlio_hilti_fixed_20261008.pcd -Algorithm SHA256
```

在 CloudCompare 中使用 File → Open 打开 PCD；选择点云子节点可查看点数和包围盒。先看整体，再放大墙面/走廊。该文件是累计配准扫描，保留远距离杂点，未做人工清理或点级精度保证。俯视图可能叠加不同高度的结构，不能只凭投影判断墙面重影。

本机原始副本为 `D:\chromeDownload\fastlio_hilti_fixed_20261008.pcd`。下载核验记录见 [VALIDATION.md](VALIDATION.md)。后续为重定位制作降采样地图时另存 `map_localization.pcd`，记录原文件 SHA256、体素大小、处理脚本和输出点数。
