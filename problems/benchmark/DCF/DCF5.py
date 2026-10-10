"""CEC2023 DCF5 的平台插件入口。

该文件只负责把文件夹名对应的公开类绑定到公共实现；论文公式、动态时间、
约束符号转换、参考 PF/PS 及可视化协议均位于 dcf_common，避免十个插件
重复维护相同逻辑。
"""

from problems.benchmark.DCF.common import DCF5Base


class DCF5(DCF5Base):
    """DCF5：动态凹凸前沿与两个混合约束。

    构造超参数由公共基类定义：decision_num 为变量数，n 为变化强度分母，
    tau 为变化频率，solution_num 为种群规模，total_evaluate_time 为平台
    播放和运行的环境数量。
    """

    # run_executor 按目录名查找同名类；公式由 DCF5Base 完整实现。
    pass
