from tkinter import ttk
import tkinter as tk

class CollapsibleListbox(ttk.Frame):
    """可折叠的Listbox组件"""
    def __init__(self, parent, title, style='success', *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # 保存原始标题
        self._title = title
        
        # 创建标题栏
        self.title_frame = ttk.Frame(self)
        self.title_frame.pack(fill="x", pady=(0, 5))
        
        # 展开/收起按钮（包含标题）
        self.expand_button = ttk.Label(self.title_frame, text=f"▼ {title}", font=("Arial", 12, "bold"), style=f'inverse-{style}', cursor="hand2")
        self.expand_button.pack(fill="x", expand=True)
        
        # 创建Listbox（使用Toplevel作为父窗口）
        self.listbox_window = tk.Toplevel(self)
        self.listbox_window.overrideredirect(True)  # 无边框
        self.listbox_window.attributes('-topmost', True)  # 保持在最上层
        self.listbox = tk.Listbox(self.listbox_window, selectmode=tk.MULTIPLE, height=3, exportselection=False)  # 禁用导出选择
        self.listbox.pack(fill="both", expand=True)
        
        # 绑定点击事件
        self.expand_button.bind("<Button-1>", self.toggle)
        self.title_frame.bind("<Button-1>", self.toggle)
        
        # 绑定鼠标事件
        self.listbox.bind("<Enter>", self.show_listbox)
        self.listbox.bind("<Leave>", self.hide_listbox)
        
        # 初始状态为隐藏
        self.is_expanded = False
        self.listbox_window.withdraw()  # 初始隐藏窗口
        
    def toggle(self, event=None):
        """切换展开/收起状态"""
        if self.is_expanded:
            self.hide_listbox()
        else:
            self.show_listbox()
        
    def show_listbox(self, event=None):
        """显示Listbox"""
        if not self.is_expanded:
            # 获取标题栏的位置和大小
            x = self.title_frame.winfo_rootx()
            y = self.title_frame.winfo_rooty() + self.title_frame.winfo_height()
            width = self.title_frame.winfo_width()
            
            # 设置Listbox窗口的位置和大小
            self.listbox_window.geometry(f"{width}x{self.listbox.winfo_reqheight()}")
            self.listbox_window.deiconify()  # 显示窗口
            self.listbox_window.geometry(f"+{x}+{y}")
            
            self.expand_button.config(text=f"▼ {self._title}")
            self.is_expanded = True
        
    def hide_listbox(self, event=None):
        """隐藏Listbox"""
        if self.is_expanded:
            self.listbox_window.withdraw()  # 隐藏窗口
            self.expand_button.config(text=f"▲ {self._title}")
            self.is_expanded = False
        
    def set_title(self, new_title):
        """设置新的标题"""
        self._title = new_title
        arrow = "▲" if not self.is_expanded else "▼"
        self.expand_button.config(text=f"{arrow} {new_title}")
        
    def insert(self, index, *elements):
        """向Listbox插入元素"""
        self.listbox.insert(index, *elements)
        
    def delete(self, first, last=None):
        """从Listbox删除元素"""
        self.listbox.delete(first, last)
        
    def get(self, first, last=None):
        """获取Listbox中的元素"""
        return self.listbox.get(first, last)
        
    def curselection(self):
        """获取当前选中的项"""
        return self.listbox.curselection()
        
    def bind(self, sequence=None, func=None, add=None):
        """绑定事件"""
        self.listbox.bind(sequence, func, add) 