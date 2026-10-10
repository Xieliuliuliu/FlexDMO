import os
import json


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_json(path):
    with open(path, "r", encoding="utf-8") as config_file:
        return json.load(config_file)

def get_all_dynamic_strategy():
    # 构建目标目录路径
    target_dir = os.path.join(PROJECT_ROOT, "algorithms", "response_strategy")

    # 存储所有策略信息的列表
    strategies = []

    # 遍历该目录下的所有文件夹
    for folder_name in sorted(os.listdir(target_dir)):
        folder_path = os.path.join(target_dir, folder_name)

        # 确保这是一个文件夹
        if os.path.isdir(folder_path):
            config_path = os.path.join(folder_path, "info.json")

            # 确保config文件存在并且是文件
            if os.path.isfile(config_path):
                try:
                    # 假设config文件是JSON格式，读取文件内容
                    config_data = _read_json(config_path)

                    # 获取name和year信息
                    name = config_data.get("name")
                    year = config_data.get("year")

                    # 将信息添加到列表
                    strategies.append({
                        "folder_name": folder_path,
                        "name": name,
                        "year": year
                    })
                except Exception as e:
                    print(f"Error reading config for {folder_name}: {e}")

    return strategies

def get_all_search_algorithm():
    # 构建目标目录路径
    target_dir = os.path.join(PROJECT_ROOT, "algorithms", "search_algorithm")

    # 存储所有搜索算法信息的列表
    search_algorithms = []

    # 遍历该目录下的所有文件夹
    for folder_name in sorted(os.listdir(target_dir)):
        folder_path = os.path.join(target_dir, folder_name)

        # 确保这是一个文件夹
        if os.path.isdir(folder_path):
            config_path = os.path.join(folder_path, "info.json")

            # 确保config文件存在并且是文件
            if os.path.isfile(config_path):
                try:
                    # 假设config文件是JSON格式，读取文件内容
                    config_data = _read_json(config_path)

                    # 获取name和year信息
                    name = config_data.get("name")
                    year = config_data.get("year")

                    # 将信息添加到列表
                    search_algorithms.append({
                        "folder_name": folder_path,
                        "name": name,
                        "year": year
                    })
                except Exception as e:
                    print(f"Error reading config for {folder_name}: {e}")

    return search_algorithms

def get_all_problem():
    # 存储所有问题信息的列表
    problems = []

    from problems.benchmark import iter_benchmarks

    # 同系列共用目录；每个问题仍有独立源码、参数和元信息。
    # folder_name 保留原注册协议的键名，但使用源码路径作为唯一身份，
    # 避免同系列问题共享目录导致界面选择、参数缓存和消融配置相互覆盖。
    for family, name, source in iter_benchmarks():
        info_path = source.with_suffix(".info.json")
        config_path = source.with_suffix(".config.json")
        try:
            config_data = _read_json(info_path)
            if config_data.get("name") != name:
                raise ValueError(f"{info_path} 中的 name 必须为 {name}")
            if not config_path.is_file():
                raise ValueError(f"{name} 缺少独立配置文件")
            problems.append({
                "folder_name": str(source),
                "format": "benchmark-file",
                "class_name": name,
                "family": family,
                "info_path": str(info_path),
                "config_path": str(config_path),
                "name": name,
                "category": config_data.get("category", "Unconstrained"),
                "constraints": int(config_data.get("constraints", 0)),
                "difficulty": config_data.get("difficulty", ""),
                "description": config_data.get("description", "动态多目标测试问题"),
            })
        except (OSError, ValueError, TypeError) as error:
            print(f"Error reading config for {name}: {error}")

    return problems

def find_match_response_strategy(dynamic_response_name):
    # 获取所有动态响应策略
    strategies = get_all_dynamic_strategy()
    # 查找与 dynamic_response_name 匹配的策略
    return next((strategy for strategy in strategies if strategy["name"] == dynamic_response_name), None)

def find_match_search_algorithm(search_algorithm_name):
    # 获取所有搜索算法
    search_algorithms = get_all_search_algorithm()
    # 查找与 search_algorithm_name 匹配的搜索算法
    return next(
        (algorithm for algorithm in search_algorithms if algorithm["name"] == search_algorithm_name), None)

def find_match_problem(problem_name):
    # 获取所有问题
    problems = get_all_problem()
    # 查找与 problem_name 匹配的问题
    return next(
        (problem for problem in problems if problem["name"] == problem_name), None)


def get_dynamic_response_config(dynamic_response_name):
    config_data = {}
    matching_strategy = find_match_response_strategy(dynamic_response_name)
    if matching_strategy is None:
        return config_data
    config_path = os.path.join(matching_strategy['folder_name'], "config.json")
    # 确保config文件存在并且是文件
    if os.path.isfile(config_path):
        try:
            # 假设config文件是JSON格式，读取文件内容
            config_data = _read_json(config_path)
        except Exception as e:
            print(f"Error reading config for {config_path}: {e}")
    return config_data


# 获取搜索算法配置
def get_search_algorithm_config(search_algorithm_name):
    config_data = {}

    matching_algorithm = find_match_search_algorithm(search_algorithm_name)

    if matching_algorithm:
        config_path = os.path.join(matching_algorithm['folder_name'], "config.json")
        # 确保config文件存在并且是文件
        if os.path.isfile(config_path):
            try:
                # 假设config文件是JSON格式，读取文件内容
                config_data = _read_json(config_path)
            except Exception as e:
                print(f"Error reading config for {config_path}: {e}")

    return config_data

# 获取问题配置
def get_problem_config(problem_name):
    config_data = {}
    # 获取所有问题
    matching_problem = find_match_problem(problem_name)

    if matching_problem:
        config_path = matching_problem.get(
            "config_path", os.path.join(matching_problem['folder_name'], "config.json")
        )
        # 确保config文件存在并且是文件
        if os.path.isfile(config_path):
            try:
                # 假设config文件是JSON格式，读取文件内容
                config_data = _read_json(config_path)
            except Exception as e:
                print(f"Error reading config for {config_path}: {e}")

    return config_data

def convert_config_to_numeric(config_dict):
    converted = {}
    for key, value in config_dict.items():
        if isinstance(value, dict):
            # 递归处理嵌套字典
            converted[key] = convert_config_to_numeric(value)
        elif isinstance(value, str):
            try:
                # 尝试转 int
                if '.' not in value:
                    converted[key] = int(value)
                else:
                    converted[key] = float(value)
            except ValueError:
                # 保留原样
                converted[key] = value
        else:
            converted[key] = value
    return converted
