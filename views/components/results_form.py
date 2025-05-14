import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import traceback
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import glob
import json
import subprocess
import sys
import importlib.util

class ResultsForm(ttk.Frame):
    """Results form component for displaying experiment results"""
    
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.main_frame = ttk.Frame(self)
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self.results_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "results_output")
        self.param_vars = {}
        self.create_folder_selection()
        
    def create_folder_selection(self):
        """Create folder selection area"""
        select_frame = ttk.Frame(self.main_frame)
        select_frame.pack(fill="x", pady=2)
        
        label = ttk.Label(select_frame, text="Select Results Folder:")
        label.pack(fill="x", pady=1)
        
        subfolders = [d for d in os.listdir(self.results_dir) 
                     if os.path.isdir(os.path.join(self.results_dir, d))]
        
        self.folder_var = tk.StringVar()
        self.folder_combo = ttk.Combobox(select_frame, 
                                       textvariable=self.folder_var,
                                       values=subfolders,
                                       state="readonly")
        self.folder_combo.pack(fill="x")
    
            
        self.folder_combo.bind('<<ComboboxSelected>>', self.on_folder_selected)
        
    def on_folder_selected(self, event=None):
        """Handle folder selection event"""
        selected_folder = self.folder_var.get()
        if not selected_folder:
            return
            
        param_file = os.path.join(self.results_dir, selected_folder, "param.json")
        try:
            if os.path.exists(param_file):
                with open(param_file, 'r', encoding='utf-8') as f:
                    params = json.load(f)
                self.create_param_inputs(params)
            else:
                self._clear_components()
        except Exception as e:
            print(f"Failed to read parameter configuration: {str(e)}")
            self._clear_components()
                    
    def create_param_inputs(self, params):
        """Create parameter input controls"""
        self._clear_components()
        
        for section_name, section_params in params.items():
            section_frame = self._create_section_frame(section_name)
            for param_info in section_params:
                self._create_param_control(section_frame, param_info)
                
        self._create_execute_button()
                
    def _create_section_frame(self, section_name):
        """Create a section frame with title"""
        section_frame = ttk.LabelFrame(self.main_frame, 
                                     text=section_name.upper(),
                                     padding=2)
        section_frame.pack(fill="x", pady=2)
        return section_frame
                
    def _create_param_control(self, parent, param_info):
        """Create a single parameter control"""
        param_name = param_info.get("name", "Unnamed Parameter")
        param_type = param_info.get("type", "string")
        param_default = param_info.get("default", "")
        
        param_frame = ttk.Frame(parent)
        param_frame.pack(fill="x", pady=1)
        
        label = ttk.Label(param_frame, text=f"{param_name}:")
        label.pack(fill="x", pady=1)
        
        if param_type in ["file_paths", "file_path"]:
            force_dir = param_name == "output_path"
            self._create_file_control(param_frame, param_name, param_type, force_dir)
        else:
            self._create_text_control(param_frame, param_name, param_default)
            
    def _create_file_control(self, parent, param_name, param_type, force_dir=False):
        """Create file selection control"""
        path_frame = ttk.Frame(parent)
        path_frame.pack(fill="x")
        
        tree = self._create_treeview(path_frame, param_type, force_dir)
        
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=1)
        
        self._create_file_buttons(btn_frame, tree, param_name, param_type, force_dir)
        self.param_vars[param_name] = tree
        
    def _create_treeview(self, parent, param_type, force_dir):
        """Create a treeview with optional scrollbar"""
        if param_type == "file_paths" and not force_dir:
            scrollbar = ttk.Scrollbar(parent)
            scrollbar.pack(side="right", fill="y")
            
            tree = ttk.Treeview(parent, 
                               height=3,
                               show="tree",
                               yscrollcommand=scrollbar.set)
            tree.pack(fill="x", expand=True)
            
            scrollbar.config(command=tree.yview)
        else:
            tree = ttk.Treeview(parent, 
                               height=1,
                               show="tree")
            tree.pack(fill="x", expand=True)
        return tree
        
    def _create_file_buttons(self, parent, tree, param_name, param_type, force_dir):
        """Create file selection buttons"""
        if param_type == "file_paths" and not force_dir:
            self._create_multiple_file_buttons(parent, tree, param_name)
        else:
            self._create_single_file_button(parent, tree, param_name, force_dir)
            
    def _create_multiple_file_buttons(self, parent, tree, param_name):
        """Create buttons for multiple file selection"""
        select_file_btn = ttk.Button(parent, 
                                   text="Select Files",
                                   command=lambda: self._select_files(tree, param_name, True))
        select_file_btn.pack(side="left", padx=2)
        
        select_dir_btn = ttk.Button(parent, 
                                  text="Select Directory",
                                  command=lambda: self._select_directory(tree, param_name))
        select_dir_btn.pack(side="left", padx=2)
        
    def _create_single_file_button(self, parent, tree, param_name, force_dir):
        """Create button for single file/directory selection"""
        text = "Select Directory" if force_dir else "Browse"
        command = (lambda: self._select_directory(tree, param_name)) if force_dir else \
                 (lambda: self._select_files(tree, param_name, False))
                 
        select_btn = ttk.Button(parent, text=text, command=command)
        select_btn.pack(side="left")
            
    def _create_text_control(self, parent, param_name, default_value):
        """Create text input control"""
        text_var = tk.StringVar(value=default_value)
        text_entry = ttk.Entry(parent, textvariable=text_var)
        text_entry.pack(side="left")
        self.param_vars[param_name] = text_var
        
    def _select_files(self, tree, param_name, is_multiple):
        """Handle file selection"""
        if is_multiple:
            paths = filedialog.askopenfilenames(
                title=f"Select {param_name} Files",
                filetypes=[("All Files", "*.*")]
            )
            if paths:
                self._add_paths_to_tree(tree, paths)
        else:
            path = filedialog.askopenfilename(
                title=f"Select {param_name} File",
                filetypes=[("All Files", "*.*")]
            )
            if path:
                self._clear_tree(tree)
                self._add_paths_to_tree(tree, [path])
                    
    def _select_directory(self, tree, param_name):
        """Handle directory selection"""
        path = filedialog.askdirectory(title=f"Select {param_name} Directory")
        if path:
            # 检查是否是多选模式（通过tree的高度判断）
            if tree.cget("height") > 1:
                # 多选模式：不清空，直接添加
                self._add_paths_to_tree(tree, [path])
            else:
                # 单选模式：清空后添加
                self._clear_tree(tree)
                self._add_paths_to_tree(tree, [path])
            
    def _clear_tree(self, tree):
        """Clear all items from tree"""
        for item in tree.get_children():
            tree.delete(item)
            
    def _add_paths_to_tree(self, tree, paths):
        """Add paths to tree without duplicates"""
        existing_paths = [tree.item(item)["text"] for item in tree.get_children()]
        for path in paths:
            if path and path not in existing_paths:
                tree.insert("", "end", text=path)
                
    def _create_execute_button(self):
        """Create execute button at the bottom"""
        execute_frame = ttk.Frame(self.main_frame)
        execute_frame.pack(fill="x", pady=10)
        
        execute_btn = ttk.Button(execute_frame, 
                               text="Execute",
                               command=self._on_execute)
        execute_btn.pack(side="right", padx=5)
        
    def _on_execute(self):
        """Handle execute button click"""
        try:
            current_folder = self.folder_var.get()
            if not current_folder:
                messagebox.showerror("Error", "Please select a folder first")
                return
                
            main_py = os.path.join(self.results_dir, current_folder, "main.py")
            if not os.path.exists(main_py):
                messagebox.showerror("Error", f"main.py not found in {current_folder}")
                return
                
            config = self.get_param_values()
            self._run_main_py(main_py, config)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to execute: {str(e)}")
            print(traceback.format_exc())
            
    def _run_main_py(self, main_py, config):
        """Run main.py with given config"""
        folder_path = os.path.dirname(main_py)
        if folder_path not in sys.path:
            sys.path.append(folder_path)
            
        spec = importlib.util.spec_from_file_location("main", main_py)
        main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_module)
        
        if not hasattr(main_module, 'run'):
            messagebox.showerror("Error", "main.py must have a 'run' function")
            return
            
        main_module.run(config)
        
    def _clear_components(self):
        """Clear all components except folder selection"""
        for widget in self.main_frame.winfo_children()[1:]:
            widget.destroy()
        self.param_vars = {}
        
    def get_param_values(self):
        """Get all parameter values"""
        values = {}
        for name, var in self.param_vars.items():
            if isinstance(var, ttk.Treeview):
                # 获取树形视图的高度来判断是单文件还是多文件
                if var.cget("height") > 1:
                    # 多文件模式：返回路径列表
                    values[name] = [var.item(item)["text"] for item in var.get_children()]
                else:
                    # 单文件模式：只返回第一个路径
                    items = var.get_children()
                    values[name] = var.item(items[0])["text"] if items else ""
            else:
                values[name] = var.get()
        return values
        
    def refresh(self):
        """Refresh results data"""
        subfolders = [d for d in os.listdir(self.results_dir) 
                     if os.path.isdir(os.path.join(self.results_dir, d))]
        self.folder_combo['values'] = subfolders
        if subfolders:
            self.folder_combo.set(subfolders[0])
            self.on_folder_selected()
