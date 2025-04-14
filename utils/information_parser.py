import random
import os
import json
import sys

def get_all_dynamic_strategy():
    # 获取当前脚本所在目录路径，也就是main.py所在的目录
    root_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # 构建目标目录路径
    target_dir = os.path.join(root_dir, "algorithms", "response_strategy")

    # 存储所有策略信息的列表
    strategies = []

    # 遍历该目录下的所有文件夹
    for folder_name in os.listdir(target_dir):
        folder_path = os.path.join(target_dir, folder_name)

        # 确保这是一个文件夹
        if os.path.isdir(folder_path):
            config_path = os.path.join(folder_path, "info.json")

            # 确保config文件存在并且是文件
            if os.path.isfile(config_path):
                try:
                    # 假设config文件是JSON格式，读取文件内容
                    with open(config_path, 'r') as config_file:
                        config_data = json.load(config_file)

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
    # 获取当前脚本所在目录路径，也就是main.py所在的目录
    root_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # 构建目标目录路径
    target_dir = os.path.join(root_dir, "algorithms", "search_algorithm")

    # 存储所有搜索算法信息的列表
    search_algorithms = []

    # 遍历该目录下的所有文件夹
    for folder_name in os.listdir(target_dir):
        folder_path = os.path.join(target_dir, folder_name)

        # 确保这是一个文件夹
        if os.path.isdir(folder_path):
            config_path = os.path.join(folder_path, "info.json")

            # 确保config文件存在并且是文件
            if os.path.isfile(config_path):
                try:
                    # 假设config文件是JSON格式，读取文件内容
                    with open(config_path, 'r') as config_file:
                        config_data = json.load(config_file)

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
    # 获取当前脚本所在目录路径，也就是main.py所在的目录
    root_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    # 构建目标目录路径
    target_dir = os.path.join(root_dir, "problems", "benchmark")

    # 存储所有问题信息的列表
    problems = []

    # 遍历该目录下的所有文件夹
    for folder_name in os.listdir(target_dir):
        folder_path = os.path.join(target_dir, folder_name)

        # 确保这是一个文件夹
        if os.path.isdir(folder_path):
            config_path = os.path.join(folder_path, "info.json")

            # 确保config文件存在并且是文件
            if os.path.isfile(config_path):
                try:
                    # 假设config文件是JSON格式，读取文件内容
                    with open(config_path, 'r') as config_file:
                        config_data = json.load(config_file)

                        # 获取name和year信息
                        name = config_data.get("name")

                        # 将信息添加到列表
                        problems.append({
                            "folder_name": folder_path,
                            "name": name,
                        })
                except Exception as e:
                    print(f"Error reading config for {folder_name}: {e}")

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
    config_path = os.path.join(matching_strategy['folder_name'], "config.json")
    # 确保config文件存在并且是文件
    if os.path.isfile(config_path):
        try:
            # 假设config文件是JSON格式，读取文件内容
            with open(config_path, 'r') as config_file:
                config_data = json.load(config_file)
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
                with open(config_path, 'r') as config_file:
                    config_data = json.load(config_file)
            except Exception as e:
                print(f"Error reading config for {config_path}: {e}")

    return config_data

# 获取问题配置
def get_problem_config(problem_name):
    config_data = {}
    # 获取所有问题
    matching_problem = find_match_problem(problem_name)

    if matching_problem:
        config_path = os.path.join(matching_problem['folder_name'], "config.json")
        # 确保config文件存在并且是文件
        if os.path.isfile(config_path):
            try:
                # 假设config文件是JSON格式，读取文件内容
                with open(config_path, 'r') as config_file:
                    config_data = json.load(config_file)
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
