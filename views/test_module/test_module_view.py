import threading
import tkinter as tk
from tkinter import ttk
from functools import partial

from matplotlib import pyplot as plt, gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.gridspec import GridSpec

from views.common.GlobalVar import global_vars
from views.common.common_components import create_column, create_separator
from views.components.collapsible_frame import CollapsibleFrame
from views.test_module.test_module_handler import (
    on_dynamic_select, on_search_select, load_dynamic_data,
    load_search_data, on_problem_select, load_problem_data,
    update_label, on_continue_button_click, on_pause_button_click,
    on_stop_button_click, load_selected_result, update_progress_control, update_result_display,
    on_scale_change
)
from plots.test_module.draw_population import draw_IGD_curve, draw_PF, draw_PS
from views.components.collapsible_listbox import CollapsibleListbox


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
    label_search = ttk.Label(frame, text="Search Algorithm", font=("Arial", 12, "bold"), style='info')
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
    label_problem = ttk.Label(frame, text="Select Problem", font=("Arial", 12, "bold"), style='warning')
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
    
    # 创建Dynamic Strategy的可折叠框架
    dynamic_collapsible = CollapsibleFrame(frame, dynamic_response_name.get(), style='success')
    dynamic_collapsible.pack(fill="x", pady=5)
    config_for_dynamic_response = dynamic_collapsible.get_content_frame()

    # 监听 selected_dynamic 的变化，实时更新 Label 和填空内容
    dynamic_response_name.trace_add("write", lambda *args: (
        dynamic_collapsible.set_title(dynamic_response_name.get()),
        update_label(None, config_for_dynamic_response, "selected_dynamic")
    ))

    # 获取 selected_search 的值
    search_name = global_vars['test_module'].get("selected_search")
    
    # 创建Search Algorithm的可折叠框架
    search_collapsible = CollapsibleFrame(frame, search_name.get(), style='info')
    search_collapsible.pack(fill="x", pady=5)
    config_for_search = search_collapsible.get_content_frame()

    # 监听 selected_search 的变化，实时更新 Label 和填空内容
    search_name.trace_add("write", lambda *args: (
        search_collapsible.set_title(search_name.get()),
        update_label(None, config_for_search, "selected_search")
    ))

    # 获取 selected_problem 的值
    problem_name = global_vars['test_module'].get("selected_problem")
    
    # 创建Problem的可折叠框架
    problem_collapsible = CollapsibleFrame(frame, problem_name.get(), style='warning')
    problem_collapsible.pack(fill="x", pady=5)
    config_for_problem = problem_collapsible.get_content_frame()

    # 监听 selected_problem 的变化，实时更新 Label 和填空内容
    problem_name.trace_add("write", lambda *args: (
        problem_collapsible.set_title(problem_name.get()),
        update_label(None, config_for_problem, "selected_problem")
    ))


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

    # 创建可折叠的Listbox
    result_listbox = CollapsibleListbox(top_frame, "Result Indicator", style='primary')
    result_listbox.pack(side="left", fill='x', expand=True)
    result_listbox.insert(tk.END, "Pareto Front")
    result_listbox.insert(tk.END, "Pareto Set")
    result_listbox.insert(tk.END, "IGD")
    
    # 添加保存结果的单选框
    save_var = tk.BooleanVar(value=False)
    save_checkbox = ttk.Checkbutton(
        top_frame,
        text="Save Results",
        variable=save_var,
        style='primary.TCheckbutton'
    )
    save_checkbox.pack(side="left", padx=(10, 0))
    
    # 将保存选项添加到全局变量中
    global_vars['test_module']['save_result'] = save_var

    # 2. 中间内容区域（仅图表）
    content_frame = ttk.Frame(result_frame)
    content_frame.pack(fill='both', expand=True)


    selected_results = []
    global_vars['test_module']['result_to_show'] = selected_results
    # 绑定 Listbox 的选择变化事件
    def on_result_select(event):
        # 获取选中的选项
        selected_indices = result_listbox.listbox.curselection()
        # 更新全局变量中的 selected_results
        global_vars['test_module']['result_to_show'] = [result_listbox.listbox.get(i) for i in selected_indices]

        # 获取当前 fig 中的 ax 数目
        result_to_show = global_vars['test_module']['result_to_show']
        current_ax_count = len(fig.axes)
        # 获取需要显示的图表数目
        required_ax_count = len(result_to_show)
        # 如果需要的 ax 数目与当前的 ax 数目不一致，重新创建所有 ax
        if required_ax_count != current_ax_count:
            lock = global_vars['test_module']['canvas_lock']
            # 获取锁
            lock.acquire()
            # 清空当前 fig 中的所有 ax
            fig.clf()
            # 重新创建所需数量的 ax
            for i in range(required_ax_count):
                fig.add_subplot(required_ax_count, 1, i + 1)
            global_vars['test_module']['canvas_version']+=1
            lock.release()
    
    # 绑定事件
    result_listbox.bind('<<ListboxSelect>>', on_result_select)
    
    # 确保在绑定事件后设置默认选择
    def set_default_selection():
        result_listbox.listbox.selection_set(0)
        # 手动触发选择事件
        on_result_select(None)
    
    # 使用 after 方法确保在组件完全初始化后设置默认选择
    result_listbox.after(100, set_default_selection)

    # 图表区域（自适应）
    fig= plt.figure(figsize=(6, 3))
    fig.add_subplot(1,1,1)

    # 调整布局
    fig.tight_layout()

    # 如果已有画布，先销毁旧画布
    if global_vars['test_module'].get('canvas') is not None:
        try:
            global_vars['test_module']['canvas'].get_tk_widget().destroy()
            global_vars['test_module']['canvas'] = None
        except Exception as e:
            print(f"[警告] 销毁旧画布失败: {e}")

    # 创建新画布
    canvas = FigureCanvasTkAgg(fig, master=content_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(side='top', fill='both', expand=True)

    # 保存画布引用
    global_vars['test_module']['canvas'] = canvas
    global_vars['test_module']['canvas_version'] = 0
    global_vars['test_module']['canvas_lock'] = threading.RLock()
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
        state='normal'  # 始终可拖动
    )
    scale.pack(fill='x', pady=(20, 10))
    
    # 保存进度条引用到全局变量
    if 'test_module' not in global_vars:
        global_vars['test_module'] = {}
    global_vars['test_module']['scale'] = scale

    # 刻度标签
    scale_labels = ttk.Frame(right_panel)
    scale_labels.pack(fill='x')

    # 动态生成刻度标签
    num_labels = 11  # 刻度标签数量（0, 25, 50, 75, 100）
    for i in range(num_labels):
        ttk.Label(scale_labels,
                  text=f"{i * (100 // (num_labels - 1))}%",
                  font=("Arial", 7)
                  ).pack(side='left', expand=True)

    # 控制标签组
    label_frame = ttk.Frame(right_panel)
    label_frame.pack(fill='x', pady=(10, 20))

    # 显示当前变化次数的标签
    current_label = ttk.Label(label_frame, text="Current Change: 0", font=("Arial", 10))
    current_label.pack(side='left', padx=10)

    # 显示总的变化次数的标签
    total_label = ttk.Label(label_frame, text="Total Change: 0", font=("Arial", 10))
    total_label.pack(side='right', padx=10)

    # 保存控件引用到全局变量
    global_vars['test_module']['current_label'] = current_label
    global_vars['test_module']['total_label'] = total_label

    # 绑定进度条变化事件
    scale.configure(command=lambda val: on_scale_change(val, current_label, total_label))

    # 初始更新进度控制
    update_progress_control(scale, current_label, total_label)


def create_result_selection(frame):
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
    row1.pack(fill='x', pady=(0, 5), expand=True)

    # 算法选择下拉框
    algo_combobox = ttk.Combobox(
        row1,
        width=30,
        state='readonly'
    )
    algo_combobox.grid(row=0, column=0, sticky='ew', padx=(0, 5))
    row1.grid_columnconfigure(0, weight=4)  # 下拉框占据4份

    # 绑定下拉框点击事件
    def on_combobox_click(event):
        from views.test_module.test_module_handler import update_result_combobox
        update_result_combobox(algo_combobox)

    algo_combobox.bind('<Button-1>', on_combobox_click)  # 点击时刷新列表

    # 初始更新结果列表
    from views.test_module.test_module_handler import update_result_combobox
    update_result_combobox(algo_combobox)

    # ===== 第二行：指标选择 =====
    row2 = ttk.Frame(selection_frame)
    row2.pack(fill='x', pady=(0, 5))

    # 指标选择下拉框
    metric_var = tk.StringVar()
    metric_combobox = ttk.Combobox(
        row2,
        textvariable=metric_var,
        values=["MIGD", "MGD", "MHV"],
        width=8,
        state='readonly'
    )
    metric_combobox.pack(side='left')
    metric_combobox.set("MIGD")  # 默认值

    # 指标值显示
    metric_value = ttk.Label(row2, text="0.0000", font=('Arial', 10))
    metric_value.pack(side='left', padx=10)
    
    # 绑定指标选择事件
    def on_metric_change(event):
        from views.test_module.test_module_handler import on_metric_change as handler_on_metric_change
        handler_on_metric_change(event, algo_combobox, metric_var, metric_value)
    
    metric_combobox.bind('<<ComboboxSelected>>', on_metric_change)

    # 在加载结果时也更新指标显示
    def on_load_button_click():
        from views.test_module.test_module_handler import on_load_button_click as handler_on_load_button_click
        handler_on_load_button_click(algo_combobox, metric_var, metric_value, param_text)

    load_button = ttk.Button(
        row1,
        text="加载",
        style='info.TButton',
        command=on_load_button_click
    )
    load_button.grid(row=0, column=1, sticky='ew')
    row1.grid_columnconfigure(1, weight=1)  # 按钮占据1份

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
    params = """"""
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
