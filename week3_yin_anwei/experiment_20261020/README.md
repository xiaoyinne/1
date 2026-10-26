# 学生三第三周实验归档

先读 [第三周周报](report/WEEK3_REPORT.md)。

本包包括原图1组、加噪12组、删块15组固定查询实验。包含报告、曲线、配置、脚本、固定查询缓存和逐组证据。

- [加噪汇总](fixed_runs/noise_summary.csv)
- [删块汇总](delete_runs/deletion_summary.csv)
- [删块事后分类](delete_runs/deletion_classified.csv)
- [核验记录](validation.json)
- [逐文件SHA256](FILE_SHA256.json)
- [来源与许可记录](SOURCES.md)

原始11GB传感器bag、408MB查询录制数据库、完整PCD和各破坏PCD未重复打包。本包包含派生的53帧固定查询缓存及1091条里程计。地图重建需要取得原PCD，再按metadata和生成脚本恢复；其他环境须恢复目录或修改脚本绝对路径。

本次归档未重新运行ICP或evo对齐；核验了已保存结果的内部一致性，不能把这些检查解释为新机器端到端复现或全新独立精度验证。噪声地图哈希为归档时记录，不能反向证明历史运行时未记录的字节状态。

未自动提交或推送GitHub。
