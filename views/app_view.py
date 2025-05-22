import os
import tkinter as tk

import ttkbootstrap as ttk
from PIL import Image, ImageTk  # 导入Pillow库

from views.experiment_module.experiment_module_view import create_experiment_module_view
from views.resources.style import set_styles
from views.test_module.test_module_handler import clear_canvas
from views.test_module.test_module_view import create_test_module_view
from views.common.GlobalVar import global_vars

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
        ("Test Module", image_test_module, 'success.Outline.TButton'),  # 使用绿色样式
        ("Experiment Module", image_experiment_module, 'info.Outline.TButton'),  # 使用蓝色样式
    ]

    # 用按钮替代Radiobutton
    def on_button_click(module_name):
        """模拟点击模块按钮时的行为"""
        selected_module.set(module_name)  # 设置选中的模块

    for i, (text, image, button_style) in enumerate(module_buttons):
        button_widget = ttk.Button(
            buttons_frame,
            text=text,
            image=image,
            style=button_style,  # 根据模块类型设置样式
            compound="top",  # 控制文本和图像的位置，"top" 表示图像在文本上面
            command=lambda name=text: on_button_click(name),  # 点击按钮时设置模块
            padding=10,
            width=20
        )

        button_widget.image = image
        button_widget.pack(side=tk.LEFT, padx=10)

    # 加载学校图标
    school_img = Image.open("./views/resources/images/school.png")
    # 保持宽高比
    target_height = 60
    aspect_ratio = school_img.width / school_img.height
    target_width = int(target_height * aspect_ratio)
    school_img = school_img.resize((target_width, target_height), Image.Resampling.LANCZOS)  # 保持宽高比
    school_photo = ImageTk.PhotoImage(school_img)
    
    # 创建右侧学校图标标签
    school_label = ttk.Label(frame_top, image=school_photo, background='#F0F0F0')  # 设置背景色与顶部框架一致
    school_label.image = school_photo  # 保持引用
    school_label.pack(side=tk.RIGHT, padx=20)

def on_selected_module_change(var, frame_main):
    # 清空主界面控件和画布
    for widget in frame_main.winfo_children():
        widget.destroy()
    clear_canvas()

    # 切换到目标模块
    if var == "Test Module":
        create_test_module_view(frame_main)
    elif var == "Experiment Module":
        create_experiment_module_view(frame_main)

def create_menu_bar(root):
    """Create menu bar with dark theme."""
    menu_bar = tk.Menu(root, background='blue', fg='white')  # Dark background for menu bar

    # File menu
    file_menu = tk.Menu(menu_bar, tearoff=0)
    file_menu.add_command(label="New", command=lambda: print("New File"))
    file_menu.add_command(label="Open", command=lambda: print("Open File"))
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)
    menu_bar.add_cascade(label="File", menu=file_menu)

    # Edit menu
    edit_menu = tk.Menu(menu_bar, tearoff=0)
    edit_menu.add_command(label="Undo", command=lambda: print("Undo"))
    edit_menu.add_command(label="Redo", command=lambda: print("Redo"))
    menu_bar.add_cascade(label="Edit", menu=edit_menu)

    # Help menu
    help_menu = tk.Menu(menu_bar, tearoff=0)
    help_menu.add_command(label="About", command=lambda: print("FlexDMO"))
    menu_bar.add_cascade(label="Help", menu=help_menu)

    # Adding the menu bar to the root window
    root.config(menu=menu_bar)

def create_main_window():
    """创建主窗口"""
    root = tk.Tk()
    root.title("FlexDMO")
    root.geometry("1600x900")

    # 设置应用图标
    icon = Image.open("./views/resources/images/icon.png")
    icon = icon.resize((48, 48), Image.Resampling.LANCZOS)  # 使用高质量的LANCZOS重采样
    icon = ImageTk.PhotoImage(icon)
    root.iconphoto(True, icon)

    # 将root存入global_vars
    global_vars['root'] = root

    # 设置样式
    set_styles()

    # 创建菜单栏
    create_menu_bar(root)

    # 顶部的模块切换部分
    frame_top = ttk.Frame(root, style='CustomTop.TFrame')
    frame_top.pack(ipadx=10, ipady=10, fill=tk.X)

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
        clear_canvas()
        root.quit()
        root.destroy()

    # 注册关闭窗口的事件
    root.protocol("WM_DELETE_WINDOW", on_exit)
    # 启动 Tkinter 主循环
    root.mainloop()



