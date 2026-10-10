"""DCP3 的平台加载入口。

Type I：PF 与 PS 同时平移，固定圆形/环形约束产生多个较小的可行区域。
具体论文公式及公共参考前沿算法位于 problems.benchmark.DCP.common。
"""

from problems.benchmark.DCP.common import DCPBase


class DCP3(DCPBase):
    """将公共 DCP 实现绑定到论文中的第 3 个测试问题。"""

    # run_executor 按文件夹名查找 DCP3 类；公共基类再根据该编号
    # 选择目标函数、约束数量、变量边界及动态参数。
    problem_number = 3
