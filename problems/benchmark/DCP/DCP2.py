"""DCP2 的平台加载入口。

Type I：目标前沿随时间振荡，两条固定约束共同考察可行性与收敛性的平衡。
具体论文公式及公共参考前沿算法位于 problems.benchmark.DCP.common。
"""

from problems.benchmark.DCP.common import DCPBase


class DCP2(DCPBase):
    """将公共 DCP 实现绑定到论文中的第 2 个测试问题。"""

    # run_executor 按文件夹名查找 DCP2 类；公共基类再根据该编号
    # 选择目标函数、约束数量、变量边界及动态参数。
    problem_number = 2
