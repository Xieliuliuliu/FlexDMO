import tkinter as tk
from tkinter import ttk, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
from functools import partial
import os

from views.common.GlobalVar import global_vars
from views.common.common_components import create_column, create_separator
from views.components.collapsible_frame import CollapsibleFrame
from views.experiment_module.experiment_module_handler import (
    on_add_button_click, on_dynamic_select, on_search_select, on_problem_select,
    update_all_configs, on_remove_button_click, on_start_button_click, on_pause_button_click
)
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

    # 创建参数框架（带滚动条）
    parameter_frame = ttk.LabelFrame(main_frame, text="parameters", padding=5)
    parameter_frame.pack(side="top", fill="both", expand=True)

    # 创建滚动框架
    scroll_frame = ScrolledFrame(parameter_frame, autohide=True)
    scroll_frame.pack(fill="both", expand=True)

    # 创建内容框架
    content_frame = ttk.Frame(scroll_frame)
    content_frame.pack(fill="both", expand=True)

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
    add_button = ttk.Button(input_frame, text="Add", width=7)
    add_button.pack(side="left", padx=2)
    add_button.bind("<Button-1>", on_add_button_click)

    # 保存变量到全局变量
    global_vars['experiment_module']['tau'] = tau_var
    global_vars['experiment_module']['n'] = n_var
    global_vars['experiment_module']['runs'] = runs_var
    global_vars['experiment_module']['parameter_frame'] = content_frame

def select_save_path(event=None):
    """选择保存路径"""
    # 获取当前保存路径
    current_path = global_vars['experiment_module']['save_path'].get()
    if not os.path.exists(current_path):
        current_path = os.path.join(os.getcwd(), "results").replace("/", "\\")
    
    # 打开文件夹选择对话框
    save_path = filedialog.askdirectory(
        title="Select Save Path",
        initialdir=current_path
    )
    
    # 如果用户选择了路径，则更新
    if save_path:
        global_vars['experiment_module']['save_path'].set(save_path.replace("/", "\\"))
    else:
        # 如果用户取消选择，则设置为项目根目录下的results
        default_path = os.path.join(os.getcwd(), "results").replace("/", "\\")
        global_vars['experiment_module']['save_path'].set(default_path)

def create_run_management(frame):
    """创建运行管理部分"""
    # 创建标题
    label_title = ttk.Label(frame, text="Run Management", font=("Arial", 14, "bold"))
    label_title.pack(pady=10)
    
    # 创建主框架
    main_frame = ttk.Frame(frame)
    main_frame.pack(fill="both", expand=True, padx=10)
    
    # 创建任务列表框架（带滚动条和边框）
    task_container = ttk.LabelFrame(main_frame, text="Tasks", padding=5)
    task_container.pack(fill="both", expand=True)
    
    # 创建滚动框架
    scroll_frame = ScrolledFrame(task_container, autohide=True)
    scroll_frame.pack(fill="both", expand=True)
    
    # 创建任务框架
    task_frame = ttk.Frame(scroll_frame)
    task_frame.pack(fill="both", expand=True)
    
    # 保存到全局变量
    global_vars['experiment_module']['run_frame'] = task_frame
    
    # 创建控制按钮框架
    control_frame = ttk.LabelFrame(main_frame, text="Control", padding=5)
    control_frame.pack(fill="x", pady=5)
    
    # 创建第一行框架（控制按钮）
    button_frame = ttk.Frame(control_frame)
    button_frame.pack(fill="x", pady=(0, 5))
    
    # 创建控制按钮
    btn_start = ttk.Button(button_frame, text="Start", width=7)
    btn_start.pack(side="left", padx=2)
    btn_start.bind("<Button-1>", on_start_button_click)
    
    btn_pause = ttk.Button(button_frame, text="Pause", width=7)
    btn_pause.pack(side="left", padx=2)
    btn_pause.bind("<Button-1>", on_pause_button_click)
    
    btn_remove = ttk.Button(button_frame, text="Remove", width=7)
    btn_remove.pack(side="left", padx=2)
    btn_remove.bind("<Button-1>", on_remove_button_click)
    
    # 创建右侧设置框架
    settings_frame = ttk.Frame(button_frame)
    settings_frame.pack(side="right")
    
    # 添加并行进程数设置
    ttk.Label(settings_frame, text="Process:").pack(side="left", padx=2)
    process_var = tk.StringVar(value="1")
    process_entry = ttk.Entry(settings_frame, textvariable=process_var, width=4)
    process_entry.pack(side="left", padx=2)
    
   
    # 创建第二行框架（保存路径）
    save_path_frame = ttk.Frame(control_frame)
    save_path_frame.pack(fill="x")
    
    # 添加保存路径设置
    ttk.Label(save_path_frame, text="Save Path:").pack(side="left", padx=2)
    save_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "results").replace("/", "\\"))
    save_path_entry = ttk.Entry(save_path_frame, textvariable=save_path_var)
    save_path_entry.pack(side="left", fill="x", expand=True, padx=2)
    save_path_entry.bind("<Button-1>", select_save_path)  # 点击输入框时打开选择对话框
    
    # 添加选择按钮
    btn_browse = ttk.Button(save_path_frame, text="Browse", width=7, command=select_save_path)
    btn_browse.pack(side="left", padx=2)
    
    # 保存变量到全局变量
    global_vars['experiment_module']['process_num'] = process_var
    global_vars['experiment_module']['save_path'] = save_path_var

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

def create_experiment_module(root):
    """创建实验模块"""
    # 创建主框架
    main_frame = ttk.Frame(root)
    main_frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    # 创建标题标签
    label_title = ttk.Label(main_frame, text="实验模块", font=("Arial", 16, "bold"))
    label_title.pack(pady=(0, 10))
    
    # 创建滚动框架
    scroll_frame = ScrolledFrame(main_frame, autohide=True)
    scroll_frame.pack(fill="both", expand=True)
    
    # 创建内容框架
    content_frame = ttk.Frame(scroll_frame)
    content_frame.pack(fill="both", expand=True)
    
    # 创建左侧框架（动态策略和搜索算法）
    left_frame = ttk.Frame(content_frame)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
    
    # 创建右侧框架（问题和参数）
    right_frame = ttk.Frame(content_frame)
    right_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))
    
    # 创建动态策略框架
    dynamic_frame = ttk.LabelFrame(left_frame, text="动态策略")
    dynamic_frame.pack(fill="both", expand=True, pady=(0, 5))
    
    # 创建动态策略树形视图
    tv_dynamic = ttk.Treeview(dynamic_frame, show="tree", selectmode="extended")
    tv_dynamic.pack(fill="both", expand=True, padx=5, pady=5)
    
    # 创建搜索算法框架
    search_frame = ttk.LabelFrame(left_frame, text="搜索算法")
    search_frame.pack(fill="both", expand=True, pady=(5, 0))
    
    # 创建搜索算法树形视图
    tv_search = ttk.Treeview(search_frame, show="tree", selectmode="extended")
    tv_search.pack(fill="both", expand=True, padx=5, pady=5)
    
    # 创建问题框架
    problem_frame = ttk.LabelFrame(right_frame, text="问题")
    problem_frame.pack(fill="both", expand=True, pady=(0, 5))
    
    # 创建问题树形视图
    tv_problem = ttk.Treeview(problem_frame, show="tree", selectmode="extended")
    tv_problem.pack(fill="both", expand=True, padx=5, pady=5)
    
    # 创建参数框架
    parameter_frame = ttk.LabelFrame(right_frame, text="参数")
    parameter_frame.pack(fill="both", expand=True, pady=(5, 0))
    
    # 创建运行管理框架
    run_frame = ttk.LabelFrame(right_frame, text="运行管理")
    run_frame.pack(fill="both", expand=True, pady=(5, 0))
    
    # 创建添加按钮
    add_button = ttk.Button(run_frame, text="添加", command=on_add_button_click)
    add_button.pack(pady=5)
    
    # 绑定选择事件
    tv_dynamic.bind('<<TreeviewSelect>>', lambda e: on_dynamic_select(tv_dynamic))
    tv_search.bind('<<TreeviewSelect>>', lambda e: on_search_select(tv_search))
    tv_problem.bind('<<TreeviewSelect>>', lambda e: on_problem_select(tv_problem))
    
    # 保存引用到全局变量
    global_vars['experiment_module'] = {
        'tv_dynamic': tv_dynamic,
        'tv_search': tv_search,
        'tv_problem': tv_problem,
        'parameter_frame': parameter_frame,
        'run_frame': run_frame,
        'selected_dynamic': [],
        'selected_search': [],
        'selected_problem': [],
        'runtime_config': {}
    }
    
    return main_frame
