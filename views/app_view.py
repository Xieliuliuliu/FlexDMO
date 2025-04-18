import os
import tkinter as tk

import ttkbootstrap as ttk
from PIL import Image, ImageTk  # 导入Pillow库
from Tools.scripts import objgraph

from views.resources.style import set_styles
from views.test_module.test_module_handler import clear_canvas
from views.test_module.test_module_view import create_test_module_view
from views.common.GlobalVar import global_vars

import gc
import tracemalloc
import objgraph  # 如果没安装，可以注释掉这部分

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
            frame_top,
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


tracemalloc.start()

def on_selected_module_change(var, frame_main):
    print("\n========== 模块切换开始 ==========\n")

    # --- 垃圾回收前清理 ---
    print("[GC] 清理前可达对象数量：", len(gc.get_objects()))
    gc.collect()
    print("[GC] 清理后可达对象数量：", len(gc.get_objects()))

    # --- 内存快照前 ---
    snapshot1 = tracemalloc.take_snapshot()

    # --- 清空主界面控件和画布 ---
    for widget in frame_main.winfo_children():
        widget.destroy()
    clear_canvas()

    # --- 切换到目标模块 ---
    if var == "Test Module":
        create_test_module_view(frame_main)

    # --- 内存快照后 ---
    snapshot2 = tracemalloc.take_snapshot()
    top_stats = snapshot2.compare_to(snapshot1, 'lineno')

    print("\n[🔍 内存变化最多的前10处代码行]")
    for stat in top_stats[:10]:
        print(stat)

    # --- 内存中对象类型统计 ---
    print("\n[📦 当前最多的对象类型]")
    objgraph.show_most_common_types(limit=10)

    # --- 可视化 Frame 的引用链（可改为你关注的类） ---
    try:
        frame_objs = objgraph.by_type('Frame')
        if frame_objs:
            tmp_dir = os.path.expanduser("~\\AppData\\Local\\Temp")
            filename = os.path.join(tmp_dir, 'frame_leak_backref.png')
            objgraph.show_backrefs(
                frame_objs[0],
                max_depth=3,
                filename=filename
            )
            print(f"[🖼️ objgraph] 已保存 Frame 的引用链图像到 {filename}")
    except Exception as e:
        print("[objgraph] 引用图生成失败：", e)

    print("\n========== 模块切换分析完成 ==========\n")

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
    help_menu.add_command(label="About", command=lambda: print("About PlatformDMOEAS"))
    menu_bar.add_cascade(label="Help", menu=help_menu)

    # Adding the menu bar to the root window
    root.config(menu=menu_bar)



def create_main_window():
    """创建主窗口"""
    root = tk.Tk()
    root.title("PlatformEDMO")
    root.geometry("1600x900")

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



