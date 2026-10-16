# 数据与代码来源

- NCLT 官方主页：https://robots.engin.umich.edu/nclt/index.html
- 引用：Nicholas Carlevaris-Bianco, Arash K. Ushani, Ryan M. Eustice, *University of Michigan North Campus Long-Term Vision and Lidar Dataset*, International Journal of Robotics Research, 2016.
- 说明文档：https://s3.us-east-2.amazonaws.com/publications.perl.engin.umich.edu/ncarlevaris-2015a.pdf
- 官方读取示例：[点云](https://s3.us-east-2.amazonaws.com/nclt.perl.engin.umich.edu/python/read_vel_sync.py)、[参考位姿](https://s3.us-east-2.amazonaws.com/nclt.perl.engin.umich.edu/python/read_ground_truth.py)。本文依据官方说明区分同步点云机体坐标与原始雷达坐标，并使用图节点参考。

原始下载：官方 S3 `nclt.perl.engin.umich.edu` 下的 `velodyne_data/2012-01-08_vel.tar.gz`、`velodyne_data/2012-02-05_vel.tar.gz`、`ground_truth/groundtruth_<日期>.csv` 和 `covariance/cov_<日期>.csv`。本机下载文件带 `(1)` 后缀，提取报告记录实际文件名与 SHA256。整包 gzip CRC 校验已通过；本地哈希不代表与官方发布校验码比对。

NCLT 数据库采用 [Open Database License 1.0](https://opendatacommons.org/licenses/odbl/1-0/)，单项内容采用 [Database Contents License 1.0](https://opendatacommons.org/licenses/dbcl/1-0/)。本目录公开的 NCLT 衍生数据集合（描述子、参考位姿子集及结果数据表）按 ODbL 1.0 提供，保留 NCLT 署名和对应单项内容许可。不将这些数据声明为作者原创数据。

Scan Context 使用 [gisbi-kim/PyICP-SLAM](https://github.com/gisbi-kim/PyICP-SLAM) 的本地 ZIP 版本，未固定上游 Git commit，补丁后模块 SHA256 为 `956938ea658270e7908a9e047e69bb0010d0a0f8efa70cb50e46ec44e1f24c72`。本包不再分发模块正文，沿用 [上游来源说明](../SOURCES.md) 和 [零重叠保护补丁](../upstream/scancontext_zero_overlap.patch)。原始每格 500 点上限及余弦评分方式保留，退化检查为独立事后脚本。

ICP 使用 Open3D 0.14.1。脚本为本次实验处理、分析和绘图记录。官方 PDF、官方示例源码、原始点云及完整参考 CSV 未重复打包。描述子由点云生成；存储的参考轨迹来自 NCLT，不是 KITTI OXTS。
