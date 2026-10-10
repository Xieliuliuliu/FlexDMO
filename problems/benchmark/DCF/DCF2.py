"""CEC2023 DCF2 的平台插件入口。

该文件只负责把文件夹名对应的公开类绑定到公共实现；论文公式、动态时间、
约束符号转换、参考 PF/PS 及可视化协议均位于 dcf_common，避免十个插件
重复维护相同逻辑。
"""

from problems.benchmark.DCF.common import DCF2Base


class DCF2(DCF2Base):
    """DCF2：动态切换位置变量与静态断裂约束。

    构造超参数由公共基类定义：decision_num 为变量数，n 为变化强度分母，
    tau 为变化频率，solution_num 为种群规模，total_evaluate_time 为平台
    播放和运行的环境数量。
    """

    # run_executor 按目录名查找同名类；公式由 DCF2Base 完整实现。
    pass
