import os
import json
import traceback
import numpy as np

from utils.information_parser import convert_config_to_numeric, find_match_problem, get_problem_config
from views.common.GlobalVar import global_vars
from components.Population import Population
from components.Individual import Individual


def _save_json_with_numpy(data, file_path):
    """通用的JSON保存函数，处理numpy数据类型
    
    Args:
        data: 要保存的数据
        file_path: 保存路径
    """
    def convert(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.int32, np.int64)):
            return int(obj)
        return str(obj)

    # 保存为 JSON 文件
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=None, separators=(',', ':'), default=convert)

    print(f"[保存成功] -> {file_path}")

def _build_base_filename(settings):
    """构建基础文件名
    
    Args:
        settings: 包含算法配置信息的字典
    
    Returns:
        str: 基础文件名
    """
    response = settings.get('response_strategy_class', 'UnknownResponse')
    algo = settings.get('search_algorithm_class', 'UnknownAlgo')
    problem = settings.get('problem_class', 'UnknownProblem')
    
    # 从problem_params中获取tau和n
    problem_params = settings.get('problem_params', {})
    tau = problem_params.get('tau', 'unknown_tau')
    n = problem_params.get('n', 'unknown_n')
    
    base_name = f"{response}_on_{algo}_on_{problem}_tau{tau}_n{n}"
    return base_name

def _get_next_filename(save_path, base_filename):
    """获取下一个可用的文件名
    
    Args:
        save_path: 保存路径
        base_filename: 基础文件名
    
    Returns:
        str: 完整的文件名
    """
    # 获取当前已有文件数量
    existing_files = [f for f in os.listdir(save_path)
                      if f.startswith(base_filename) and f.endswith('.json')]
    index = len(existing_files) + 1
    return f"{base_filename}_{index}.json"

def save_module_results(data, save_path):
    """通用的模块结果保存函数
    
    Args:
        data: 要保存的数据，包含settings信息
        save_path: 保存路径
        extra_info: 额外的文件名信息，如tau、n等
        auto_index: 是否自动添加索引号，默认True
    """
    os.makedirs(save_path, exist_ok=True)
    
    # 从数据中获取settings
    if isinstance(data, dict) and 'settings' in data:
        settings = data['settings']
    
    # 构建文件名
    base_filename = _build_base_filename(settings)
    filename = _get_next_filename(save_path, base_filename)
    
    full_path = os.path.join(save_path, filename)
    _save_json_with_numpy(data, full_path)

def save_experiment_module_information_results(history, save_path):
    """保存实验模块的结果
    
    Args:
        history: 算法运行的历史记录
        save_path: 保存路径
    """
    # 从settings中获取算法组合信息
    settings = history.get('settings', {})
    response = settings.get('response_strategy_class', 'UnknownResponse')
    search = settings.get('search_algorithm_class', 'UnknownAlgo')
    problem = settings.get('problem_class', 'UnknownProblem')
    
    # 构建子目录路径
    result_dir = os.path.join(save_path, f"{response}_{search}", problem)
    os.makedirs(result_dir, exist_ok=True)
    
    # 转换runtime中的population为dict
    runtime_dict = {}
    for t, populations in history.get('runtime', {}).items():
        runtime_dict[str(t)] = {}
        for eval_time, population in populations.items():
            runtime_dict[str(t)][str(eval_time)] = population.to_dict()

    final_result = {
        "settings": settings,
        "information": runtime_dict
    }
    
    save_module_results(final_result, result_dir)

def save_test_module_information_results(save_path="results/test_module/"):
    """保存 test_module 中所有环境的 settings 和各时间点的 population 字符串表示，结构为 settings + information"""
    runtime_populations = global_vars['test_module']["runtime_populations"]

    # 获取 settings 信息（从任意环境任意时间点提取一次即可）
    any_env = next(iter(runtime_populations.values()))
    any_result = next(iter(any_env.values()))
    settings = any_result.get('settings', {})
    
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

    # 使用通用保存函数
    save_module_results(final_result, save_path)

def load_test_module_information_results(file_path):
    """从JSON文件中加载测试模块的结果信息
    
    Args:
        file_path (str): JSON文件的完整路径
        
    Returns:
        dict: 包含settings和各环境population信息的字典
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # 恢复settings
        settings = data.get('settings', {})
        
        # 获取问题配置
        problem_config = settings.get('problem_params', {})
        problem_class = settings.get('problem_class', '')
        
        # 动态导入问题类
        from utils.run_executor import load_main_class_from_folder
        ProblemClass = load_main_class_from_folder(find_match_problem(problem_class)['folder_name'])
        
        # 获取默认配置并更新
        config = get_problem_config(problem_class)
        for key, value in problem_config.items():
            if key in config:
                config[key] = value
        
        # 初始化问题类
        problem = ProblemClass(**convert_config_to_numeric(config))
        
        # 恢复runtime_populations
        runtime_populations = {}
        information = data.get('information', {})
        
        for env_key, env_data in information.items():
            env_populations = {}
            
            for time_key, pop_data in env_data.items():
                # 从字典重建Population对象
                individuals = []
                decisions = pop_data.get('decision', [])
                objectives,constrains = problem.evaluate(np.array(decisions),False,t=int(env_key))
       
                
                # 确保所有列表长度一致
                min_length = min(len(decisions), len(objectives))
                if min_length == 0:
                    continue
                    
                for i in range(min_length):
                    # 创建个体
                    individual = Individual(np.array(decisions[i]))
                    
                    # 设置目标值
                    if i < len(objectives):
                        individual.F = np.array(objectives[i])
                    
                    # 设置约束值
                    if constrains is not None:
                        individual.G = np.array(constrains[i])
                        individual.feasible = np.all(constrains[i] <= 0)
                    
                    individuals.append(individual)
                    
                # 创建种群
                population = Population(individuals=individuals)
                
                # 设置问题的时间步
                t = int(env_key)
                problem.t = t
                
                # 使用问题类获取当前时间步的POF和POS
                POF = problem.get_pareto_front(t)
                POS = problem.get_pareto_set(t)
                
                # 重建每个时间点的信息字典
                env_populations[int(time_key)] = {
                    'population': population,
                    'settings': settings,  # 每个时间点都包含相同的settings
                    'POS': POS,
                    'POF': POF,
                    'bound': [np.array(b) for b in pop_data.get('bound', [[], []])],
                    't': t,
                    'evaluate_times': int(time_key)
                }
                
            runtime_populations[int(env_key)] = env_populations
            
        # 更新global_vars中的数据
        if 'test_module' not in global_vars:
            global_vars['test_module'] = {}
        global_vars['test_module']['runtime_populations'] = runtime_populations
        
        print(f"[加载成功] <- {file_path}")
        return {'settings': settings, 'runtime_populations': runtime_populations}
        
    except Exception as e:
        print(f"[加载失败] {str(e)}")
        print(traceback.format_exc())
        return None


