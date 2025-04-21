import gc
import threading
from tkinter import ttk
import os
import tkinter as tk

from matplotlib import pyplot as plt

from utils.information_parser import get_dynamic_response_config, get_search_algorithm_config, get_problem_config, \
    get_all_dynamic_strategy, get_all_search_algorithm, get_all_problem, find_match_response_strategy, \
    find_match_problem, find_match_search_algorithm
from utils.run_executor import run_in_test_mode, delete_state_in_test_mode, listen_pipe
from views.common.GlobalVar import global_vars
from utils.result_io import load_test_module_information_results
from plots.test_module.draw_population import draw_PF


# Create a function to update the StringVars when an item is selected
def on_dynamic_select(tv_dynamic):
    selected_item = tv_dynamic.selection()
    if selected_item:
        selected_value = tv_dynamic.item(selected_item[0], 'values')[0]  # Get the algorithm name
        global_vars['test_module']['selected_dynamic'].set(selected_value)


def on_search_select(tv_search):
    selected_item = tv_search.selection()
    if selected_item:
        selected_value = tv_search.item(selected_item[0], 'values')[0]  # Get the algorithm name
        global_vars['test_module']['selected_search'].set(selected_value)

def on_problem_select(tv_problem):
    """处理测试问题选择"""
    selected_item = tv_problem.selection()
    if selected_item:
        selected_value = tv_problem.item(selected_item[0], 'values')[0]  # 获取选中的问题名称
        global_vars['test_module']['selected_problem'].set(selected_value)

def load_dynamic_data():
    """加载Dynamic Strategy算法数据"""
    data = get_all_dynamic_strategy()
    # 从数据库加载数据
    return data

def load_search_data():
    """加载Search Algorithm数据"""
    data = get_all_search_algorithm()
    return data

def load_problem_data():
    """加载Search Algorithm数据"""
    data = get_all_problem()
    return data


# 动态绑定text的更新
def update_label(label, fill_frame, config_type):
    # 获取选中项
    select_item = global_vars['test_module'][config_type].get()
    label.config(text=select_item)  # 更新标签文本为选中的动态策略

    """清空并更新填空内容"""
    # 清空当前框架中的内容（如果有）
    for widget in fill_frame.winfo_children():
        widget.destroy()

    # 根据传入的 config_type 获取相应的配置
    if config_type == "selected_dynamic":
        config = get_dynamic_response_config(select_item)  # 获取响应策略配置
    elif config_type == "selected_search":
        config = get_search_algorithm_config(select_item)  # 获取搜索算法配置
    elif config_type == "selected_problem":
        config = get_problem_config(select_item)  # 获取问题配置
    else:
        raise ValueError(f"Unknown config type: {config_type}")
    # 确保 runtime_config 是 dict
    if 'runtime_config' not in global_vars['test_module']:
        global_vars['test_module']['runtime_config'] = {}

    # 将填空内容保存到全局变量
    global_vars['test_module']['runtime_config'][config_type] = config  # 保存配置到全局变量

    # 动态生成填空内容并监听内容的修改
    row = 0  # 行号，确保每个参数显示在不同的行中
    # 动态生成填空内容并监听内容的修改
    for param, default_value in config.items():
        # 创建标签并设置为 grid
        param_label = ttk.Label(fill_frame, text=f"{param}: ", font=("Arial", 10))
        param_label.grid(row=row, column=0, padx=5, pady=2, sticky="w")

        # 创建 Entry 控件并设置为 grid
        param_entry = ttk.Entry(fill_frame)
        param_entry.insert(0, default_value)  # 设置默认值
        param_entry.grid(row=row, column=1, padx=5, pady=2)

        # 设置事件监听，实时获取用户修改的配置
        def on_entry_change(event, param=param, entry=param_entry):
            # 更新全局配置，保存用户修改的值
            global_vars['test_module']['runtime_config'][config_type][param] = entry.get()
            # print(global_vars['test_module'])

        # 监听内容变化
        param_entry.bind("<KeyRelease>", on_entry_change)  # 监听键盘输入，实时更新
        row += 1  # 增加行号，确保下一个参数出现在下一行

def on_continue_button_click():
    """按钮点击事件"""
    # 打印相关的运行配置
    # print("runtime_config:")
    # print(global_vars['test_module']['runtime_config'])

    # 获取并打印 dynamic 相关信息
    response_strategy = global_vars['test_module']['selected_dynamic'].get()  # 获取 selected_dynamic 的当前值
    # print(f"Selected Dynamic: {find_match_response_strategy(response_strategy)}")

    # 获取并打印 search 相关信息
    search_algorithm = global_vars['test_module']['selected_search'].get()  # 获取 selected_search 的当前值
    # print(f"Selected Search: {find_match_search_algorithm(search_algorithm)}")

    # 获取并打印 result_to_show 相关信息
    result_to_show = global_vars['test_module']['result_to_show'].get()  # 获取 result_to_show 的当前值
    # print(f"Result to Show: {result_to_show}")

    # 获取并打印 problem 相关信息
    problem_name = global_vars['test_module']['selected_problem'].get()  # 获取 selected_problem 的当前值
    # print(f"Selected Problem: {find_match_problem(problem_name)}")
    run_in_test_mode(
        find_match_response_strategy(response_strategy),
        find_match_search_algorithm(search_algorithm),
        find_match_problem(problem_name),
        result_to_show,
        global_vars['test_module']['runtime_config']
    )


def on_pause_button_click():
    # 检查是否存在该状态
    process_entry = global_vars.get('test_module')
    if process_entry and process_entry['process_state'] is not None and 'process_state' in process_entry:
        process_entry['process_state'].value = 'pause'
    else:
        print("[主进程] 无 process_state，不执行暂停")

def on_stop_button_click():
    process_entry = global_vars.get('test_module')
    if process_entry and process_entry['process_state'] is not None and 'process_state' in process_entry:
        process_entry['process_state'].value = 'stop'
        delete_state_in_test_mode()
    else:
        print("[主进程] 无 process_state，不执行终止")


def clear_canvas():
    """彻底释放 Tkinter Canvas + Matplotlib Figure"""

    canvas = global_vars['test_module'].get('canvas')
    if canvas:
        try:
            fig = canvas.figure

            # 强制清空所有 axes，patches，text
            fig.clf()
            fig.clear()

            # 确保底层 Artist 和 Transform 不再引用
            for ax in fig.axes:
                ax.clear()
            fig.axes.clear()

            plt.close(fig)
            del fig

            # 销毁 Tkinter widget
            widget = canvas.get_tk_widget()
            if widget.winfo_exists():
                widget.destroy()

            del canvas
            global_vars['test_module']['canvas'] = None

        except Exception as e:
            print(f"[清理失败] {e}")

    if 'ax' in global_vars['test_module']:
        del global_vars['test_module']['ax']

    # 强制垃圾回收
    import gc
    gc.collect()

def get_result_files():
    """获取结果目录下的所有JSON文件
    
    Returns:
        tuple: (json_files, result_names) - 文件名列表和显示名称列表
    """
    results_dir = "results/test_module"
    if not os.path.exists(results_dir):
        os.makedirs(results_dir, exist_ok=True)
        return [], []

    # 获取所有JSON文件
    json_files = [f for f in os.listdir(results_dir) if f.endswith('.json')]
    
    # 从文件名中提取显示名称
    result_names = []
    for file in json_files:
        # 移除.json后缀
        base_name = file[:-5]
        # 将下划线替换为空格，使显示更友好
        display_name = base_name.replace('_', ' ')
        result_names.append(display_name)
    
    return json_files, result_names

def update_result_combobox(combobox):
    """更新结果选择下拉框的选项
    
    Args:
        combobox: ttk.Combobox对象
    """
    _, result_names = get_result_files()
    combobox['values'] = result_names
    if result_names:
        combobox.set(result_names[0])  # 设置第一个为默认值

def load_selected_result(selected_result):
    """加载选中的结果文件
    
    Args:
        selected_result (str): 选中的结果显示名称
        
    Returns:
        dict: 加载的结果数据，如果加载失败则返回None
    """
    if not selected_result:
        return None
        
    # 将显示名称转换回文件名
    file_name = selected_result.replace(' ', '_') + '.json'
    file_path = os.path.join("results/test_module", file_name)
    
    # 加载结果
    result = load_test_module_information_results(file_path)
    if result:
        # 更新global_vars中的数据
        if 'test_module' not in global_vars:
            global_vars['test_module'] = {}
        global_vars['test_module']['runtime_populations'] = result['runtime_populations']
        global_vars['test_module']['runtime_historical_config'] = result['settings']
        print(f"成功加载结果: {selected_result}")
    else:
        print(f"加载结果失败: {selected_result}")
        
    return result

def update_result_display(scale, result_data, param_text, metric_value):
    """更新结果显示
    
    Args:
        scale: 进度条对象
        result_data (dict): 结果数据
        param_text (tk.Text): 参数显示文本框
        metric_value (ttk.Label): 指标值显示标签
    """
    settings = result_data.get('settings', {})
    
    # 更新参数显示
    param_text.configure(state='normal')
    param_text.delete('1.0', tk.END)
    
    # 直接显示settings中的所有字段
    param_text.insert('1.0', "Settings:\n")
    for key, value in settings.items():
        if isinstance(value, dict):
            param_text.insert(tk.END, f"\n{key}:\n")
            for sub_key, sub_value in value.items():
                param_text.insert(tk.END, f"  {sub_key}: {sub_value}\n")
        else:
            param_text.insert(tk.END, f"{key}: {value}\n")
    
    # 从全局变量中获取标签
    current_label = global_vars['test_module'].get('current_label')
    total_label = global_vars['test_module'].get('total_label')
    
    # 如果找到了进度条和标签，更新它们
    if scale and current_label and total_label:
        update_progress_control(scale, current_label, total_label)
    
    param_text.configure(state='disabled')

def update_progress_control(scale, current_label, total_label):
    """更新进度控制组件
    
    Args:
        scale: ttk.Scale对象
        current_label: 当前变化次数标签
        total_label: 总变化次数标签
    """
    # 确保进度条始终可拖动
    scale.configure(state='normal')
    
    # 检查全局变量
    if 'test_module' not in global_vars:
        scale.configure(from_=0, to=100)
        scale.set(0)
        current_label.config(text="Current Evaluation: 0")
        total_label.config(text="Total Evaluation: 0")
        return
    
    # 获取运行时数据
    runtime_populations = global_vars['test_module'].get('runtime_populations', {})
    runtime_config = global_vars['test_module'].get('runtime_historical_config', {})
    
    # 如果没有数据，显示默认值
    if not runtime_config or not runtime_populations:
        scale.configure(from_=0, to=100)
        scale.set(0)
        current_label.config(text="Current Evaluation: 0")
        total_label.config(text="Total Evaluation: 0")
        return
    
    try:
        # 获取总变化次数
        problem_params = runtime_config.get('problem_params', {})
        total_changes = int(problem_params.get('change_each_evaluations', 0)) *  int(problem_params.get('total_change_time', 0))
        
        # 获取当前变化次数
        current_change = 0
        
        # 更新进度条
        scale.configure(from_=0, to=total_changes)
        
        # 更新标签
        current_label.config(text=f"Current Evaluation: {current_change}")
        total_label.config(text=f"Total Evaluation: {total_changes}")
        
    except Exception as e:
        print(f"更新进度控制时出错: {e}")
        scale.configure(from_=0, to=100)
        scale.set(0)
        current_label.config(text="Current Evaluation: 0")
        total_label.config(text="Total Evaluation: 0")

def on_scale_change(val, current_label, total_label):
    """处理进度条变化事件
    
    Args:
        val: 进度条当前值（浮点数）
        current_label: 当前变化次数标签
        total_label: 总变化次数标签
    """
    try:
        # 将进度值转换为浮点数
        current_eval = float(val)
        
        # 更新标签
        current_label.config(text=f"Current Evaluation: {current_eval:.0f}")
        
        # 获取运行时数据
        runtime_populations = global_vars['test_module'].get('runtime_populations', {})
        
        # 如果是第一次初始化，直接返回
        if not runtime_populations:
            return
            
        # 获取所有环境的数据
        all_time_points = []
        for env_data in runtime_populations.values():
            all_time_points.extend(map(int, env_data.keys()))
        
        # 去重并排序
        time_points = sorted(set(all_time_points))
        
        # 找到最接近的时间点
        closest_time = None
        min_diff = float('inf')
        
        for time_point in time_points:
            diff = abs(time_point - current_eval)
            if diff < min_diff:
                min_diff = diff
                closest_time = time_point
        
        if closest_time is not None:
            # 获取所有环境在最近时间点的种群数据
            populations = []
            for env_data in runtime_populations.values():
                if closest_time in env_data:
                    populations.append(env_data[closest_time])
            
            # 更新图表
            canvas = global_vars['test_module']['canvas']
            ax = global_vars['test_module']['ax']
            
            # 清空当前图表
            ax.clear()
            
            # 绘制所有环境的种群
            for population in populations:
                draw_PF(population, ax)
            
            canvas.draw()
            
    except Exception as e:
        print(f"[错误] 更新进度条时出错: {str(e)}")