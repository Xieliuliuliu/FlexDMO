import json
import os
import time
from multiprocessing import current_process

class Algorithm:
    def __init__(self,state=None,pip=None,mode='test'):
        """
        基础算法抽象类。
        :param state: 进程状态
        :param pip: 进程间通信管道
        :param mode: 运行模式，'test'或'experiment'
        """
        self.history = {"runtime":{},"settings": None}  # 用于记录信息
        self.state = state
        self.pip = pip
        self.mode = mode  # 保存运行模式

    def optimize(self, problem, response_strategy):
        """
        主优化接口，输入一个 Problem，返回优化结果。
        必须由子类实现。
        """
        raise NotImplementedError

    def collect_information(self, population, problem, response_strategy):
        if self.history["settings"] is None:
            def extract_simple_attrs(obj):
                return {
                    k: v for k, v in vars(obj).items()
                    if isinstance(v, (int, float, str, bool, type(None)))
                }

            self.history["settings"] = {
                "problem_class": problem.__class__.__name__,
                "search_algorithm_class": self.__class__.__name__,
                "response_strategy_class": response_strategy.__class__.__name__,
                "problem_params": extract_simple_attrs(problem),
                "search_algorithm_params": extract_simple_attrs(self),
                "response_strategy_params":  extract_simple_attrs(response_strategy),
            }
        # 记录
        if problem.t not in self.history["runtime"]:
            self.history["runtime"][problem.t] = {}

        self.history["runtime"][problem.t][problem.evaluate_time] = population.copy()

        if self.pip is not None:
            if self.mode == 'test':
                # 测试模式：发送完整信息
                self.pip.send({
                    "settings": self.history["settings"],
                    'POS': problem.get_pareto_set(),
                    "POF": problem.get_pareto_front(),
                    "bound": [problem.xl, problem.xu],
                    't': problem.t,
                    'evaluate_times': problem.evaluate_time,
                    'population': population
                })
            elif self.mode == 'experiment':
                # 实验模式：只发送进度信息
                progress = ((problem.t + 1) / (problem.total_change_time)) * 100
                self.pip.send({
                    'progress': progress
                })

    def control_process(self):
        current_state = self.state
        if current_state is None:
            return True  # 状态不存在，默认继续运行

        # 检查状态值
        if current_state.value == 'running':
            return True
        elif current_state.value == 'pause':
            print(f"[子进程] {current_process().name} 暂停中...")
            while current_state.value == 'pause':
                time.sleep(0.5)
        if current_state.value == 'stop':
            print(f"[子进程] {current_process().name} 接收到终止指令")
            return False
        else:
            return True  # 未知状态，也默认继续
