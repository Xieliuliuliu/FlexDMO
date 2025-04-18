import gc
import threading
from tkinter import ttk

from matplotlib import pyplot as plt

from utils.information_parser import get_dynamic_response_config, get_search_algorithm_config, get_problem_config, \
    get_all_dynamic_strategy, get_all_search_algorithm, get_all_problem, find_match_response_strategy, \
    find_match_problem, find_match_search_algorithm
from utils.run_executor import run_in_test_mode, delete_state_in_test_mode, listen_pipe
from views.common.GlobalVar import global_vars



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
