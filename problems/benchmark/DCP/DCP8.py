"""DCP8 的平台加载入口。

Type III：目标和约束同时变化；在 t=0 时真实前沿位于约束边界而非原始 PF。
具体论文公式及公共参考前沿算法位于 problems.benchmark.DCP.common。
"""

from problems.benchmark.DCP.common import DCPBase


class DCP8(DCPBase):
    """将公共 DCP 实现绑定到论文中的第 8 个测试问题。"""

    # run_executor 按文件夹名查找 DCP8 类；公共基类再根据该编号
    # 选择目标函数、约束数量、变量边界及动态参数。
    problem_number = 8
