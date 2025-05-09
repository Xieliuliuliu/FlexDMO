import tkinter as tk
from tkinter import ttk

class TaskProgress(ttk.Frame):
    """任务进度条组件"""
    
    def __init__(self, parent, problem, dynamic, search, tau, n, run, runs, problem_config=None, dynamic_config=None, search_config=None):
        """初始化任务进度条组件
        
        Args:
            parent: 父容器
            problem: 问题名称
            dynamic: 动态策略
            search: 搜索算法
            tau: tau值
            n: n值
            run: 当前运行次数
            runs: 总运行次数
            problem_config: 问题配置
            dynamic_config: 动态策略配置
            search_config: 搜索算法配置
        """
        super().__init__(parent)
        self.problem = problem
        self.dynamic = dynamic
        self.search = search
        self.tau = tau
        self.n = n
        self.run = run
        self.runs = runs
        self.problem_config = problem_config or {}
        self.dynamic_config = dynamic_config or {}
        self.search_config = search_config or {}
        
        # 创建状态变量
        self.status_var = tk.StringVar(value="waiting")
        
        # 创建主框架（带边框）
        self.frame = ttk.Frame(parent)
        self.frame.pack(fill="x", expand=True, padx=5, pady=2)
        
        # 设置主框架样式
        self.frame.configure(relief="solid", borderwidth=1)
        
        # 创建第一行框架（任务信息）
        self.info_frame = ttk.Frame(self.frame)
        self.info_frame.pack(fill="x", expand=True, padx=10, pady=5)
        
        # 创建任务信息标签
        task_info = f"{problem} : {dynamic}-{search} (tau={tau}, n={n}, run={run}/{runs})"
        self.task_label = ttk.Label(self.info_frame, text=task_info)
        self.task_label.pack(side="left", padx=5)
        
        # 创建第二行框架（进度条和状态）
        self.progress_frame = ttk.Frame(self.frame)
        self.progress_frame.pack(fill="x", expand=True, padx=10, pady=5)
        
        # 创建进度条容器框架
        self.progress_container = ttk.Frame(self.progress_frame)
        self.progress_container.pack(side="left", fill="x", expand=True, padx=5)
        
        # 创建进度条
        self.progress = ttk.Progressbar(self.progress_container, mode='determinate')
        self.progress.pack(fill="x", expand=True)
        
        # 创建状态标签
        self.status_label = ttk.Label(self.progress_frame, textvariable=self.status_var)
        self.status_label.pack(side="left", padx=5)
        


        self.process = None
        self.process_state = None

    
    def update_progress(self, value):
        """更新进度条值
        
        Args:
            value: 进度值（0-100）
        """
        self.progress['value'] = value
    
    def update_status(self, status):
        """更新状态文本
        
        Args:
            status: 状态文本
        """
        self.status_var.set(status)
    
    def destroy(self):            
        """销毁任务卡片，清理所有资源"""
        # 清理进程
        if hasattr(self, 'process') and self.process:
            try:
                self.process.terminate()
                self.process.join(timeout=1)
                if self.process.is_alive():
                    self.process.kill()
            except:
                pass
            self.process = None
            
        # 清理Manager
        if hasattr(self, 'manager'):
            try:
                self.manager.shutdown()
            except:
                pass
            self.manager = None
            
        # 清理状态
        if hasattr(self, 'process_state'):
            self.process_state = None
            
        # 清理回调函数
        if hasattr(self, 'on_complete'):
            self.on_complete = None
            
        # 销毁所有子组件
        for widget in self.winfo_children():
            try:
                widget.destroy()
            except:
                pass
                
        # 销毁主框架
        if hasattr(self, 'frame'):
            try:
                self.frame.destroy()
            except:
                pass
                
        # 销毁界面
        super().destroy()
    
    def get_info(self):
        """获取任务信息"""
        return {
            'problem': self.problem,
            'dynamic': self.dynamic,
            'search': self.search,
            'tau': self.tau,
            'n': self.n,
            'run': self.run,
            'total_runs': self.runs,
            'status': self.status_var.get().lower(),  # 获取状态变量的值并转换为小写
            'problem_config': self.problem_config,
            'dynamic_config': self.dynamic_config,
            'search_config': self.search_config
        } 