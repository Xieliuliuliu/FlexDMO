from tkinter import ttk


class CollapsibleFrame(ttk.Frame):
    """可折叠框架组件"""
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
        
        # 为了向后兼容，将expand_button也作为title_label
        self.title_label = self.expand_button
        
        # 内容框架
        self.content_frame = ttk.Frame(self)
        self.content_frame.pack(fill="x", expand=True)
        
        # 绑定点击事件
        self.expand_button.bind("<Button-1>", self.toggle)
        self.title_frame.bind("<Button-1>", self.toggle)
        
        # 初始状态为展开
        self.is_expanded = True
        
    def toggle(self, event=None):
        """切换展开/收起状态"""
        if self.is_expanded:
            self.content_frame.pack_forget()
            self.expand_button.config(text=f"▲ {self._title}")
        else:
            self.content_frame.pack(fill="x", expand=True)
            self.expand_button.config(text=f"▼ {self._title}")
        self.is_expanded = not self.is_expanded
        
    def set_title(self, new_title):
        """设置新的标题"""
        self._title = new_title
        arrow = "▲" if not self.is_expanded else "▼"
        self.expand_button.config(text=f"{arrow} {new_title}")
        
    def get_content_frame(self):
        """获取内容框架"""
        return self.content_frame
