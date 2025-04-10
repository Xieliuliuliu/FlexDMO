from tkinter import ttk

import ttkbootstrap
from matplotlib import pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from views.common.GlobalVar import global_vars
from views.common.common_components import create_column, create_separator


import tkinter as tk
from tkinter import ttk

from views.test_module.test_module_handler import on_dynamic_select, on_search_select, load_dynamic_data, \
    load_search_data, on_problem_select, load_problem_data, update_label, on_continue_button_click, \
    on_pause_button_click, on_stop_button_click


def create_dynamic_strategy_section(frame):
    """创建动态策略部分"""
    label_dynamic = ttk.Label(frame, text="Dynamic Strategy", font=("Arial", 12, "bold"), style='success')
    label_dynamic.pack(anchor="w", pady=10)

    # Create a Frame to hold the Treeview and Scrollbar for Dynamic Strategy
    dynamic_frame = ttk.Frame(frame)
    dynamic_frame.pack(fill="x", pady=10)

    # 获取动态策略算法数据
    dynamic_data = load_dynamic_data()

    # Create a Treeview widget for Dynamic Strategy algorithms
    tv_dynamic = ttk.Treeview(dynamic_frame, show='headings', height=8)
    tv_dynamic.configure(columns=('name', 'year'))

    # Configure columns
    tv_dynamic.column('name', width=150, anchor='w', stretch=True)
    tv_dynamic.column('year', width=100, anchor='w', stretch=True)

    # Set column headings
    tv_dynamic.heading('name', text='Algorithm Name', anchor='w')
    tv_dynamic.heading('year', text='Year', anchor='w')

    # 插入数据
    for data in dynamic_data:
        folder, name, year = data.values()
        tv_dynamic.insert('', 'end', values=(name, year), iid=folder)

    # Create scrollbar for Treeview (Dynamic Strategy)
    scrollbar_dynamic = ttk.Scrollbar(dynamic_frame, orient='vertical', command=tv_dynamic.yview)
    tv_dynamic.configure(yscrollcommand=scrollbar_dynamic.set)

    # Place the Treeview and Scrollbar in the dynamic_frame
    tv_dynamic.pack(side="left", fill="x", expand=True)
    scrollbar_dynamic.pack(side="right", fill="y", padx=(5, 0))

    # Set the default selection to the first item
    tv_dynamic.selection_set(tv_dynamic.get_children()[0])

    return tv_dynamic

def create_search_algorithm_section(frame):
    """创建搜索算法部分"""
    label_search = ttk.Label(frame, text="Search Algorithm", font=("Arial", 12, "bold") ,style='info')
    label_search.pack(anchor="w", pady=10)

    # Create a Frame to hold the Treeview and Scrollbar for Search Algorithm
    search_frame = ttk.Frame(frame)
    search_frame.pack(fill="x", pady=10)

    # 获取搜索算法数据
    search_data = load_search_data()

    # Create a Treeview widget for Search Algorithms
    tv_search = ttk.Treeview(search_frame, show='headings', height=8)
    tv_search.configure(columns=('name', 'year'))

    # Configure columns
    tv_search.column('name', width=150, anchor='w', stretch=True)
    tv_search.column('year', width=100, anchor='w', stretch=True)

    # Set column headings
    tv_search.heading('name', text='Algorithm Name', anchor='w')
    tv_search.heading('year', text='Year', anchor='w')

    # 插入数据
    for data in search_data:
        folder, name, year = data.values()
        tv_search.insert('', 'end', values=(name, year), iid=folder)


    # Create scrollbar for Treeview (Search Algorithm)
    scrollbar_search = ttk.Scrollbar(search_frame, orient='vertical', command=tv_search.yview)
    tv_search.configure(yscrollcommand=scrollbar_search.set)

    # Place the Treeview and Scrollbar in the search_frame
    tv_search.pack(side="left", fill="x", expand=True)
    scrollbar_search.pack(side="right", fill="y", padx=(5, 0))

    # Set the default selection to the first item
    tv_search.selection_set(tv_search.get_children()[0])

    return tv_search

def create_problem_selection_section(frame):
    """创建问题选择部分"""
    label_problem = ttk.Label(frame, text="Select Problem", font=("Arial", 12, "bold") ,style='warning')
    label_problem.pack(anchor="w", pady=10)

    # Create a Frame to hold the Treeview and Scrollbar for Problem Selection
    problem_frame = ttk.Frame(frame)
    problem_frame.pack(fill="x", pady=10)

    # 获取测试问题数据
    problem_data = load_problem_data()

    # Create a Treeview widget for Problem Selection
    tv_problem = ttk.Treeview(problem_frame, show='headings', height=8)
    tv_problem.configure(columns=('name',))

    # Configure columns
    tv_problem.column('name', width=150, anchor='w', stretch=True)

    # Set column headings
    tv_problem.heading('name', text='Problem Name', anchor='w')

    # 插入数据
    for data in problem_data:
        folder, name = data.values()
        tv_problem.insert('', 'end', values=(name), iid=folder)

    # Create scrollbar for Treeview (Problem Selection)
    scrollbar_problem = ttk.Scrollbar(problem_frame, orient='vertical', command=tv_problem.yview)
    tv_problem.configure(yscrollcommand=scrollbar_problem.set)

    # Place the Treeview and Scrollbar in the problem_frame
    tv_problem.pack(side="left", fill="x", expand=True)
    scrollbar_problem.pack(side="right", fill="y", padx=(5, 0))

    # Set the default selection to the first item
    tv_problem.selection_set(tv_problem.get_children()[0])

    return tv_problem

def create_algorithm_selection(frame):
    """创建完整的算法选择区域"""
    label_algo = ttk.Label(frame, text="Algorithm selection", font=("Arial", 14, "bold"))
    label_algo.pack(pady=10)  # Span across two columns in the grid, simply use padding with pack

    # 创建并显示各个部分
    tv_dynamic = create_dynamic_strategy_section(frame)
    tv_search = create_search_algorithm_section(frame)
    tv_problem = create_problem_selection_section(frame)

    # 创建 StringVar 用于保存选择的算法和问题
    selected_dynamic = tk.StringVar()
    selected_search = tk.StringVar()
    selected_problem = tk.StringVar()

    global_vars['test_module']['selected_dynamic'] = selected_dynamic
    global_vars['test_module']['selected_search'] = selected_search
    global_vars['test_module']['selected_problem'] = selected_problem

    # 将默认选择项绑定到 StringVar
    selected_dynamic.set(tv_dynamic.item(tv_dynamic.selection()[0], 'values')[0])
    selected_search.set(tv_search.item(tv_search.selection()[0], 'values')[0])
    selected_problem.set(tv_problem.item(tv_problem.selection()[0], 'values')[0])

    # 绑定选择事件
    tv_dynamic.bind('<<TreeviewSelect>>', lambda event: on_dynamic_select(tv_dynamic))
    tv_search.bind('<<TreeviewSelect>>', lambda event: on_search_select(tv_search))
    tv_problem.bind('<<TreeviewSelect>>', lambda event: on_problem_select(tv_problem))


def create_parameter_settings(frame):
    """创建算法选择区域"""
    label_dynamic_response = ttk.Label(frame, text="Parameter settings", font=("Arial", 14, "bold"))
    label_dynamic_response.pack(pady=10)  # Span across two columns in the grid, simply use padding with pack

    # 获取 selected_dynamic 的值
    dynamic_response_name = global_vars['test_module'].get("selected_dynamic")
    label_algo = ttk.Label(frame, text=dynamic_response_name.get(), font=("Arial", 12, "bold"), style="inverse-success", anchor='center')
    label_algo.pack(pady=10, fill='x')

    # 创建用于显示填空内容的框架
    config_for_dynamic_response = ttk.Frame(frame)
    config_for_dynamic_response.pack(pady=10, fill='x')

    # 监听 selected_dynamic 的变化，实时更新 Label 和填空内容
    dynamic_response_name.trace_add("write", lambda *args: update_label(label_algo, config_for_dynamic_response, "selected_dynamic"))

    search_name = global_vars['test_module'].get("selected_search")
    label_search_algo = ttk.Label(frame, text=search_name.get(), font=("Arial", 12, "bold"), style="inverse-info", anchor='center')
    label_search_algo.pack(pady=10, fill='x')

    config_for_search = ttk.Frame(frame)
    config_for_search.pack(pady=10, fill='x')

    # 监听 selected_search 的变化，实时更新 Label 和填空内容
    search_name.trace_add("write", lambda *args: update_label(label_search_algo, config_for_search, "selected_search"))


    problem_name = global_vars['test_module'].get("selected_problem")
    label_problem_algo = ttk.Label(frame, text=problem_name.get(), font=("Arial", 12, "bold"), style="inverse-warning", anchor='center')
    label_problem_algo.pack(pady=10, fill='x')

    config_for_problem = ttk.Frame(frame)
    config_for_problem.pack(pady=10, fill='x')

    # 监听 selected_problem 的变化，实时更新 Label 和填空内容
    problem_name.trace_add("write", lambda *args: update_label(label_problem_algo, config_for_problem, "selected_problem"))


def create_result_display(frame):
    """创建图表显示区域（一行两列底部控制面板）"""
    # ==================== 顶部标题 ====================
    label_result = ttk.Label(frame,
                           text="Result Display",
                           font=("Arial", 14, "bold"))
    label_result.pack(pady=10)

    # ==================== 主容器框架 ====================
    result_frame = ttk.Frame(frame)
    result_frame.pack(fill='both', expand=True, padx=5, pady=5)

    # 1. 顶部控制栏（结果指标选择）
    top_frame = ttk.Frame(result_frame)
    top_frame.pack(side="top", fill="x", pady=(0, 10))

    result_label = ttk.Label(top_frame,
                           text="Result Indicator:",
                           font=("Arial", 11))
    result_label.pack(side="left", padx=(0, 5))
    # 创建 StringVar 并绑定到 result_choose
    result_to_show = tk.StringVar()
    # 创建 Combobox
    result_choose = ttk.Combobox(top_frame, values=['Population',"IGD"], width=25, textvariable=result_to_show,state="readonly")

    # 设置默认选项为第一个
    result_to_show.set(result_choose['values'][0])

    global_vars['test_module']['result_to_show'] = result_to_show
    result_choose.pack(side="left", fill='x', expand=True)

    # 2. 中间内容区域（仅图表）
    content_frame = ttk.Frame(result_frame)
    content_frame.pack(fill='both', expand=True)

    # 图表区域（自适应）
    fig, ax = plt.subplots(figsize=(6, 4))


    canvas = FigureCanvasTkAgg(fig, master=content_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side='top', fill='both', expand=True)

    global_vars['test_module']['canvas'] = canvas
    global_vars['test_module']['ax'] = ax
    # 3. 底部控制面板（一行两列布局）
    bottom_frame = ttk.Frame(result_frame)
    bottom_frame.pack(side="bottom", fill='x', pady=10)

    # ===== 左侧：控制按钮 =====
    left_panel = ttk.LabelFrame(bottom_frame,
                              text="Controls",
                              padding=(10, 10),
                              width=120)  # 固定宽度
    left_panel.pack(side='left', fill='y', padx=(0, 10))

    # 垂直排列的按钮
    btn_continue = ttk.Button(
        left_panel,
        text="▶ Continue",
        style='info.TButton',
        width=12,
        command=on_continue_button_click  # 恢复运行
    )
    btn_continue.pack(pady=3)

    # ⏸ Pause（暂停）
    btn_pause = ttk.Button(
        left_panel,
        text="⏸ Pause",
        style='warning.TButton',
        width=12,
        command=on_pause_button_click  # 暂停运行
    )
    btn_pause.pack(pady=3)

    # Terminate（终止）
    btn_terminate = ttk.Button(
        left_panel,
        text="⛔ Terminate",
        style='danger.TButton',
        width=12,
        command=on_stop_button_click  # 强制终止
    )
    btn_terminate.pack(pady=3)

    # ===== 右侧：进度控制 =====
    right_panel = ttk.LabelFrame(bottom_frame,
                                 text="Progress Control",
                                 padding=(10, 10))
    right_panel.pack(side='left', fill='both', expand=True)

    # 进度条
    scale = ttk.Scale(
        right_panel,
        orient="horizontal",
        from_=0,
        to=100,
        value=0,
        style='info.Horizontal.TScale',
        command=lambda val: update_labels(val)  # 更新标签时，绑定进度条变化
    )
    scale.pack(fill='x', pady=(20, 10))  # 设置上下间距，使其垂直居中

    # 刻度标签
    scale_labels = ttk.Frame(right_panel)
    scale_labels.pack(fill='x')

    # 动态生成刻度标签，并确保它们严格与进度条一致
    num_labels = 11  # 刻度标签数量（0, 25, 50, 75, 100）
    for i in range(num_labels):
        ttk.Label(scale_labels,
                  text=f"{i * (100 // (num_labels - 1))}%",  # 按照比例生成刻度
                  font=("Arial", 7)
                  ).pack(side='left', expand=True)

    # 控制标签组
    label_frame = ttk.Frame(right_panel)
    label_frame.pack(fill='x', pady=(10, 20))

    # 显示当前变化次数的标签
    current_label = ttk.Label(label_frame, text="Current Change: 0", font=("Arial", 10))
    current_label.pack(side='left', padx=10)

    # 显示总的变化次数的标签
    total_label = ttk.Label(label_frame, text="Total Change: 100", font=("Arial", 10))
    total_label.pack(side='right', padx=10)

    # 更新标签内容的函数
    def update_labels(val):
        # 当前变化次数和总变化次数是基于进度条值的
        current_change = int(float(val))  # Convert val to float first, then to int

        total_change = 100  # 假设总变化次数为100（可以根据实际需求进行调整）

        current_label.config(text=f"Current Change: {current_change}")
        total_label.config(text=f"Total Change: {total_change}")


def create_result_selection(frame):
    """创建图表显示区域（一行两列底部控制面板）"""
    # ==================== 顶部标题 ====================
    label_result = ttk.Label(frame,
                           text="Result Selection",
                           font=("Arial", 14, "bold"))
    label_result.pack(pady=10)
    """创建结果选择区域（三行布局）"""
    # 主容器
    selection_frame = ttk.Frame(frame)
    selection_frame.pack(fill='x', padx=5, pady=5)

    # ===== 第一行：算法/问题选择 =====
    row1 = ttk.Frame(selection_frame)
    row1.pack(fill='x', pady=(0, 5), expand=True)  # 添加expand=True

    # 算法选择下拉框
    algo_var = tk.StringVar()
    algo_combobox = ttk.Combobox(
        row1,
        textvariable=algo_var,
        values=["SGEA with MOEA/D on DF1", "DM with NSGA-II on DF13"],
        width=30,  # 明确设置宽度
        state='readonly'
    )
    algo_combobox.pack(side='left', fill='x', expand=True)  # 添加fill和expand
    algo_combobox.set("SGEA with MOEA/D on DF1")  # 默认值


    # ===== 第二行：指标选择 =====
    row2 = ttk.Frame(selection_frame)
    row2.pack(fill='x', pady=(0, 5))

    # 指标选择下拉框
    metric_var = tk.StringVar()
    metric_combobox = ttk.Combobox(
        row2,
        textvariable=metric_var,
        values=["GD", "IGD", "HV"],
        width=8,
        state='readonly'
    )
    metric_combobox.pack(side='left')
    metric_combobox.set("GD")  # 默认值

    # 指标值显示
    metric_value = ttk.Label(row2, text="1.7468", font=('Arial', 10))
    metric_value.pack(side='left', padx=10)

    # ===== 第三行：参数显示 =====
    row3 = ttk.Frame(selection_frame)
    row3.pack(fill='both', expand=True)

    # 参数文本框
    param_text = tk.Text(
        row3,
        height=60,
        width=30,
        font=('Courier New', 9),
        wrap='word',
        padx=5,
        pady=5
    )
    param_text.pack(fill='both', expand=True)

    # 初始参数内容
    params = """<Algorithm: SGEA>
            <Problem: FDA1>
            N: 100
            M: 
            D: 
            maxFE: 10000
            taut: 10
            nt: 10"""
    param_text.insert('1.0', params)
    param_text.configure(state='disabled')  # 设为只读


def create_test_module_view(frame_main):
    # 使用grid布局调整列比例为 1:1:2:1
    frame_main.grid_rowconfigure(0, weight=1)
    frame_main.grid_columnconfigure(0, weight=1)
    frame_main.grid_columnconfigure(2, weight=1)
    frame_main.grid_columnconfigure(4, weight=2)
    frame_main.grid_columnconfigure(6, weight=1)

    # 第一列：Algorithm selection
    frame_left = create_column(frame_main, 0)  # 传递列的位置
    create_algorithm_selection(frame_left)

    # 竖线分隔
    create_separator(frame_main, 1)

    # 第二列：Parameter setting
    frame_center_left = create_column(frame_main, 2)
    create_parameter_settings(frame_center_left)

    # 竖线分隔
    create_separator(frame_main, 3)

    # 第三列：Result display
    frame_center_right = create_column(frame_main, 4)
    create_result_display(frame_center_right)

    # 竖线分隔
    create_separator(frame_main, 5)

    # 第四列：Result selection
    frame_right = create_column(frame_main, 6)
    create_result_selection(frame_right)
