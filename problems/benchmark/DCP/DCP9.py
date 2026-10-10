"""DCP9 的平台加载入口。

Type III：前沿控制变量 xr 随时间移动，多条窄不可行带容易诱导局部收敛。
具体论文公式及公共参考前沿算法位于 problems.benchmark.DCP.common。
"""

from problems.benchmark.DCP.common import DCPBase


class DCP9(DCPBase):
    """将公共 DCP 实现绑定到论文中的第 9 个测试问题。"""

    # run_executor 按文件夹名查找 DCP9 类；公共基类再根据该编号
    # 选择目标函数、约束数量、变量边界及动态参数。
    problem_number = 9
