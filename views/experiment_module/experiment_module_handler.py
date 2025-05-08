import tkinter as tk
from tkinter import ttk
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

def on_continue_button_click():
    """按钮点击事件"""
    # 获取选中的算法和问题
    selected_dynamic = global_vars['experiment_module']['selected_dynamic']
    selected_search = global_vars['experiment_module']['selected_search']
    selected_problem = global_vars['experiment_module']['selected_problem']
    
    # TODO: 实现实验运行逻辑
    print("Selected Dynamic Strategies:", selected_dynamic)
    print("Selected Search Algorithms:", selected_search)
    print("Selected Problems:", selected_problem)
    print("Runtime Config:", global_vars['experiment_module'].get('runtime_config', {}))

def create_config_frame(frame, value, style, get_config_func):
    """创建配置界面
    
    Args:
        frame: 父框架
        value: 配置项的值
        style: 样式（success/info/warning）
        get_config_func: 获取配置的函数
    """
    collapsible = CollapsibleFrame(frame, value, style=style)
    collapsible.pack(fill="x", pady=5)
    content_frame = collapsible.get_content_frame()
    config = get_config_func(value)
    if config:
        update_label(content_frame, value, config)

def update_all_configs():
    """更新所有配置"""
    frame = global_vars['experiment_module']['parameter_frame']
    
    # 获取当前所有CollapsibleFrame
    current_frames = {}
    for widget in frame.winfo_children():
        if isinstance(widget, CollapsibleFrame):
            current_frames[widget._title] = widget
    print(current_frames.keys())
    # 更新动态策略配置
    for value in global_vars['experiment_module']['selected_dynamic']:
        title = f"Dynamic Strategy: {value}"
        if title not in current_frames:
            create_config_frame(frame, value, 'success', get_dynamic_response_config)
        else:
            del current_frames[title]
            
    # 更新搜索算法配置
    for value in global_vars['experiment_module']['selected_search']:
        title = f"Search Algorithm: {value}"
        if title not in current_frames:
            create_config_frame(frame, value, 'info', get_search_algorithm_config)
        else:
            del current_frames[title]
            
    # 更新问题配置
    for value in global_vars['experiment_module']['selected_problem']:
        title = f"Problem: {value}"
        if title not in current_frames:
            create_config_frame(frame, value, 'warning', get_problem_config)
        else:
            del current_frames[title]
    
    # 删除不再需要的框架
    for frame in current_frames.values():
        frame.destroy()

def on_dynamic_select(tv_dynamic):
    """处理动态策略选择"""
    selected_items = tv_dynamic.selection()
    if selected_items:
        selected_values = [tv_dynamic.item(item, 'values')[0] for item in selected_items]
        global_vars['experiment_module']['selected_dynamic'] = selected_values
        update_all_configs()

def on_search_select(tv_search):
    """处理搜索算法选择"""
    selected_items = tv_search.selection()
    if selected_items:
        selected_values = [tv_search.item(item, 'values')[0] for item in selected_items]
        global_vars['experiment_module']['selected_search'] = selected_values
        update_all_configs()

def on_problem_select(tv_problem):
    """处理问题选择"""
    selected_items = tv_problem.selection()
    if selected_items:
        selected_values = [tv_problem.item(item, 'values')[0] for item in selected_items]
        global_vars['experiment_module']['selected_problem'] = selected_values
        update_all_configs()