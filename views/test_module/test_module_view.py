import threading
import tkinter as tk
from tkinter import ttk
from functools import partial
import os

from matplotlib import pyplot as plt, gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.gridspec import GridSpec
from matplotlib.figure import Figure

from views.common.GlobalVar import global_vars
from views.common.common_components import create_column, create_separator
from views.common.responsive_workspace import ResponsiveWorkspace, scrollable_content
from views.components.collapsible_frame import CollapsibleFrame
from views.test_module.test_module_handler import (
    on_dynamic_select, on_search_select, load_dynamic_data,
    load_search_data, on_problem_select, load_problem_data,
    get_problem_summary, update_label,
    on_continue_button_click, on_pause_button_click,
    on_stop_button_click, on_save_button_click, update_progress_control,
    on_scale_change, load_selected_result, update_result_display
)
from views.components.collapsible_listbox import CollapsibleListbox
from utils.run_executor import start_live_chart_pump
from utils.test_runtime import set_run_status


def create_dynamic_strategy_section(frame):
    """创建动态策略部分"""
    label_dynamic = ttk.Label(frame, text="动态响应策略", font=("Arial", 12, "bold"), style='success')
    label_dynamic.pack(anchor="w", pady=10)

    # Create a Frame to hold the Treeview and Scrollbar for Dynamic Strategy
    dynamic_frame = ttk.Frame(frame)
    dynamic_frame.pack(fill="x", pady=10)

    # 获取动态策略算法数据
    dynamic_data = load_dynamic_data()

    # Create a Treeview widget for Dynamic Strategy algorithms
    tv_dynamic = ttk.Treeview(
        dynamic_frame,
        show='headings',
        height=max(3, min(8, len(dynamic_data))),
    )
    tv_dynamic.configure(columns=('name', 'year'))

    # Configure columns
    tv_dynamic.column('name', width=150, anchor='w', stretch=True)
    tv_dynamic.column('year', width=60, anchor='center', stretch=False)

    # Set column headings
    tv_dynamic.heading('name', text='算法名称', anchor='w')
    tv_dynamic.heading('year', text='年份', anchor='w')

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
    label_search = ttk.Label(frame, text="搜索算法", font=("Arial", 12, "bold"), style='info')
    label_search.pack(anchor="w", pady=10)

    # Create a Frame to hold the Treeview and Scrollbar for Search Algorithm
    search_frame = ttk.Frame(frame)
    search_frame.pack(fill="x", pady=10)

    # 获取搜索算法数据
    search_data = load_search_data()

    # Create a Treeview widget for Search Algorithms
    tv_search = ttk.Treeview(
        search_frame,
        show='headings',
        height=max(3, min(8, len(search_data))),
    )
    tv_search.configure(columns=('name', 'year'))

    # Configure columns
    tv_search.column('name', width=150, anchor='w', stretch=True)
    tv_search.column('year', width=60, anchor='center', stretch=False)

    # Set column headings
    tv_search.heading('name', text='算法名称', anchor='w')
    tv_search.heading('year', text='年份', anchor='w')

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
    label_problem = ttk.Label(frame, text="测试问题", font=("Arial", 12, "bold"), style='warning')
    label_problem.pack(anchor="w", pady=10)

    # Create a Frame to hold the Treeview and Scrollbar for Problem Selection
    problem_frame = ttk.Frame(frame)
    problem_frame.pack(fill="x", pady=10)

    # 获取测试问题数据
    problem_data = load_problem_data()

    # Create a Treeview widget for Problem Selection
    tv_problem = ttk.Treeview(
        problem_frame,
        show='headings',
        height=max(5, min(8, len(problem_data))),
    )
    tv_problem.configure(columns=('name', 'category', 'constraints'))

    # Configure columns
    tv_problem.column('name', width=90, anchor='w', stretch=True)
    tv_problem.column(
        'category',
        width=90,
        minwidth=90,
        anchor='center',
        stretch=False,
    )
    tv_problem.column(
        'constraints',
        width=62,
        minwidth=62,
        anchor='center',
        stretch=False,
    )

    # Set column headings
    tv_problem.heading('name', text='问题', anchor='w')
    tv_problem.heading('category', text='约束类型', anchor='center')
    tv_problem.heading('constraints', text='约束数', anchor='center')

    # 插入数据
    for data in problem_data:
        tv_problem.insert(
            '',
            'end',
            values=(
                data["name"],
                "有约束" if data["constraints"] else "无约束",
                data["constraints"],
            ),
            iid=data["folder_name"],
        )

    # Create scrollbar for Treeview (Problem Selection)
    scrollbar_problem = ttk.Scrollbar(problem_frame, orient='vertical', command=tv_problem.yview)
    tv_problem.configure(yscrollcommand=scrollbar_problem.set)

    # Place the Treeview and Scrollbar in the problem_frame
    tv_problem.pack(side="left", fill="x", expand=True)
    scrollbar_problem.pack(side="right", fill="y", padx=(5, 0))

    # Set the default selection to the first item
    tv_problem.selection_set(tv_problem.get_children()[0])

    global_vars['test_module'].pop('problem_description_label', None)

    return tv_problem

def create_algorithm_selection(frame):
    """创建完整的算法选择区域"""
    label_algo = ttk.Label(frame, text="算法与问题", font=("Arial", 12, "bold"))
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
    label_dynamic_response = ttk.Label(frame, text="参数设置", font=("Arial", 12, "bold"))
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
                           text="运行与回放",
                           font=("Arial", 12, "bold"))
    label_result.pack(pady=10)

    # ==================== 主容器框架 ====================
    result_frame = ttk.Frame(frame)
    result_frame.pack(fill='both', expand=True, padx=5, pady=5)

    # 1. 顶部控制栏（结果指标选择）
    top_frame = ttk.Frame(result_frame)
    top_frame.grid(row=0, column=0, sticky='ew', pady=(0, 6))
    result_frame.columnconfigure(0, weight=1)
    result_frame.rowconfigure(1, weight=1)

    # 创建可折叠的Listbox
    result_listbox = CollapsibleListbox(top_frame, "显示图表", style='primary')
    result_listbox.pack(side="left", fill='x', expand=True)
    # 从config.json中读取结果指标
    config_path = os.path.join("plots", "test_module", "config.json")
    with open(config_path, "r") as f:
        import json
        config = json.load(f)
        for indicator in config["result_indicator"]:
            result_listbox.insert(tk.END, indicator)
    
    # 添加保存结果的单选框
    save_var = tk.BooleanVar(value=False)
    save_checkbox = ttk.Checkbutton(
        top_frame,
        text="自动保存",
        variable=save_var,
        style='primary.TCheckbutton'
    )
    save_checkbox.pack(side="left", padx=(10, 0))

    status_label = ttk.Label(result_frame, text="", wraplength=500, anchor='w')
    status_label.grid(row=1, column=0, sticky='ew', pady=(0, 4))
    status_label.bind('<Configure>', lambda event: status_label.configure(
        wraplength=max(100, event.width - 8)))
    global_vars['test_module']['status_label'] = status_label
    result_frame.rowconfigure(1, weight=0)
    result_frame.rowconfigure(2, weight=1)
    
    # 将保存选项添加到全局变量中
    global_vars['test_module']['save_result'] = save_var

    # 2. 中间内容区域（仅图表）
    content_frame = ttk.Frame(result_frame)
    content_frame.grid(row=2, column=0, sticky='nsew')


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
                ax = fig.add_subplot(required_ax_count, 1, i + 1)
                ax.tick_params(axis='both', labelsize=9)
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
    # A pyplot figure creates a native macOS manager that doubles its DPI.
    # Construct the embedded figure directly so Tk owns sizing from the start.
    fig = Figure(figsize=(6, 3), dpi=100, layout='constrained')
    ax = fig.add_subplot(1, 1, 1)
    ax.tick_params(axis='both', labelsize=9)

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
    start_live_chart_pump(canvas.get_tk_widget())
    # 3. 底部控制面板（一行两列布局）
    bottom_frame = ttk.Frame(result_frame)
    bottom_frame.grid(row=3, column=0, sticky='ew', pady=(6, 0))

    # ===== 左侧：控制按钮 =====
    left_panel = ttk.LabelFrame(bottom_frame,
                              text="运行控制",
                              padding=(10, 10),
                              width=120)  # 固定宽度
    left_panel.pack(side='top', fill='x', pady=(0, 4))

    # 垂直排列的按钮
    btn_continue = ttk.Button(
        left_panel,
        text="开始 / 继续",
        style='info.TButton',
        width=10,
        command=on_continue_button_click  # 恢复运行
    )
    btn_continue.pack(side='left', padx=3)

    # ⏸ Pause（暂停）
    btn_pause = ttk.Button(
        left_panel,
        text="暂停",
        style='warning.TButton',
        width=8,
        command=on_pause_button_click  # 暂停运行
    )
    btn_pause.pack(side='left', padx=3)

    # Terminate（终止）
    btn_terminate = ttk.Button(
        left_panel,
        text="终止",
        style='danger.TButton',
        width=8,
        command=on_stop_button_click  # 强制终止
    )
    btn_terminate.pack(side='left', padx=3)

    btn_save = ttk.Button(left_panel, text="保存结果", width=8,
                          command=on_save_button_click)
    btn_save.pack(side='left', padx=3)
    global_vars['test_module'].update(pause_button=btn_pause,
                                      stop_button=btn_terminate,
                                      manual_save_button=btn_save)
    set_run_status(global_vars['test_module'].get('run_status', 'idle'))

    # ===== 右侧：进度控制 =====
    right_panel = ttk.LabelFrame(bottom_frame,
                                 text="回放时间轴",
                                 padding=(10, 10))
    right_panel.pack(side='top', fill='x')

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
    scale.pack(fill='x', pady=(4, 4))
    
    # 保存进度条引用到全局变量
    if 'test_module' not in global_vars:
        global_vars['test_module'] = {}
    global_vars['test_module']['scale'] = scale

    # 刻度标签
    scale_labels = ttk.Frame(right_panel)
    scale_labels.pack(fill='x')

    # 动态生成刻度标签
    num_labels = 5
    for i in range(num_labels):
        ttk.Label(scale_labels,
                  text=f"{i * (100 // (num_labels - 1))}%",
                  font=("Arial", 7)
                  ).pack(side='left', expand=True)

    # 控制标签组
    label_frame = ttk.Frame(right_panel)
    label_frame.pack(fill='x', pady=(4, 0))

    # 显示当前变化次数的标签
    current_label = ttk.Label(label_frame, text="当前评估次数： 0", font=("Arial", 10))
    current_label.pack(side='top', anchor='w')

    # 显示总的变化次数的标签
    total_label = ttk.Label(label_frame, text="总评估次数： 0", font=("Arial", 10))
    total_label.pack(side='top', anchor='w')

    # 保存控件引用到全局变量
    global_vars['test_module']['current_label'] = current_label
    global_vars['test_module']['total_label'] = total_label

    # 绑定进度条变化事件
    scale.configure(command=lambda val: on_scale_change(val, current_label, total_label))

    # 初始更新进度控制
    update_progress_control(scale, current_label, total_label)


def create_result_selection(frame):
    label_result = ttk.Label(frame,
                           text="历史结果",
                           font=("Arial", 12, "bold"))
    label_result.pack(pady=10)
    """创建结果选择区域（三行布局）"""
    # 主容器
    selection_frame = ttk.Frame(frame)
    selection_frame.pack(fill='both', expand=True, padx=5, pady=5)
    selection_frame.columnconfigure(0, weight=1)
    selection_frame.rowconfigure(2, weight=1)

    # ===== 第一行：算法/问题选择 =====
    row1 = ttk.Frame(selection_frame)
    row1.grid(row=0, column=0, sticky='ew', pady=(0, 8))

    # 创建文件选择框架
    file_frame = ttk.Frame(row1)
    file_frame.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 4))
    row1.grid_columnconfigure(0, weight=4)  # 文件选择框架占据4份

    # 创建文件路径输入框
    file_path_var = tk.StringVar()
    file_entry = ttk.Entry(file_frame, textvariable=file_path_var, state='readonly', width=15)
    file_entry.pack(side='left', padx=(0, 5), fill='x', expand=True)

    # 创建文件选择按钮
    def select_history_file():
        from tkinter import filedialog
        
        initial_dir = os.path.join(os.getcwd(), "results")
        file_path = filedialog.askopenfilename(
            title="选择历史记录文件",
            initialdir=initial_dir,
            filetypes=[("JSON files", "*.json")]
        )
        
        if file_path:
            file_path_var.set(file_path)

    select_btn = ttk.Button(
        file_frame, 
        text="选择文件",
        command=select_history_file,
        width=10
    )
    select_btn.pack(side='left')

    # ===== 第二行：指标选择 =====
    row2 = ttk.Frame(selection_frame)
    row2.grid(row=1, column=0, sticky='ew', pady=(0, 8))

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
        handler_on_metric_change(event, file_path_var, metric_var, metric_value)
    
    metric_combobox.bind('<<ComboboxSelected>>', on_metric_change)

    # 在加载结果时更新指标显示
    def on_load_button_click():
        from views.test_module.test_module_handler import on_load_button_click as handler_on_load_button_click
        handler_on_load_button_click(file_path_var, metric_var, metric_value, param_text)

    load_button = ttk.Button(
        row1,
        text="加载并回放",
        style='info.TButton',
        command=on_load_button_click
    )
    load_button.grid(row=1, column=0, columnspan=2, sticky='ew')
    row1.grid_columnconfigure(1, weight=1)  # 按钮占据1份

    # ===== 第三行：参数显示 =====
    row3 = ttk.Frame(selection_frame)
    row3.grid(row=2, column=0, sticky='nsew')

    # 参数文本框
    param_text = tk.Text(
        row3,
        height=8,
        width=12,
        font=('Courier New', 9),
        wrap='word',
        padx=5,
        pady=5
    )
    scrollbar = ttk.Scrollbar(row3, orient='vertical', command=param_text.yview)
    param_text.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side='right', fill='y')
    param_text.pack(side='left', fill='both', expand=True)

    # 初始参数内容
    params = """"""
    param_text.insert('1.0', params)
    param_text.configure(state='disabled')  # 设为只读

def create_test_module_view(frame_main):
    workspace = ResponsiveWorkspace(frame_main, ("算法与问题", "参数设置", "运行与回放", "历史结果"))
    global_vars['test_module']['workspace'] = workspace
    create_algorithm_selection(scrollable_content(workspace.panels[0]))
    parameter_content = scrollable_content(workspace.panels[1])
    global_vars['test_module']['parameter_content'] = parameter_content
    create_parameter_settings(parameter_content)
    create_result_display(workspace.panels[2])
    create_result_selection(workspace.panels[3])
