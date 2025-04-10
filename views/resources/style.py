import ttkbootstrap as ttk

def set_styles():
    """设置 Tkinter 样式"""
    # 获取 Style 对象
    style = ttk.Style()

    # 设置 ttk.Frame 背景颜色
    style.configure('CustomTop.TFrame', background='#F0F0F0')
    # 设置第二个 frame 的样式
    style.configure('CustomSep.TFrame', background='#b0b0b0')
