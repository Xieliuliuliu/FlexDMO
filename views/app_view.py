import tkinter as tk
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk
from PIL import Image, ImageTk  # 导入Pillow库

from views.experiment_module.experiment_module_view import create_experiment_module_view
from views.resources.style import set_styles
from views.test_module.test_module_handler import clear_canvas
from utils.run_executor import delete_state_in_test_mode
from views.test_module.test_module_view import create_test_module_view
from views.common.GlobalVar import global_vars
from utils.ui_dispatch import start_ui_dispatch, stop_ui_dispatch

def create_module_switch(frame_top, selected_module):
    """创建模块切换区域"""
    selected_module.set("Test Module")  # 默认选中第一个模块

    # 加载图像并缩放
    def load_and_resize_image(image_path, size=(30, 30)):
        img = Image.open(image_path)  # 使用Pillow加载图像
        img = img.resize(size)  # 缩放图像
        return ImageTk.PhotoImage(img)  # 转换为Tkinter兼容的格式

    # 加载并缩小图像
    image_test_module = load_and_resize_image("./views/resources/images/test_module_icon.png")
    image_experiment_module = load_and_resize_image("./views/resources/images/experiment_module_icon.png")

    # 创建左侧按钮容器
    buttons_frame = ttk.Frame(frame_top, style='CustomTop.TFrame')
    buttons_frame.pack(side=tk.LEFT, fill=tk.Y)

    module_buttons = [
        ("Test Module", "测试运行", image_test_module, 'success.Outline.TButton'),
        ("Experiment Module", "批量实验", image_experiment_module, 'info.Outline.TButton'),
    ]

    # 用按钮替代Radiobutton
    def on_button_click(module_name):
        """模拟点击模块按钮时的行为"""
        selected_module.set(module_name)  # 设置选中的模块

    for i, (module_name, text, image, button_style) in enumerate(module_buttons):
        button_widget = ttk.Button(
            buttons_frame,
            text=text,
            image=image,
            style=button_style,  # 根据模块类型设置样式
            compound="left",
            command=lambda name=module_name: on_button_click(name),
            padding=6,
            width=12
        )

        button_widget.image = image
        button_widget.pack(side=tk.LEFT, padx=10)

    # 加载学校图标
    school_img = Image.open("./views/resources/images/school.png")
    # 保持宽高比
    target_height = 32
    aspect_ratio = school_img.width / school_img.height
    target_width = int(target_height * aspect_ratio)
    school_img = school_img.resize((target_width, target_height), Image.Resampling.LANCZOS)  # 保持宽高比
    school_photo = ImageTk.PhotoImage(school_img)
    
    # 创建右侧学校图标标签
    school_label = ttk.Label(frame_top, image=school_photo, background='#F0F0F0')  # 设置背景色与顶部框架一致
    school_label.image = school_photo  # 保持引用
    school_label.pack(side=tk.RIGHT, padx=20)

    def fit_header(event):
        if event.widget is frame_top:
            if event.width < 900:
                school_label.pack_forget()
            elif not school_label.winfo_manager():
                school_label.pack(side=tk.RIGHT, padx=20)

    frame_top.bind('<Configure>', fit_header, add='+')

def on_selected_module_change(var, frame_main):
    # Keep parameter edits, replay data and running task cards across navigation.
    frames = getattr(frame_main, '_module_frames', None)
    if frames is None:
        frames = frame_main._module_frames = {}
    for frame in frames.values():
        frame.pack_forget()
    if var not in frames:
        frame = ttk.Frame(frame_main)
        frames[var] = frame
        if var == "Test Module":
            create_test_module_view(frame)
        elif var == "Experiment Module":
            create_experiment_module_view(frame)
    frames[var].pack(fill=tk.BOTH, expand=True)

def create_menu_bar(root):
    """Create menu bar with dark theme."""
    menu_bar = tk.Menu(root, background='blue', fg='white')  # Dark background for menu bar

    def open_result():
        from utils.test_runtime import test_run_active
        if test_run_active():
            messagebox.showinfo("暂时无法加载", "请先终止运行或等待完成，再打开历史结果。")
            return
        file_path = filedialog.askopenfilename(
            title="打开 FlexDMO 结果",
            initialdir="results",
            filetypes=[("FlexDMO JSON result", "*.json")],
        )
        if not file_path:
            return
        global_vars['test_module']['selected_module'].set('Test Module')
        from views.test_module.test_module_handler import (
            load_selected_result,
            update_progress_control,
        )

        result = load_selected_result(file_path)
        if result is None:
            messagebox.showerror("FlexDMO", "结果文件无法加载，请检查文件格式和问题组件。")
            return
        scale = global_vars["test_module"].get("scale")
        current_label = global_vars["test_module"].get("current_label")
        total_label = global_vars["test_module"].get("total_label")
        if scale and current_label and total_label:
            update_progress_control(scale, current_label, total_label)
            workspace = global_vars['test_module'].get('workspace')
            if workspace is not None:
                workspace.show_panel(2)
        messagebox.showinfo("FlexDMO", "结果已加载，可拖动回放时间轴查看历史快照。")

    file_menu = tk.Menu(menu_bar, tearoff=0)
    file_menu.add_command(label="打开结果…", command=open_result)
    file_menu.add_separator()
    file_menu.add_command(label="退出", command=lambda: root.event_generate("<<CloseApp>>"))
    menu_bar.add_cascade(label="文件", menu=file_menu)

    help_menu = tk.Menu(menu_bar, tearoff=0)
    help_menu.add_command(
        label="关于",
        command=lambda: messagebox.showinfo(
            "关于 FlexDMO",
            "FlexDMO\n动态多目标优化实验平台",
        ),
    )
    menu_bar.add_cascade(label="帮助", menu=help_menu)

    # Adding the menu bar to the root window
    root.config(menu=menu_bar)

def create_main_window():
    """创建主窗口"""
    root = tk.Tk()
    root.title("FlexDMO")
    width = min(1600, max(640, root.winfo_screenwidth() - 80))
    height = min(900, max(480, root.winfo_screenheight() - 120))
    root.geometry(f"{width}x{height}")
    root.minsize(640, 480)

    # 设置应用图标
    icon = Image.open("./views/resources/images/icon.png")
    icon = icon.resize((48, 48), Image.Resampling.LANCZOS)  # 使用高质量的LANCZOS重采样
    icon = ImageTk.PhotoImage(icon)
    root.iconphoto(True, icon)

    # 将root存入global_vars
    global_vars['root'] = root
    start_ui_dispatch(root)

    # 设置样式
    set_styles()

    # 创建菜单栏
    create_menu_bar(root)

    # 顶部的模块切换部分
    frame_top = ttk.Frame(root, style='CustomTop.TFrame')
    frame_top.pack(pady=4, fill=tk.X)

    # 添加横向分隔线
    separator = ttk.Separator(root, orient="horizontal")  # 创建水平分隔符
    separator.pack(fill=tk.X)  # 设置分隔符的填充和垂直间距

    # 创建主体区域
    frame_main = tk.Frame(root)
    frame_main.pack(pady=10, fill=tk.BOTH, expand=True)

    selected_module = tk.StringVar()
    global_vars['test_module']['selected_module'] = selected_module

    # 绑定 selected_module 变量的变化事件
    selected_module.trace_add("write", lambda *args: on_selected_module_change(selected_module.get(), frame_main))
    create_module_switch(frame_top, selected_module)

    def on_exit():
        delete_state_in_test_mode()
        stop_ui_dispatch()
        clear_canvas()
        root.quit()
        root.destroy()

    # 注册关闭窗口的事件
    root.protocol("WM_DELETE_WINDOW", on_exit)
    root.bind("<<CloseApp>>", lambda _event: on_exit())
    # 启动 Tkinter 主循环
    root.mainloop()
