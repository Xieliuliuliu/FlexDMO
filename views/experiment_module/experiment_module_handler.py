import tkinter as tk
from tkinter import ttk, messagebox
import os

from views.common.GlobalVar import global_vars
from utils.information_parser import get_dynamic_response_config, get_search_algorithm_config, get_problem_config
from views.components.collapsible_frame import CollapsibleFrame

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
        messagebox.showwarning("配置不完整", 
                             f"请选择以下配置：\n{', '.join(missing_configs)}")
        return
    
    # 获取运行时配置
    runtime_config = global_vars['experiment_module'].get('runtime_config', {})
    
    # 获取运行管理框架
    run_frame = global_vars['experiment_module']['run_frame']
    
    # 为每个组合创建进度条
    for problem in selected_problem:
        for dynamic in selected_dynamic:
            for search in selected_search:
                # 创建任务框架
                task_frame = ttk.Frame(run_frame)
                task_frame.pack(fill="x", padx=5, pady=2)
                
                # 创建左侧信息框架
                info_frame = ttk.Frame(task_frame)
                info_frame.pack(side="left", fill="x")
                
                # 创建任务信息标签
                task_info = f"{problem} - {dynamic} - {search}"
                task_label = ttk.Label(info_frame, text=task_info)
                task_label.pack(side="left", padx=5)
                
                # 创建右侧控制框架
                control_frame = ttk.Frame(task_frame)
                control_frame.pack(side="right")
                
                # 创建进度条
                progress = ttk.Progressbar(control_frame, length=200, mode='determinate')
                progress.pack(side="left", padx=5)
                
                # 创建状态标签
                status_label = ttk.Label(control_frame, text="等待中")
                status_label.pack(side="left", padx=5)
                
                # 保存进度条和状态标签的引用
                if 'tasks' not in global_vars['experiment_module']:
                    global_vars['experiment_module']['tasks'] = []
                global_vars['experiment_module']['tasks'].append({
                    'frame': task_frame,
                    'progress': progress,
                    'status': status_label,
                    'info': task_info
                })
    
    print("\n=== 实验配置 ===")
    for category, items in [
        ('动态策略', selected_dynamic),
        ('搜索算法', selected_search),
        ('问题', selected_problem)
    ]:
        print(f"\n{category}:")
        for item in items:
            print(f"  {item}")
            if item in runtime_config:
                for param, value in runtime_config[item].items():
                    print(f"    {param}: {value}")
    print("\n=== 配置结束 ===")

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