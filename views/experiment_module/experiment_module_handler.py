import gc
import tkinter as tk
from tkinter import ttk
import os
import ttkbootstrap as ttk
from ttkbootstrap.dialogs import Messagebox

from utils.run_executor_for_experiment import begin_running
from views.common.GlobalVar import global_vars
from utils.information_parser import get_dynamic_response_config, get_search_algorithm_config, get_problem_config
from views.components.collapsible_frame import CollapsibleFrame
from views.components.task_progress import TaskProgress

def update_label(fill_frame, config_type, config):
    """更新标签内容"""
    # 清空现有内容
    for widget in fill_frame.winfo_children():
        widget.destroy()
    # 创建内容区域
    content_frame = ttk.Frame(fill_frame)
    content_frame.pack(fill="x", expand=True)
    
    # 确保 runtime_config 是 dict
    if 'runtime_config' not in global_vars['experiment_module']:
        global_vars['experiment_module']['runtime_config'] = {}

    # 将填空内容保存到全局变量
    global_vars['experiment_module']['runtime_config'][config_type] = config  # 保存配置到全局变量
    
    # 动态生成填空内容并监听内容的修改
    for param, default_value in config.items():
        # 创建参数容器
        param_frame = ttk.Frame(content_frame)
        param_frame.pack(fill="x", pady=2)
        
        # 创建标签
        param_label = ttk.Label(param_frame, text=f"{param}: ", font=("Arial", 10), anchor="w")
        param_label.pack(side="left", fill="x", padx=1, expand=True)
        
        # 创建 Entry 控件
        param_entry = ttk.Entry(param_frame)
        param_entry.insert(0, default_value)  # 设置默认值
        param_entry.pack(side="left", fill="x", padx=5)
        
        # 设置事件监听，实时获取用户修改的配置
        def on_entry_change(event, param=param, entry=param_entry):
            # 更新全局配置，保存用户修改的值
            if config_type not in global_vars['experiment_module']['runtime_config']:
                global_vars['experiment_module']['runtime_config'][config_type] = {}
            global_vars['experiment_module']['runtime_config'][config_type][param] = entry.get()

        # 监听内容变化
        param_entry.bind("<KeyRelease>", on_entry_change)

def create_tasks(problem, dynamic, search, tau_values, n_values, runs, run_frame, runtime_config):
    """创建任务列表
    
    Args:
        problem: 问题名称
        dynamic: 动态策略
        search: 搜索算法
        tau_values: tau值列表
        n_values: n值列表
        runs: 运行次数
        run_frame: 运行管理框架
        runtime_config: 运行时配置
    
    Returns:
        list: 任务列表
    """
    tasks = []
    for tau in tau_values:
        for n in n_values:
            for run in range(runs):
                # 从runtime_config获取配置信息
                problem_config = runtime_config.get(problem, {})
                dynamic_config = runtime_config.get(dynamic, {})
                search_config = runtime_config.get(search, {})
                
                # 创建任务进度条组件
                task = TaskProgress(
                    run_frame, 
                    problem, 
                    dynamic, 
                    search, 
                    tau, 
                    n, 
                    run+1, 
                    runs,
                    problem_config=problem_config,
                    dynamic_config=dynamic_config,
                    search_config=search_config
                )
                tasks.append(task)
    return tasks

def on_add_button_click(event=None):
    """按钮点击事件"""
    # 获取所有配置
    selected_dynamic = global_vars['experiment_module']['selected_dynamic']
    selected_search = global_vars['experiment_module']['selected_search']
    selected_problem = global_vars['experiment_module']['selected_problem']
    
    # 检查是否有未选择的配置
    missing_configs = []
    if len(selected_dynamic) == 0:
        missing_configs.append("动态策略")
    if len(selected_search) == 0:
        missing_configs.append("搜索算法")
    if len(selected_problem) == 0:
        missing_configs.append("问题")
    
    if len(missing_configs) > 0:
        Messagebox.show_warning(
            title="配置不完整",
            message=f"请选择以下配置：\n{', '.join(missing_configs)}",
            parent=global_vars['experiment_module']['run_frame'].winfo_toplevel()
        )
        return
    
    # 获取运行时配置
    runtime_config = global_vars['experiment_module'].get('runtime_config', {})
    
    # 获取运行管理框架
    run_frame = global_vars['experiment_module']['run_frame']
    
    # 获取tau、n和runs的值
    tau_values = [int(x.strip()) for x in global_vars['experiment_module'].get('tau', tk.StringVar()).get().split(',')]
    n_values = [int(x.strip()) for x in global_vars['experiment_module'].get('n', tk.StringVar()).get().split(',')]
    runs = int(global_vars['experiment_module'].get('runs', tk.StringVar()).get())
    
    # 初始化任务列表
    if 'tasks' not in global_vars['experiment_module']:
        global_vars['experiment_module']['tasks'] = []
    
    # 为每个组合创建任务
    for problem in selected_problem:
        for dynamic in selected_dynamic:
            for search in selected_search:
                tasks = create_tasks(
                    problem, dynamic, search,
                    tau_values, n_values, runs,
                    run_frame, runtime_config
                )
                global_vars['experiment_module']['tasks'].extend(tasks)


def create_config_frame(frame, value, style, get_config_func, type, after=None):
    """创建配置界面
    
    Args:
        frame: 父框架
        value: 配置项的值
        style: 样式（success/info/warning）
        get_config_func: 获取配置的函数
        type: 框架类型
        after: 在哪个框架之后创建
    """
    collapsible = CollapsibleFrame(frame, value, style=style)
    collapsible.type = type
    if after:
        collapsible.pack(fill="x", pady=5, after=after)
    else:
        collapsible.pack(fill="x", pady=5)
    content_frame = collapsible.get_content_frame()
    config = get_config_func(value)
    if config:
        update_label(content_frame, value, config)
    return collapsible

def update_all_configs():
    """更新所有配置"""
    frame = global_vars['experiment_module']['parameter_frame']
    
    # 清空现有框架
    for widget in frame.winfo_children():
        widget.destroy()

    # 获取需要的配置
    need_dynamic = global_vars['experiment_module']['selected_dynamic']
    need_search = global_vars['experiment_module']['selected_search']
    need_problem = global_vars['experiment_module']['selected_problem']

    # 1. 创建动态策略框架
    for name in need_dynamic:
        create_config_frame(frame, name, 'success', 
                          get_dynamic_response_config, 'dynamic')

    # 2. 创建搜索算法框架
    for name in need_search:
        create_config_frame(frame, name, 'info', 
                          get_search_algorithm_config, 'search')

    # 3. 创建问题框架
    for name in need_problem:
        create_config_frame(frame, name, 'warning', 
                          get_problem_config, 'problem')

def on_dynamic_select(tv_dynamic):
    """处理动态策略选择"""
    selected_items = tv_dynamic.selection()
    selected_values = [tv_dynamic.item(item, 'values')[0] for item in selected_items]
    global_vars['experiment_module']['selected_dynamic'] = selected_values
    update_all_configs()

def on_search_select(tv_search):
    """处理搜索算法选择"""
    selected_items = tv_search.selection()
    selected_values = [tv_search.item(item, 'values')[0] for item in selected_items]
    global_vars['experiment_module']['selected_search'] = selected_values
    update_all_configs()

def on_problem_select(tv_problem):
    """处理问题选择"""
    selected_items = tv_problem.selection()
    selected_values = [tv_problem.item(item, 'values')[0] for item in selected_items]
    global_vars['experiment_module']['selected_problem'] = selected_values
    update_all_configs()

def on_remove_button_click(event=None):
    """删除所有运行卡片"""
    # 检查是否有运行中的任务
    if 'tasks' not in global_vars['experiment_module']:
        return
        
    tasks = global_vars['experiment_module']['tasks']
    if not tasks:
        return
        
    # 弹出确认对话框
    result = Messagebox.show_question(
        title="Confirm Delete",
        message="Are you sure you want to delete all running cards?",
        buttons=["Yes", "No"],
        parent=global_vars['experiment_module']['run_frame'].winfo_toplevel()
    )
    
    if result == "Yes" or result == "确认":
        # 销毁所有任务卡片
        for task in tasks:
            task.destroy()
        # 清空任务列表
        global_vars['experiment_module']['tasks'] = []
        # 释放监听线程
        
        for task in tasks:
            if task.process:
                task.process.terminate()
                task.process.join()
                task.process = None
        gc.collect()

def on_pause_button_click(event=None):
    """暂停/恢复按钮点击事件处理"""
    # 获取所有任务卡片
    task_cards = global_vars['experiment_module']['tasks']
    
    # 找到所有运行中的任务
    running_tasks = [card for card in task_cards if card.get_info()['status'] == 'running']
    # 找到所有暂停中的任务
    paused_tasks = [card for card in task_cards if card.get_info()['status'] == 'pause']
    
    if running_tasks:  # 如果有运行中的任务，则暂停它们
        # 更新所有运行中任务的状态
        for task in running_tasks:
            if hasattr(task, 'process_state') and task.process_state:
                task.process_state.value = 'pause'
            task.update_status('pause')
            task.status_label.configure(foreground='orange')  # 暂停状态显示为橙色
    elif paused_tasks:  # 如果有暂停的任务，则恢复它们
        # 更新所有暂停任务的状态
        for task in paused_tasks:
            if hasattr(task, 'process_state') and task.process_state:
                task.process_state.value = 'running'
            task.update_status('running')
            task.status_label.configure(foreground='blue')  # 运行状态显示为蓝色

def on_start_button_click(event=None):
    """开始按钮点击事件处理"""
    # 获取并行进程数
    parallel_processes = int(global_vars['experiment_module']['process_num'].get())
    
    # 获取所有任务卡片
    task_cards = global_vars['experiment_module']['tasks']
    
    # 计算当前运行中的任务数
    running_count = sum(1 for card in task_cards if card.get_info()['status'] == 'running')
    
    # 如果运行中的任务数已经达到或超过并行进程数，直接返回
    if running_count >= parallel_processes:
        return
    
    # 计算还可以启动多少个任务
    available_slots = parallel_processes - running_count
    
    # 获取所有等待中的任务
    waiting_tasks = [card for card in task_cards if card.get_info()['status'] == 'waiting']
    
    # 更新等待中的任务状态
    for task in waiting_tasks[:available_slots]:
        start_task(task)

def start_task(task):
    """启动单个任务"""
    # 更新任务状态为running
    task.update_status('running')
    # 更新界面显示
    task.update_progress(0)  # 重置进度条
    # 更新任务卡片样式（如果需要）
    task.status_label.configure(foreground='blue')  # 可以根据需要修改颜色
    # 开始运行任务，并传入完成回调函数
    begin_running(task, on_task_complete)

def on_task_complete(completed_task):
    """任务完成时的回调函数"""
    # 任务完成后，尝试启动新的等待任务
    on_start_button_click()
    
    # 这里可以添加其他完成后的处理逻辑
    completed_task.update_status('completed')
    completed_task.status_label.configure(foreground='green')