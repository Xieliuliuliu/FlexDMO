# FlexDMO
<div align="center">
  <img src="views/resources/images/icon.png" alt="FlexDMO Logo" width="200"/>
</div>

📚 **简介**
------------------------------------------------------------

该框架用于实验和测试各类动态多目标算法在不同 benchmarks 和实际问题下的表现。本框架旨在提供一个结构化、可视化的实验环境，方便参数设置、问题选择、算法设计、和性能评估。

⚙️ 本框架将持续加入多种算法的实现，并可以轻松地进行扩展以加入新的算法或模块。

🔍 **注意**  
实现和结果仅供参考。如果你有更好的实现或改进建议，欢迎通过提交 **Issue** 或 **Email** 与我们进行沟通。我们鼓励社区的反馈和贡献！

## 🌐 官方网站
FlexDMO 的详细框架说明可通过以下链接访问：👉 https://flexdmo.cn

该网站全面介绍了 FlexDMO 框架的核心功能模块，包括算法组件、测试问题、响应策略、性能指标、在线可视化界面与结果输出功能。
此外，网站还提供了完整的 API 文档、使用指南、快速入门教程、参数配置说明及自定义扩展方法，旨在为研究人员和开发者提供一个结构化、可扩展、易用的动态多目标优化实验平台，支持高效的算法设计、性能评估与结果分析。

## 📂 项目结构 (Project Structure)

```text
FlexDMO/
├── algorithms/ # 算法实现
│ ├── response_strategy/ # 响应策略相关算法
│ ├── search_algorithm/ # 搜索算法实现
├── components/ # 框架组件
├── plots/ # 可视化绘图模块
├── problems/ # 问题定义
│ ├── benchmark/ # 基准测试问题
│ ├── real_problem/ # 实际问题定义
├── results_output/ # 对实验结果进行结果输出
├── utils/ # 工具函数
├── views/ # 用户界面相关
├── main.py # 主程序入口
```


💻 **依赖安装**
------------------------------------------------------------

在开始使用框架之前，首先需要安装相关的依赖库。以下是框架所需的所有库及其安装方式：

```bash
# 1. 克隆仓库
git clone https://github.com/Xieliuliuliu/FlexDMO.git
cd FlexDMO

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 开始运行
python main.py
```

📧 联系方式
------------------------------------------------------------
- Issues提交地址: https://github.com/Xieliuliuliu/FlexDMO/issues
- Email: xiejinsong@whu.edu.cn & hyhhyh@whu.edu.cn

🌟 感谢
------------------------------------------------------------
我们感谢所有的贡献者和研究人员！欢迎⭐ Star 和 🔱 Fork！

✅ 许可协议
------------------------------------------------------------
本项目采用 Apache-2.0 许可证。
