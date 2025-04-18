import os
import json
import numpy as np

from views.common.GlobalVar import global_vars


def save_test_module_information_results(save_path="results/test_module/"):
    """保存 test_module 中所有环境的 settings 和各时间点的 population 字符串表示，结构为 settings + information"""
    os.makedirs(save_path, exist_ok=True)
    runtime_populations = global_vars['test_module']["runtime_populations"]

    # 获取 settings 信息（从任意环境任意时间点提取一次即可）
    any_env = next(iter(runtime_populations.values()))
    any_result = next(iter(any_env.values()))
    settings = any_result.get('settings', {})
    response = settings.get('response_strategy_class', 'UnknownResponse')
    algo = settings.get('search_algorithm_class', 'UnknownAlgo')
    problem = settings.get('problem_class', 'UnknownProblem')
    base_filename = f"{response}_on_{algo}_on_{problem}"

    # 获取当前已有文件数量
    existing_files = [f for f in os.listdir(save_path)
                      if f.startswith(base_filename) and f.endswith('.json')]
    index = len(existing_files) + 1
    filename = f"{base_filename}_{index}.json"
    full_path = os.path.join(save_path, filename)

    # 构建总结果结构
    final_result = {
        "settings": settings,
        "information": {}
    }

    # 遍历每个环境
    for env_key, population_info in runtime_populations.items():
        env_population_record = {}

        # 提取该环境下的每个时间点 population
        for time_key, info in population_info.items():
            if "population" in info:
                env_population_record[str(time_key)] = info["population"].to_dict()

        final_result["information"][str(env_key)] = env_population_record

    # 自定义转换器
    def convert(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return str(obj)

    # 保存为 JSON 文件
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(final_result, f, indent=None, separators=(',', ':'), default=convert)

    print(f"[保存成功] -> {full_path}")
