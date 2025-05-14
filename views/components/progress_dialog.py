import tkinter as tk
from tkinter import ttk
from views.common.GlobalVar import global_vars

class ProgressDialog:
    """进度条对话框组件"""
    
    def __init__(self, title="Progress", width=400, height=150):
        """初始化进度条对话框
        
        Args:
            title: 窗口标题
            width: 窗口宽度
            height: 窗口高度
        """
        # 从global_vars获取root窗口
        self.root = global_vars.get('root')
        if not self.root:
            raise ValueError("Root window not found in global_vars")
            
        self.window = tk.Toplevel(self.root)
        self.window.title(title)
        self.window.geometry(f"{width}x{height}")
        self.window.transient(self.root)  # 设置为主窗口的子窗口
        self.window.grab_set()  # 模态窗口
        
        # 创建主框架
        self.frame = ttk.Frame(self.window, padding="20")
        self.frame.pack(fill="both", expand=True)
        
        # 创建标题标签
        self.title_label = ttk.Label(self.frame, text="Loading...")
        self.title_label.pack(pady=(0, 10))
        
        # 创建进度条
        self.progress_bar = ttk.Progressbar(self.frame, 
                                          orient="horizontal", 
                                          length=360, 
                                          mode="determinate")
        self.progress_bar.pack(pady=10)
        
        # 创建状态标签
        self.status_label = ttk.Label(self.frame, text="0%")
        self.status_label.pack(pady=5)
        
    def update_progress(self, value, status_text=None):
        """更新进度条和状态
        
        Args:
            value: 进度值（0-100）
            status_text: 状态文本，如果为None则显示百分比
        """
        self.progress_bar["value"] = value
        if status_text is None:
            status_text = f"{int(value)}%"
        self.status_label.config(text=status_text)
        self.window.update()
        
    def update_status(self, text):
        """更新状态文本
        
        Args:
            text: 状态文本
        """
        self.status_label.config(text=text)
        self.window.update()
        
    def set_title(self, text):
        """设置标题文本
        
        Args:
            text: 标题文本
        """
        self.title_label.config(text=text)
        self.window.update()
        
    def close(self):
        """关闭进度条窗口"""
        self.window.destroy() 