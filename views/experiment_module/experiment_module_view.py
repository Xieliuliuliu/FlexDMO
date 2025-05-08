
import tkinter as tk

def create_experiment_module_view(frame_main):
    # 使用grid布局调整列比例为 1:1:2:1
    frame_main.grid_rowconfigure(0, weight=1)
    # 创造一个label显示实验模块
    label = tk.Label(frame_main, text="Experiment Module", font=("Arial", 20))
    label.grid(row=0, column=0, padx=10, pady=10)
    frame_main.grid_columnconfigure(0, weight=1)
    frame_main.grid_columnconfigure(2, weight=1)
    frame_main.grid_columnconfigure(4, weight=2)
    frame_main.grid_columnconfigure(6, weight=1)
