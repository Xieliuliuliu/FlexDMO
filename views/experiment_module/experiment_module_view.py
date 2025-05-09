import tkinter as tk
from tkinter import ttk
from functools import partial

from views.common.GlobalVar import global_vars
from views.common.common_components import create_column, create_separator
from views.components.collapsible_frame import CollapsibleFrame
from views.experiment_module.experiment_module_handler import on_add_button_click, on_dynamic_select, on_problem_select, on_search_select
from views.test_module.test_module_handler import load_dynamic_data, load_problem_data, load_search_data

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
    return tv_problem

def create_algorithm_selection(frame):
    """创建完整的算法选择区域"""
    # 创建主框架并限制宽度
    main_frame = ttk.Frame(frame, width=200)  # 设置固定宽度
    main_frame.pack(fill="both", expand=True)
    main_frame.pack_propagate(False)  # 防止自动调整大小
    
    # 创建标题
    label_algo = ttk.Label(main_frame, text="Algorithm selection", font=("Arial", 14, "bold"))
    label_algo.pack(pady=10)

    # 创建并显示各个部分
    tv_dynamic = create_dynamic_strategy_section(main_frame)
    tv_search = create_search_algorithm_section(main_frame)
    tv_problem = create_problem_selection_section(main_frame)

    # 初始化选中项列表
    global_vars['experiment_module']['selected_dynamic'] = []
    global_vars['experiment_module']['selected_search'] = []
    global_vars['experiment_module']['selected_problem'] = []

    # 绑定选择事件
    tv_dynamic.bind('<<TreeviewSelect>>', lambda event: on_dynamic_select(tv_dynamic))
    tv_search.bind('<<TreeviewSelect>>', lambda event: on_search_select(tv_search))
    tv_problem.bind('<<TreeviewSelect>>', lambda event: on_problem_select(tv_problem))


def create_parameter_settings(frame):
    """创建参数设置区域"""
    # 创建标题
    label_title = ttk.Label(frame, text="Parameter Settings", font=("Arial", 14, "bold"))
    label_title.pack(pady=10)

    # 创建主框架来包含画布和底部栏
    main_frame = ttk.Frame(frame, width=350)  # 在Frame创建时设置宽度
    main_frame.pack(fill="both", expand=True, padx=10)
    main_frame.pack_propagate(False)  # 防止Frame自动调整大小

    # 创建画布容器框架（带边框）
    canvas_frame = ttk.LabelFrame(main_frame, text="parameters", padding=5)
    canvas_frame.pack(side="top", fill="both", expand=True)

    # 创建画布和滚动条
    canvas = tk.Canvas(canvas_frame)
    scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
    
    # 创建内容框架
    content_frame = ttk.Frame(canvas)
    
    # 配置画布
    canvas.configure(yscrollcommand=scrollbar.set)
    
    # 创建窗口
    canvas_window = canvas.create_window((0, 0), window=content_frame, anchor="nw", width=canvas.winfo_width())
    
    # 布局 - 修改为垂直排列
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # 创建底部带边框的栏
    bottom_frame = ttk.LabelFrame(main_frame, text="settings", padding=5)
    bottom_frame.pack(side="top", fill="x", pady=5)

    # 创建输入框架
    input_frame = ttk.Frame(bottom_frame)
    input_frame.pack(fill="x", pady=5)

    # 添加 tau 输入
    ttk.Label(input_frame, text="tau:").pack(side="left", padx=5)
    tau_var = tk.StringVar(value="10,20")
    tau_entry = ttk.Entry(input_frame, textvariable=tau_var, width=8)
    tau_entry.pack(side="left", padx=5)

    # 添加 n 输入
    ttk.Label(input_frame, text="n:").pack(side="left", padx=5)
    n_var = tk.StringVar(value="5,10")
    n_entry = ttk.Entry(input_frame, textvariable=n_var, width=8)
    n_entry.pack(side="left", padx=5)

    # 添加运行次数输入
    ttk.Label(input_frame, text="runs:").pack(side="left", padx=5)
    runs_var = tk.StringVar(value="1")
    runs_entry = ttk.Entry(input_frame, textvariable=runs_var, width=8)
    runs_entry.pack(side="left", padx=5)

    # 添加按钮
    add_button = ttk.Button(input_frame, text="Add", width=6)
    add_button.pack(side="left", padx=2)
    add_button.bind("<Button-1>", on_add_button_click)

    # 保存变量到全局变量
    global_vars['experiment_module']['tau'] = tau_var
    global_vars['experiment_module']['n'] = n_var
    global_vars['experiment_module']['runs'] = runs_var

    # 配置滚动
    def on_configure(event):
        # 获取父窗口的高度
        parent_height = canvas_frame.winfo_height()
        # 设置最大高度为父窗口高度减去标题高度和边距
        max_height = parent_height - label_title.winfo_height() - 20
        # 更新画布滚动区域
        canvas.configure(scrollregion=canvas.bbox("all"))
        # 更新内容框架宽度，减去滚动条宽度
        canvas.itemconfig(canvas_window, width=canvas.winfo_width() - scrollbar.winfo_width())

    def on_mousewheel(event):
        # 获取当前滚动位置
        first, last = canvas.yview()
        # 计算滚动量
        delta = -1 * (event.delta // 120)
        # 如果已经滚动到顶部且继续向上滚动，则不执行
        if first <= 0 and delta < 0:
            return
        # 如果已经滚动到底部且继续向下滚动，则不执行
        if last >= 1 and delta > 0:
            return
        # 滚动画布
        canvas.yview_scroll(delta, "units")

    # 绑定事件
    content_frame.bind('<Configure>', on_configure)
    canvas.bind('<Configure>', on_configure)
    canvas.bind_all("<MouseWheel>", on_mousewheel)

    # 保存框架到全局变量
    global_vars['experiment_module']['parameter_frame'] = content_frame

def create_run_management(frame):
    """创建运行管理部分"""
    # 创建标题
    label_title = ttk.Label(frame, text="Run Management", font=("Arial", 14, "bold"))
    label_title.pack(pady=10)
    
    # 创建主框架
    main_frame = ttk.Frame(frame)
    main_frame.pack(fill="both", expand=True, padx=10)
    
    # 创建任务列表框架（带滚动条）
    task_container = ttk.Frame(main_frame)
    task_container.pack(fill="both", expand=True)
    
    # 创建画布和滚动条
    canvas = tk.Canvas(task_container)
    scrollbar = ttk.Scrollbar(task_container, orient="vertical", command=canvas.yview)
    
    # 创建任务框架（放在画布中）
    task_frame = ttk.Frame(canvas)
    
    # 配置画布
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas_window = canvas.create_window((0, 0), window=task_frame, anchor="nw")
    
    # 布局
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
    # 配置滚动和宽度
    def on_configure(event):
        # 更新画布滚动区域
        canvas.configure(scrollregion=canvas.bbox("all"))
        # 设置任务框架的宽度为画布宽度减去滚动条宽度
        canvas.itemconfig(canvas_window, width=canvas.winfo_width() - scrollbar.winfo_width())
    
    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    # 绑定事件
    task_frame.bind('<Configure>', on_configure)
    canvas.bind('<Configure>', on_configure)
    canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    # 保存到全局变量
    global_vars['experiment_module']['run_frame'] = task_frame
    
    # 创建控制按钮框架
    control_frame = ttk.Frame(main_frame)
    control_frame.pack(fill="x", pady=10)
    
    # 创建左侧按钮框架
    button_frame = ttk.Frame(control_frame)
    button_frame.pack(side="left")
    
    # 创建控制按钮
    btn_start = ttk.Button(button_frame, text="Start", width=6)
    btn_start.pack(side="left", padx=2)
    
    btn_pause = ttk.Button(button_frame, text="Pause", width=6)
    btn_pause.pack(side="left", padx=2)
    
    btn_stop = ttk.Button(button_frame, text="Stop", width=6)
    btn_stop.pack(side="left", padx=2)
    
    btn_remove = ttk.Button(button_frame, text="Remove", width=6)
    btn_remove.pack(side="left", padx=2)
    
    # 创建右侧设置框架
    settings_frame = ttk.Frame(control_frame)
    settings_frame.pack(side="right")
    
    # 添加并行进程数设置
    ttk.Label(settings_frame, text="Process:").pack(side="left", padx=2)
    process_var = tk.StringVar(value="1")
    process_entry = ttk.Entry(settings_frame, textvariable=process_var, width=4)
    process_entry.pack(side="left", padx=2)
    
    # 添加确认按钮
    btn_confirm = ttk.Button(settings_frame, text="Confirm", width=6)
    btn_confirm.pack(side="left", padx=2)
    
    # 保存变量到全局变量
    global_vars['experiment_module']['process_num'] = process_var

def create_result_display(frame):
    """创建结果输出部分"""
    # 创建标题
    label_title = ttk.Label(frame, text="Result Display", font=("Arial", 14, "bold"))
    label_title.pack(pady=10)



def create_experiment_module_view(frame_main):
    # 使用grid布局调整列比例为 1:1:2:1
    frame_main.grid_rowconfigure(0, weight=1)
    
    # 设置列的最小宽度
    MIN_WIDTH = 200  # 最小宽度
    
    # 第一列：Algorithm selection
    frame_main.grid_columnconfigure(0, weight=1, minsize=MIN_WIDTH)
    frame_left = create_column(frame_main, 0)
    frame_left.grid(sticky="nsew")
    create_algorithm_selection(frame_left)

    # 竖线分隔
    frame_main.grid_columnconfigure(1, weight=0, minsize=2)
    create_separator(frame_main, 1)

    # 第二列：Parameter setting
    frame_main.grid_columnconfigure(2, weight=1, minsize=MIN_WIDTH)
    frame_center_left = create_column(frame_main, 2)
    frame_center_left.grid(sticky="nsew")
    create_parameter_settings(frame_center_left)

    # 竖线分隔
    frame_main.grid_columnconfigure(3, weight=0, minsize=2)
    create_separator(frame_main, 3)

    # 第三列：Result display
    frame_main.grid_columnconfigure(4, weight=2, minsize=MIN_WIDTH*2)
    frame_center_right = create_column(frame_main, 4)
    frame_center_right.grid(sticky="nsew")
    create_run_management(frame_center_right)

    # 竖线分隔
    frame_main.grid_columnconfigure(5, weight=0, minsize=2)
    create_separator(frame_main, 5)

    # 第四列：Result selection
    frame_main.grid_columnconfigure(6, weight=1, minsize=MIN_WIDTH)
    frame_right = create_column(frame_main, 6)
    frame_right.grid(sticky="nsew")
    create_result_display(frame_right)
