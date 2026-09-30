import tkinter as tk
from tkinter import ttk, filedialog
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from views.components.scrolled_frame import NativeScrolledFrame as ScrolledFrame
from functools import partial
import os

from views.common.GlobalVar import global_vars
from views.common.common_components import create_column, create_separator
from views.common.responsive_workspace import ResponsiveWorkspace, scrollable_content
from views.components.collapsible_frame import CollapsibleFrame
from views.experiment_module.experiment_module_handler import (
    on_add_button_click, on_dynamic_select, on_search_select, on_problem_select,
    update_all_configs, on_remove_button_click, on_start_button_click, on_pause_button_click
)
from views.test_module.test_module_handler import load_dynamic_data, load_problem_data, load_search_data
from views.components.results_form import ResultsForm

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
    return tv_problem

def create_algorithm_selection(frame):
    """创建完整的算法选择区域"""
    # 创建主框架并限制宽度
    main_frame = ttk.Frame(frame)
    main_frame.pack(fill="both", expand=True)
    
    # 创建标题
    label_algo = ttk.Label(main_frame, text="算法与问题", font=("Arial", 12, "bold"))
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
    label_title = ttk.Label(frame, text="实验参数", font=("Arial", 12, "bold"))
    label_title.pack(pady=10)

    # 创建主框架来包含画布和底部栏
    main_frame = ttk.Frame(frame)
    main_frame.pack(fill="both", expand=True, padx=10)

    # 创建参数框架（带滚动条）
    parameter_frame = ttk.LabelFrame(main_frame, text="算法参数", padding=5)
    parameter_frame.pack(side="top", fill="both", expand=True)

    # 创建滚动框架
    scroll_frame = ScrolledFrame(parameter_frame, autohide=True)
    scroll_frame.pack(fill="both", expand=True)

    # 创建内容框架
    content_frame = ttk.Frame(scroll_frame)
    content_frame.pack(fill="both", expand=True)

    # 创建底部带边框的栏
    bottom_frame = ttk.LabelFrame(main_frame, text="批量设置", padding=5)
    bottom_frame.pack(side="top", fill="x", pady=5)

    # 创建输入框架
    input_frame = ttk.Frame(bottom_frame)
    input_frame.pack(fill="x", pady=5)

    # 添加 tau 输入
    ttk.Label(input_frame, text="变化间隔（代）：").grid(row=0, column=0, sticky='w', pady=2)
    tau_var = tk.StringVar(value="10,20")
    tau_entry = ttk.Entry(input_frame, textvariable=tau_var, width=5)
    tau_entry.grid(row=0, column=1, sticky='ew', pady=2)

    # 添加 n 输入
    ttk.Label(input_frame, text="环境变化强度：").grid(row=1, column=0, sticky='w', pady=2)
    n_var = tk.StringVar(value="5,10")
    n_entry = ttk.Entry(input_frame, textvariable=n_var, width=5)
    n_entry.grid(row=1, column=1, sticky='ew', pady=2)

    # 添加运行次数输入
    ttk.Label(input_frame, text="重复运行次数：").grid(row=2, column=0, sticky='w', pady=2)
    runs_var = tk.StringVar(value="1")
    runs_entry = ttk.Entry(input_frame, textvariable=runs_var, width=5)
    runs_entry.grid(row=2, column=1, sticky='ew', pady=2)
    input_frame.columnconfigure(1, weight=1)

    # 添加按钮
    add_button = ttk.Button(input_frame, text="添加任务", width=7)
    add_button.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(4, 0))
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
        current_path = os.path.join(os.getcwd(), "results", "experiment_module")
    
    # 打开文件夹选择对话框
    save_path = filedialog.askdirectory(
        title="Select Save Path",
        initialdir=current_path
    )
    
    # 如果用户选择了路径，则更新
    if save_path:
        global_vars['experiment_module']['save_path'].set(os.path.normpath(save_path))


def create_run_management(frame):
    """创建运行管理部分"""
    # 创建标题
    label_title = ttk.Label(frame, text="任务进度", font=("Arial", 12, "bold"))
    label_title.pack(pady=10)
    
    # 创建主框架
    main_frame = ttk.Frame(frame)
    main_frame.pack(fill="both", expand=True, padx=10)
    
    # 创建任务列表框架（带滚动条和边框）
    task_container = ttk.LabelFrame(main_frame, text="实验任务", padding=5)
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
    control_frame = ttk.LabelFrame(main_frame, text="运行控制", padding=5)
    control_frame.pack(fill="x", pady=5)
    
    # 创建第一行框架（控制按钮）
    button_frame = ttk.Frame(control_frame)
    button_frame.pack(fill="x", pady=(0, 5))
    
    # 创建控制按钮
    btn_start = ttk.Button(button_frame, text="开始", width=7)
    btn_start.pack(side="left", padx=2)
    btn_start.bind("<Button-1>", on_start_button_click)
    
    btn_pause = ttk.Button(button_frame, text="暂停", width=7)
    btn_pause.pack(side="left", padx=2)
    btn_pause.bind("<Button-1>", on_pause_button_click)
    
    btn_remove = ttk.Button(button_frame, text="移除", width=7)
    btn_remove.pack(side="left", padx=2)
    btn_remove.bind("<Button-1>", on_remove_button_click)
    
    # 创建右侧设置框架
    settings_frame = ttk.Frame(button_frame)
    settings_frame.pack(side="right")
    
    # 添加并行进程数设置
    ttk.Label(settings_frame, text="并行数：").pack(side="left", padx=2)
    process_var = tk.StringVar(value="1")
    process_entry = ttk.Entry(settings_frame, textvariable=process_var, width=4)
    process_entry.pack(side="left", padx=2)
    
   
    # 创建第二行框架（保存路径）
    save_path_frame = ttk.Frame(control_frame)
    save_path_frame.pack(fill="x")
    
    # 添加保存路径设置
    ttk.Label(save_path_frame, text="保存路径：").pack(side="left", padx=2)
    save_path_var = tk.StringVar(value=os.path.join(os.getcwd(), "results", "experiment_module"))
    save_path_entry = ttk.Entry(save_path_frame, textvariable=save_path_var)
    save_path_entry.pack(side="left", fill="x", expand=True, padx=2)
    save_path_entry.bind("<Button-1>", select_save_path)  # 点击输入框时打开选择对话框
    
    # 添加选择按钮
    btn_browse = ttk.Button(save_path_frame, text="选择", width=7, command=select_save_path)
    btn_browse.pack(side="left", padx=2)
    
    # 保存变量到全局变量
    global_vars['experiment_module']['process_num'] = process_var
    global_vars['experiment_module']['save_path'] = save_path_var

def create_result_display(frame):
    """创建结果输出部分"""
    # 创建标题
    label_title = ttk.Label(frame, text="结果分析", font=("Arial", 12, "bold"))
    label_title.pack(pady=10)
    
    # 创建主框架
    main_frame = ttk.Frame(frame)
    main_frame.pack(fill="both", expand=True, padx=10)
    
    # 创建结果表单
    results_form = ResultsForm(main_frame)
    results_form.pack(fill="both", expand=True)
    
    # 保存到全局变量
    global_vars['experiment_module']['results_form'] = results_form

def create_experiment_module_view(frame_main):
    workspace = ResponsiveWorkspace(frame_main, ("算法与问题", "实验参数", "任务进度", "结果分析"))
    global_vars['experiment_module']['workspace'] = workspace
    create_algorithm_selection(scrollable_content(workspace.panels[0]))
    create_parameter_settings(workspace.panels[1])
    create_run_management(workspace.panels[2])
    create_result_display(workspace.panels[3])

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
