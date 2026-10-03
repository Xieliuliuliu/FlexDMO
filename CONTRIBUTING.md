# 贡献指南

[返回项目首页](README.md) · [使用手册](docs/usage.md) · [算法接口](flexdmo_app/CODE_API.md)

欢迎提交算法改进、可复现的问题修复、回归测试和文档更正。

## 反馈问题

在 [Issues](https://github.com/Xieliuliuliu/FlexDMO/issues) 中提供：

- 操作系统、Python 版本和 Git 提交。
- 响应策略、搜索算法、测试问题与实际参数。
- 最短复现步骤、预期行为和实际结果。
- 错误堆栈或截图；闪退时可附去除个人路径信息后的崩溃记录。

不要上传密码、私钥、访问令牌、未公开研究代码或完整的个人数据目录。
无需提交整个运行目录；能复现问题的小规模配置通常更有用。

## 本地开发与检查

先按[安装指南](docs/installation.md)创建虚拟环境。
完整测试包含算法专用依赖，额外安装：

```bash
.venv/bin/python -m pip install -r requirements-test.txt
MPLBACKEND=Agg .venv/bin/python -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s flexdmo_app/tests -t . -v
git diff --check
```

Windows 使用 `.\.venv\Scripts\python.exe` 替代 `.venv/bin/python`。
Linux 需要安装图形系统库，即使界面测试采用离屏模式。

界面或进程控制的变更还应在实际桌面会话检查运行、暂停、终止、回放和工作区切换。
macOS 可运行以下集成检查；不要设置 `QT_QPA_PLATFORM=offscreen`：

```bash
.venv/bin/python -m flexdmo_app.replay_smoke
.venv/bin/python -m flexdmo_app.code_smoke
```

CI 配置覆盖 Linux、Windows、macOS 的自动测试和依赖检查，见 [tests.yml](.github/workflows/tests.yml)。
边界检查会阻止旧界面依赖回流，并验证基础启动不依赖算法专用训练库。
自动测试通过不意味着所有平台、组件和参数组合均已验证。

## 新增或修改算法

先阅读[算法接口](flexdmo_app/CODE_API.md)。
单文件算法可直接实现 `step`、`response` 或支持的类接口，不要求另写注册 JSON。

算法贡献请附原始文献、主要实现步骤、参数说明和小规模验证。
论文方法的适配、简化或替换算子需要明确说明。
引入新库时，保持算法专用依赖按需加载，不将大型训练库加入基础启动依赖。

## 提交 Pull Request

说明要解决的问题、变更范围、验证命令及结果。
修复问题时加入对应回归测试；只改文档时检查链接、命令和图片。
界面修改附真实运行截图，避免只提供效果图。

保持算法修改、界面修改和无关清理的边界清楚。
测试产物放在忽略目录或临时目录；不提交虚拟环境、运行数据和用户导入的算法。
公开文档截图放在 `docs/assets/`，不要包含个人路径或敏感信息。

## 许可与署名

项目采用 [Apache License 2.0](LICENSE)。提交的代码和素材应具有可用于本项目的权利，
保留必要的第三方许可与署名。算法出处写在实现或文档中，不以项目署名代替论文作者。
