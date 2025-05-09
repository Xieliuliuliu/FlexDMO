import os
from multiprocessing import Process, Pipe, Manager
import threading
import traceback
from utils.run_executor import load_main_class_from_folder, convert_config_to_numeric
import time

def begin_running(task_card, on_complete=None):
    """开始运行实验任务
    
    Args:
        task_card: TaskProgress实例，包含任务信息和状态
        on_complete: 任务完成时的回调函数
    """
    # 获取任务信息
    task_info = task_card.get_info()
    
    # 创建进程间通信对象
    manager = Manager()
    state = manager.Value('c', 'running')
    parent_conn, child_conn = Pipe()
    
    # 创建并启动子进程
    p = Process(
        target=run_experiment_process,
        args=(
            task_info['problem'],
            task_info['dynamic'],
            task_info['search'],
            task_info['tau'],
            task_info['n'],
            task_info['run'],
            task_info['problem_config'],
            task_info['dynamic_config'],
            task_info['search_config'],
            state,
            child_conn
        ),
        name=f"Exp_{task_info['problem']}_{task_info['dynamic']}_{task_info['search']}_{task_info['tau']}_{task_info['n']}_{task_info['run']}"
    )
    
    # 将进程对象赋值给task_card
    task_card.process = p
    task_card.process_state = state
    task_card.manager = manager
    task_card.on_complete = on_complete  # 保存回调函数
    
    # 启动进程
    p.start()
    
    # 启动监听线程
    threading.Thread(
        target=listen_experiment_pipe,
        args=(parent_conn, p, task_card),
        name=f"Exp_{task_info['problem']}_{task_info['dynamic']}_{task_info['search']}_{task_info['tau']}_{task_info['n']}_{task_info['run']}_listen"
    ).start()

def run_experiment_process(problem, dynamic, search, tau, n, run, problem_config, dynamic_config, search_config, state, child_conn):
    """在子进程中运行实验
    
    Args:
        problem: 问题名称
        dynamic: 动态策略
        search: 搜索算法
        tau: tau值
        n: n值
        run: 运行次数
        problem_config: 问题配置
        dynamic_config: 动态策略配置
        search_config: 搜索算法配置
        state: 进程状态
        child_conn: 子进程管道
    """
    try:
        from views.test_module.test_module_handler import (
            find_match_response_strategy,
            find_match_search_algorithm,
            find_match_problem
        )
        
        # 获取正确的文件夹名
        dynamic_folder = find_match_response_strategy(dynamic)
        search_folder = find_match_search_algorithm(search)
        problem_folder = find_match_problem(problem)
        
        # 覆盖问题配置中的tau和n值
        problem_config['tau'] = tau
        problem_config['n'] = n
        
        # 加载类
        ResponseClass = load_main_class_from_folder(dynamic_folder['folder_name'])
        SearchClass = load_main_class_from_folder(search_folder['folder_name'])
        ProblemClass = load_main_class_from_folder(problem_folder['folder_name'])
        
        # 实例化对象
        response_instance = ResponseClass(**convert_config_to_numeric(dynamic_config))
        search_instance = SearchClass(**convert_config_to_numeric(search_config), state=state, pip=child_conn, mode='experiment')
        problem_instance = ProblemClass(**convert_config_to_numeric(problem_config))
        
        # 运行优化
        search_instance.optimize(problem_instance, response_instance)
        print("run experiment process end")
    except Exception as e:
        print(f"[Error in experiment process]: {e}")
        # 打印错误信息
        print(traceback.format_exc())

def listen_experiment_pipe(parent_conn, process, task_card):
    """监听子进程通信，更新任务状态和进度"""
    try:
        while True:
            # 检查进程是否还活着
            if not process.is_alive():
                # 如果进程已经结束，检查是否有最后的数据
                try:
                    if parent_conn.poll():
                        data = parent_conn.recv()
                        if isinstance(data, dict) and 'progress' in data:
                            task_card.update_progress(data['progress'])
                except (EOFError, BrokenPipeError):
                    pass
                # 更新任务状态为已完成
                task_card.update_status('completed')
                # 调用完成回调函数
                if hasattr(task_card, 'on_complete') and task_card.on_complete:
                    task_card.on_complete(task_card)
                return  # 直接返回，结束线程
                
            # 检查是否有新数据
            try:
                if parent_conn.poll():
                    data = parent_conn.recv()
                    if isinstance(data, dict):
                        if 'progress' in data:
                            task_card.update_progress(data['progress'])
                        if 'status' in data:
                            task_card.update_status(data['status'])
            except (EOFError, BrokenPipeError):
                # 如果管道已关闭，检查进程状态
                if process.is_alive():
                    # 如果进程还在运行，可能是临时通信问题，继续监听
                    continue
                else:
                    # 如果进程已结束，更新状态并退出
                    task_card.update_status('completed')
                    # 调用完成回调函数
                    if hasattr(task_card, 'on_complete') and task_card.on_complete:
                        task_card.on_complete(task_card)
                    return  # 直接返回，结束线程
            
    except Exception as e:
        print(f"监听线程发生错误: {str(e)}")
        # 发生错误时，检查进程状态
        if process.is_alive():
            task_card.update_status('error')
        else:
            task_card.update_status('completed')
            # 调用完成回调函数
            if hasattr(task_card, 'on_complete') and task_card.on_complete:
                task_card.on_complete(task_card)
        return  # 发生异常时也结束线程
    finally:
        # 确保关闭连接
        try:
            parent_conn.close()
            task_card.manager.shutdown()
        except:
            pass