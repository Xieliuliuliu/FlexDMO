import importlib
import os
import time
import traceback

from matplotlib.gridspec import GridSpec

from plots.test_module.draw_population import draw_IGD_curve, draw_PF, draw_PS, draw_selected_chart
from utils.information_parser import convert_config_to_numeric
from utils.result_io import save_test_module_information_results
from views.common.GlobalVar import global_vars
from multiprocessing import Manager, Pipe, Process
import threading

def load_main_class_from_folder(folder_path):
    """
    给定一个文件夹路径，加载其中的 main.py 并返回其中定义的类（与文件夹同名）
    """
    main_path = os.path.join(folder_path, "main.py")
    module_name = os.path.basename(folder_path)

    if not os.path.isfile(main_path):
        raise FileNotFoundError(f"No main.py found in {folder_path}")

    spec = importlib.util.spec_from_file_location(module_name, main_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 默认类名就是文件夹名，例如 NSGA2 目录下就是 NSGA2 类
    class_name = os.path.basename(folder_path)
    if not hasattr(module, class_name):
        raise AttributeError(f"{class_name} class not found in {main_path}")

    return getattr(module, class_name)


def run_in_test_mode(response_strategy, search_algorithm, problem_name, result_to_show: str, runtime_config: dict):
    """运行测试模式：已有子进程则恢复，否则启动新进程"""
    current_process = global_vars['test_module'].get("current_process")
    current_state = global_vars['test_module'].get("process_state")

    if current_process and current_process.is_alive():
        if current_state:
            current_state.value = 'running'
        print("[主进程] 已有子进程，已发送恢复指令")
        return

    start_new_test_process(response_strategy, search_algorithm, problem_name, result_to_show, runtime_config)

def start_new_test_process(response_strategy, search_algorithm, problem_name, result_to_show: str, runtime_config: dict):
    """启动一个新的子进程并监听 Pipe"""
    manager = Manager()
    state = manager.Value('c', 'running')
    parent_conn, child_conn = Pipe()

    p = Process(
        target=run_in_test_mode_process,
        args=(response_strategy, search_algorithm, problem_name, result_to_show, runtime_config, state, child_conn),
        name="TestOptimizer"
    )

    save_state_in_test_mode(state, p, parent_conn,child_conn)
    p.start()
    threading.Thread(
        target=listen_pipe,
        args=(parent_conn, p),
        daemon=True
    ).start()



def run_in_test_mode_process(response_strategy, search_algorithm, problem_name, result_to_show: str, runtime_config,
                             state, child_conn):
    """独立子进程中执行的优化逻辑"""
    try:
        print("Subprocess started for test mode optimization...")

        # 加载类
        ResponseClass = load_main_class_from_folder(response_strategy['folder_name'])
        SearchClass = load_main_class_from_folder(search_algorithm['folder_name'])
        ProblemClass = load_main_class_from_folder(problem_name['folder_name'])

        # 实例化对象
        response_instance = ResponseClass(**convert_config_to_numeric(runtime_config['selected_dynamic']))
        search_instance = SearchClass(**convert_config_to_numeric(runtime_config['selected_search']), state=state,pip=child_conn)
        problem_instance = ProblemClass(**convert_config_to_numeric(runtime_config['selected_problem']))

        search_instance.optimize(problem_instance, response_instance)
    except Exception as e:
        print(f"[Error in subprocess]: {traceback.print_exc()}")


def save_state_in_test_mode(state, p, parent_conn,child_conn):
    global_vars['test_module']["process_state"] = state
    global_vars['test_module']["current_process"] = p
    global_vars['test_module']["parent_conn"] = parent_conn
    global_vars['test_module']["child_conn"] = child_conn
    global_vars['process_manager'][p.name] = {"process_state": state, "current_process": p, "parent_conn": parent_conn, "child_conn":child_conn}
    global_vars['test_module']["runtime_populations"] = {}


def delete_state_in_test_mode():
    """删除测试模式下的状态
    
    清理所有相关资源，包括进程、管道连接和全局变量
    """
    try:
        # 获取 test_module 字典，如果不存在则返回空字典
        test_module = global_vars.get('test_module', {})
        
        # 检查并清理进程
        if "current_process" in test_module and test_module["current_process"] is not None:
            p = test_module["current_process"]
            
            # 关闭管道连接
            if "child_conn" in test_module and test_module["child_conn"] is not None:
                test_module["child_conn"].close()
                print("关闭子进程管道连接")
            
            # 终止进程
            if p.is_alive():
                p.terminate()
                print('终止进程')
            
            # 清理进程管理器中的记录
            if p.name in global_vars.get('process_manager', {}):
                global_vars['process_manager'][p.name] = None
        
        # 重置所有相关状态
        test_module["process_state"] = None
        test_module["current_process"] = None
        test_module["parent_conn"] = None
        test_module["child_conn"] = None
        test_module["runtime_populations"] = {}
        
    except Exception as e:
        print(f"[错误] 清理状态时出错: {str(e)}")
        # 即使出错也尝试清理全局变量
        if 'test_module' in global_vars:
            global_vars['test_module'] = {}



# 主进程监听 pipe
def listen_pipe(parent_conn, process):
    print("[主进程] Pipe监听已启动")
    try:
        # 在启动时禁用进度条
        scale = global_vars['test_module'].get('scale')
        if scale:
            scale.configure(state='disabled')
            
        while True:
            time.sleep(0.2)  # 避免空转

            # 检查子进程是否还活着
            if not process.is_alive():
                print("[主进程] 子进程已结束，Pipe监听线程退出")
                break
            # 安全地 poll Pipe
            if parent_conn.poll():
                try:
                    information = parent_conn.recv()
                    # print(f"[主进程] 收到子进程信息")
                    save_runtime_population_information(information)
                    draw_chart(information)
                except EOFError:
                    print("[主进程] Pipe连接已关闭（EOF）")
                    break
    except (BrokenPipeError, OSError) as e:
        print(f"[主进程] Pipe监听异常中止: {e}")
    finally:
        print("[主进程] close parent")
        # 在结束时启用进度条
        scale = global_vars['test_module'].get('scale')
        print("正在保存运行数据")
        try:
            save_test_module_information_results()
        except Exception as e:
            print(f"[主进程] 保存数据异常")
        if scale:
            scale.configure(state='normal')
        parent_conn.close()

def canvas_draw(canvas,canvas_version):
    lock = global_vars['test_module']['canvas_lock']
    lock.acquire()
    canvas_version_after = global_vars['test_module']['canvas_version']
    if canvas_version == canvas_version_after:
        canvas.draw()
    lock.release()


def save_runtime_population_information(information):
    t = information["t"]
    evaluate_times = information["evaluate_times"]

    # 确保 'runtime_populations' 字典存在
    if "runtime_populations" not in global_vars['test_module']:
        global_vars['test_module']["runtime_populations"] = {}

    # 初始化该代数 t 的信息
    if t not in global_vars['test_module']["runtime_populations"]:
        global_vars['test_module']["runtime_populations"][t] = {}

    # 保存信息
    global_vars['test_module']["runtime_populations"][t][evaluate_times] = information


def draw_chart(information):
     # 更新图表
    canvas = global_vars['test_module'].get('canvas')
    fig = canvas.figure

    # 获取要显示的图表类型
    result_to_show = global_vars['test_module'].get('result_to_show', ['Pareto Front'])
    lock = global_vars['test_module']['canvas_lock']
    canvas_version = global_vars['test_module']['canvas_version']
    lock.acquire()

    # 遍历 fig.axes 和 result_to_show，一一进行绘图
    for ax, result_type in zip(fig.axes, result_to_show):
       draw_selected_chart(information, ax, result_type)

    # 更新图表
    lock.release()
    # 如果不是主线程，使用 after 方法在主线程中调用 canvas.draw()
    canvas.get_tk_widget().after(0, lambda: canvas_draw(canvas, canvas_version))