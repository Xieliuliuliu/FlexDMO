# 文档截图

这些图片由 `flexdmo_app.docs_capture` 从实际桌面运行生成，
用于说明界面与操作，不用于证明算法性能。

| 文件 | 内容 |
| --- | --- |
| workspace.png | D-NSGA-II-B / NSGAII / CDP1 测试与环境回放 |
| batch-experiments.png | D-NSGA-II-B 与 NoResponse，使用 NSGAII / CDP1，各重复两次 |
| result-comparison.png | 上述批次的环境末帧 IGD 对比 |

使用已有的临时目录生成截图，检查图片后将需要的 PNG 复制到本目录：

```bash
.venv/bin/python -m flexdmo_app.docs_capture --output /absolute/path/to/existing-directory
```

截图脚本使用小规模参数，并检查运行前后的结果文件保持不变。
截图中包含的参数和指标只是演示数据；研究结果应另行保存完整配置和原始记录。
