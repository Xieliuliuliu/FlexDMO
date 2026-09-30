import gc
from tkinter import ttk
import os
import tkinter as tk
from tkinter import messagebox, filedialog
import math

from matplotlib import pyplot as plt

from utils.information_parser import get_dynamic_response_config, get_search_algorithm_config, get_problem_config, \
    get_all_dynamic_strategy, get_all_search_algorithm, get_all_problem, find_match_response_strategy, \
    find_match_problem, find_match_search_algorithm
from utils.run_executor import (
    delete_state_in_test_mode,
    draw_chart,
    run_in_test_mode,
    stop_live_chart_pump,
)
from views.common.GlobalVar import global_vars
from utils.result_io import load_test_module_information_results
from utils.result_io import save_test_module_information_results
from utils.test_runtime import test_run_active, set_run_status


PARAMETER_LABELS = {
    "decision_num": "决策变量数",
    "n": "环境变化强度",
    "tau": "变化间隔（代）",
    "total_evaluate_time": "环境总数",
    "solution_num": "种群规模",
    "neighbor_size": "邻域大小",
    "max_replacements": "最大替换数量",
    "differential_weight": "差分权重",
    "replacement_rate": "种群替换比例",
    "mutation_probability": "变异概率",
    "distribution_index": "变异分布指数",
    "ar_order": "自回归阶数",
    "history_length": "历史记录长度",
    "cluster_num": "聚类数量",
    "weak_learners": "弱学习器数量",
    "random_multiplier": "候选种群倍数",
    "covariance_regularization": "协方差正则系数",
    "key_points": "预测关键点数量",
    "regularization": "回归正则系数",
    "predicted_fraction": "预测个体比例",
    "mutation_fraction": "变异个体比例",
    "noise_scale": "采样噪声强度",
    "seed": "随机种子",
    "delta": "邻域选择概率",
    "proM": "变异概率",
    "disM": "变异分布指数",
    "proC": "交叉概率",
    "disC": "交叉分布指数",
    "K": "局部模型数量",
    "u": "训练样本数量",
    "hidden_size": "隐藏层大小",
    "dropout": "随机失活比例",
    "lr": "学习率",
}


def format_parameter_label(parameter):
    friendly = PARAMETER_LABELS.get(parameter)
    return friendly if friendly else parameter


def validate_runtime_config(runtime_config):
    """Return actionable validation messages before a process is started."""
    errors = []
    positive_parameters = {
        "decision_num",
        "n",
        "tau",
        "total_evaluate_time",
        "solution_num",
        "neighbor_size",
        "max_replacements",
        "hidden_size",
        "u",
        "disM",
        "disC",
        "K",
        "lr",
        "distribution_index",
        "ar_order",
        "history_length",
        "cluster_num",
        "weak_learners",
        "random_multiplier",
        "covariance_regularization",
        "key_points",
        "regularization",
    }
    probability_parameters = {
        "delta",
        "dropout",
        "proM",
        "proC",
        "predicted_fraction",
        "mutation_fraction",
    }
    integer_parameters = {
        "ar_order",
        "history_length",
        "cluster_num",
        "weak_learners",
        "random_multiplier",
        "key_points",
    }
    positive_probability_parameters = {
        "replacement_rate",
        "mutation_probability",
    }

    for section_name, parameters in runtime_config.items():
        for parameter, raw_value in parameters.items():
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                errors.append(f"{parameter}: must be a number")
                continue
            if not math.isfinite(value):
                errors.append(f"{parameter}: must be finite")
            elif parameter in integer_parameters and not value.is_integer():
                errors.append(f"{parameter}: must be an integer")
            elif parameter in positive_parameters and value <= 0:
                errors.append(f"{parameter}: must be greater than 0")
            elif (
                parameter in positive_probability_parameters
                and not 0 < value <= 1
            ):
                errors.append(
                    f"{parameter}: must be greater than 0 and at most 1"
                )
            elif parameter in probability_parameters and not 0 <= value <= 1:
                errors.append(f"{parameter}: must be between 0 and 1")

    dynamic_parameters = runtime_config.get("selected_dynamic", {})
    try:
        ar_order = float(dynamic_parameters["ar_order"])
        history_length = float(dynamic_parameters["history_length"])
        if (
            math.isfinite(ar_order)
            and math.isfinite(history_length)
            and history_length <= ar_order
        ):
            errors.append(
                "history_length: must be greater than ar_order"
            )
    except (KeyError, TypeError, ValueError):
        pass
    try:
        predicted_fraction = float(
            dynamic_parameters["predicted_fraction"]
        )
        mutation_fraction = float(
            dynamic_parameters["mutation_fraction"]
        )
        if (
            math.isfinite(predicted_fraction)
            and math.isfinite(mutation_fraction)
            and predicted_fraction + mutation_fraction > 1
        ):
            errors.append(
                "predicted_fraction + mutation_fraction: "
                "must not exceed 1"
            )
    except (KeyError, TypeError, ValueError):
        pass
    try:
        if float(dynamic_parameters["key_points"]) < 2:
            errors.append("key_points: must be at least 2")
    except (KeyError, TypeError, ValueError):
        pass
    try:
        if float(dynamic_parameters["noise_scale"]) < 0:
            errors.append("noise_scale: must be non-negative")
    except (KeyError, TypeError, ValueError):
        pass
    return errors


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
        description_label = global_vars['test_module'].get(
            'problem_description_label'
        )
        if description_label is not None:
            description_label.config(
                text=get_problem_summary(selected_value)
            )


def get_problem_summary(problem_name):
    """Build a compact user-facing summary for the selected problem."""
    problem = next(
        (
            item
            for item in get_all_problem()
            if item["name"] == problem_name
        ),
        None,
    )
    if problem is None:
        return ""
    description = problem.get("description", "")
    return description

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
    
    # 如果label不为None，则更新标签文本
    if label is not None:
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
    for param, default_value in config.items():
        # 创建参数容器
        param_frame = ttk.Frame(fill_frame)
        param_frame.pack(fill="x", pady=2)
        param_frame.grid_columnconfigure(0, weight=1)

        # 创建标签
        param_label = ttk.Label(
            param_frame,
            text=f"{format_parameter_label(param)}: ",
            font=("Arial", 10),
            anchor="w",
            justify="left",
            wraplength=145,
        )
        param_label.grid(
            row=0,
            column=0,
            sticky="ew",
            padx=(1, 4),
        )

        
        # 创建 Entry 控件
        param_entry = ttk.Entry(param_frame, width=9)
        param_entry.insert(0, default_value)  # 设置默认值
        param_entry.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(0, 5),
        )
        
        # 设置事件监听，实时获取用户修改的配置
        def on_entry_change(event, param=param, entry=param_entry):
            # 更新全局配置，保存用户修改的值
            global_vars['test_module']['runtime_config'][config_type][param] = entry.get()
            # print(global_vars['test_module'])

        # 监听内容变化
        param_entry.bind("<KeyRelease>", on_entry_change)  # 监听键盘输入，实时更新

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
    result_to_show = global_vars['test_module']['result_to_show']  # 获取 result_to_show 的当前值
    # print(f"Result to Show: {result_to_show}")

    # 获取并打印 problem 相关信息
    problem_name = global_vars['test_module']['selected_problem'].get()  # 获取 selected_problem 的当前值
    # print(f"Selected Problem: {find_match_problem(problem_name)}")
    runtime_config = global_vars['test_module']['runtime_config']
    validation_errors = validate_runtime_config(runtime_config)
    if validation_errors:
        messagebox.showerror(
            "Invalid parameters",
            "Please correct the following values:\n\n"
            + "\n".join(f"• {error}" for error in validation_errors),
        )
        return

    try:
        run_in_test_mode(
            find_match_response_strategy(response_strategy),
            find_match_search_algorithm(search_algorithm),
            find_match_problem(problem_name),
            result_to_show,
            runtime_config
        )
    except Exception as error:
        set_run_status("failed", f"启动失败：{error}")
        messagebox.showerror("无法启动", str(error))
        return
    workspace = global_vars['test_module'].get('workspace')
    if workspace is not None:
        workspace.show_panel(2)


def on_pause_button_click():
    """处理暂停按钮点击事件"""
    process_entry = global_vars.get('test_module', {})
    if test_run_active() and process_entry.get('process_state') is not None:
        process_entry['process_state'].value = 'pause'
        set_run_status("paused")
    else:
        print("[主进程] 无 process_state，不执行暂停")

def on_stop_button_click():
    """处理停止按钮点击事件"""
    process_entry = global_vars.get('test_module', {})
    if test_run_active():
        set_run_status("stopped")
        delete_state_in_test_mode(clear_history=False)
        scale = process_entry.get('scale')
        if scale is not None:
            scale.configure(state='normal')
            update_progress_control(scale, process_entry['current_label'],
                                    process_entry['total_label'],
                                    start_at_end=True, render_selected=True)
        save_result = process_entry.get('save_result')
        if process_entry.get('runtime_populations') and save_result is not None and save_result.get():
            try:
                path = save_test_module_information_results()
                set_run_status('stopped', f"部分结果已保存：{path}")
            except Exception as error:
                set_run_status('stopped', f"自动保存失败：{error}；请手动保存")
    else:
        print("[主进程] 无 process_state，不执行终止")


def on_save_button_click():
    """Save completed or terminated data even if auto-save was not enabled."""
    if test_run_active():
        messagebox.showinfo("保存结果", "请等待运行完成或终止后再保存结果。")
        return
    if not global_vars['test_module'].get('runtime_populations'):
        messagebox.showinfo("保存结果", "还没有可保存的数据，请先运行或加载结果。")
        return
    directory = filedialog.askdirectory(title="选择结果保存目录", initialdir="results")
    if not directory:
        return
    try:
        path = save_test_module_information_results(directory)
        set_run_status(global_vars['test_module'].get('run_status', 'completed'),
                       f"结果已保存：{path}")
        messagebox.showinfo("保存成功", path)
    except Exception as error:
        messagebox.showerror("保存失败", str(error))


def clear_canvas():
    """彻底释放 Tkinter Canvas + Matplotlib Figure"""

    stop_live_chart_pump()
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
        selected_result (str): 选中的结果显示名称或文件路径
        
    Returns:
        dict: 加载的结果数据，如果加载失败则返回None
    """
    if not selected_result:
        return None
    if test_run_active():
        messagebox.showinfo("暂时无法加载", "优化仍在运行或暂停中，请先终止或等待完成。")
        return None
        
    # 如果输入已经是完整的文件路径，直接使用
    file_path = selected_result
    
    # 加载结果
    result = load_test_module_information_results(file_path)
    if result:
        # 更新global_vars中的数据
        if 'test_module' not in global_vars:
            global_vars['test_module'] = {}
        global_vars['test_module']['runtime_populations'] = result['runtime_populations']
        global_vars['test_module']['runtime_historical_config'] = result['settings']
        global_vars['test_module'].pop('pending_live_information', None)
        set_run_status("replay")
        print(f"成功加载结果: {selected_result}")
    else:
        print(f"加载结果失败: {selected_result}")
        set_run_status("failed", "结果文件无法加载，请检查文件格式及所需的问题组件")
        
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
        # 跳过以_开头的属性
        if key.startswith('_'):
            continue
            
        if isinstance(value, dict):
            param_text.insert(tk.END, f"\n{key}:\n")
            for sub_key, sub_value in value.items():
                # 跳过以_开头的子属性
                if sub_key.startswith('_'):
                    continue
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


def build_replay_timeline(runtime_populations):
    """Flatten runtime snapshots into a stable evaluation-ordered timeline."""
    timeline = []
    for environment_key, environment_data in runtime_populations.items():
        for evaluation_key, information in environment_data.items():
            timeline.append(
                (int(evaluation_key), int(environment_key), information)
            )
    return sorted(timeline, key=lambda item: (item[0], item[1]))


def update_progress_control(
    scale,
    current_label,
    total_label,
    start_at_end=False,
    render_selected=False,
):
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
        current_label.config(text="当前评估次数： 0")
        total_label.config(text="总评估次数： 0")
        return
    
    test_state = global_vars['test_module']
    runtime_populations = test_state.get('runtime_populations', {})
    
    # 如果没有数据，显示默认值
    if not runtime_populations:
        test_state.pop('replay_timeline', None)
        scale.configure(from_=0, to=100)
        scale.set(0)
        current_label.config(text="当前评估次数： 0")
        total_label.config(text="总评估次数： 0")
        return
    
    try:
        timeline = build_replay_timeline(runtime_populations)
        if not timeline:
            raise ValueError("运行记录中没有可回放的快照")
        test_state['replay_timeline'] = timeline

        selected_index = len(timeline) - 1 if start_at_end else 0
        selected_evaluation, _, selected_information = timeline[selected_index]
        last_evaluation = timeline[-1][0]
        
        # 滑块使用连续的快照序号，避免稀疏评估次数造成大片无变化区域。
        scale.configure(from_=0, to=max(0, len(timeline) - 1))
        test_state['suppress_replay_callback'] = True
        try:
            scale.set(selected_index)
        finally:
            test_state.pop('suppress_replay_callback', None)
        
        # 更新标签
        current_label.config(text=f"当前评估次数： {selected_evaluation}")
        total_label.config(text=f"总评估次数： {last_evaluation}")

        if render_selected:
            draw_chart(selected_information)
        
    except Exception as e:
        print(f"更新进度控制时出错: {e}")
        test_state.pop('replay_timeline', None)
        scale.configure(from_=0, to=100)
        scale.set(0)
        current_label.config(text="当前评估次数： 0")
        total_label.config(text="总评估次数： 0")

def on_scale_change(val, current_label, total_label):
    """处理进度条变化事件
    
    Args:
        val: 进度条当前值（浮点数）
        current_label: 当前变化次数标签
        total_label: 总变化次数标签
    """
    try:
        test_state = global_vars['test_module']
        if test_state.get('suppress_replay_callback'):
            return

        runtime_populations = test_state.get('runtime_populations', {})
        
        # 如果是第一次初始化，直接返回
        if not runtime_populations:
            return
            
        timeline = test_state.get('replay_timeline')
        if not timeline:
            timeline = build_replay_timeline(runtime_populations)
            test_state['replay_timeline'] = timeline

        if timeline:
            snapshot_index = min(
                max(int(round(float(val))), 0),
                len(timeline) - 1,
            )
            evaluation, _, information = timeline[snapshot_index]
            current_label.config(text=f"当前评估次数： {evaluation}")
            draw_chart(information)


    except Exception as e:
        print(f"[错误] 更新进度条时出错: {str(e)}")

def update_metric_display(result, metric_name, metric_value):
    """更新指标显示
    
    Args:
        result (dict): 结果数据
        metric_name (str): 指标名称
        metric_value (ttk.Label): 指标显示标签
    """
    try:
        # 获取所有环境的种群数据
        runtime_populations = result.get('runtime_populations', {})
        if not runtime_populations:
            metric_value.config(text="0.0000")
            return
            
        # 根据指标类型计算值
        from utils.metrics import calculate_MIGD, calculate_MGD, calculate_MHV
        if metric_name == "MIGD":
            value = calculate_MIGD(runtime_populations)
        elif metric_name == "MGD":
            value = calculate_MGD(runtime_populations)
        elif metric_name == "MHV":
            value = calculate_MHV(runtime_populations)
        else:
            raise ValueError(f"Unknown metric name: {metric_name}")
            
        # 更新标签显示
        metric_value.config(text=f"{value:.4f}")
        
    except Exception as e:
        print(f"[错误] 更新指标显示时出错: {str(e)}")
        metric_value.config(text="0.0000")

def on_load_button_click(file_path_var, metric_var, metric_value, param_text):
    """处理加载按钮点击事件
    
    Args:
        file_path_var: 文件路径变量
        metric_var: 指标变量
        metric_value: 指标值显示标签
        param_text: 参数显示文本框
    """
    file_path = file_path_var.get()
    if not file_path:
        return
        
    result = load_selected_result(file_path)
    if result:
        # 获取进度条
        scale = global_vars['test_module'].get('scale')
        current_label = global_vars['test_module'].get('current_label')
        total_label = global_vars['test_module'].get('total_label')
        
        # 更新显示
        update_result_display(scale, result, param_text, metric_value)
        
        # 更新指标显示
        update_metric_display(result, metric_var.get(), metric_value)
        
        # 调用 on_scale_change 更新图表
        if scale and current_label and total_label:
            on_scale_change(scale.get(), current_label, total_label)
        workspace = global_vars['test_module'].get('workspace')
        if workspace is not None:
            workspace.show_panel(2)

def on_metric_change(event, file_path_var, metric_var, metric_value):
    """处理指标选择变化事件
    
    Args:
        event: 事件对象
        file_path_var: 文件路径变量
        metric_var: 指标变量
        metric_value: 指标值显示标签
    """
    file_path = file_path_var.get()
    if file_path:
        result = load_selected_result(file_path)
        if result:
            update_metric_display(result, metric_var.get(), metric_value)
