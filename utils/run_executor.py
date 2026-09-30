import importlib
import os
import traceback

from plots.test_module.draw_population import draw_selected_chart
from utils.information_parser import convert_config_to_numeric
from utils.result_io import save_test_module_information_results
from utils.ui_dispatch import dispatch_ui
from utils.test_runtime import history_lock, set_run_status
from views.common.GlobalVar import global_vars
from multiprocessing import Manager, Pipe, Process
import threading


LIVE_CHART_REFRESH_MS = 100


def queue_latest_chart(information):
    """Keep only the newest live frame while preserving full replay history."""
    global_vars["test_module"]["pending_live_information"] = information


def take_latest_chart():
    """Consume the newest frame waiting for the Tk main thread."""
    return global_vars["test_module"].pop("pending_live_information", None)


def start_live_chart_pump(widget, refresh_ms=LIVE_CHART_REFRESH_MS):
    """Render the newest available frame at a bounded rate on the Tk thread."""
    test_state = global_vars["test_module"]
    token = test_state.get("live_chart_pump_token", 0) + 1
    test_state["live_chart_pump_token"] = token

    def pump():
        current_state = global_vars["test_module"]
        if current_state.get("live_chart_pump_token") != token:
            return
        try:
            if not widget.winfo_exists():
                return
            information = take_latest_chart()
            if information is not None:
                draw_chart(information)
                evaluation = information.get("evaluate_times")
                current_state["last_live_evaluation"] = evaluation
                current_label = current_state.get("current_label")
                if current_label is not None and evaluation is not None:
                    current_label.configure(
                        text=f"当前评估次数： {evaluation}"
                    )
        except Exception as error:
            print(f"[Live chart refresh error] {error}")
        try:
            if (
                current_state.get("live_chart_pump_token") == token
                and widget.winfo_exists()
            ):
                current_state["live_chart_pump_job"] = widget.after(
                    refresh_ms, pump
                )
        except Exception:
            return

    test_state["live_chart_pump_job"] = widget.after(refresh_ms, pump)


def stop_live_chart_pump():
    """Invalidate the current live-render loop and discard its pending frame."""
    test_state = global_vars.get("test_module", {})
    test_state["live_chart_pump_token"] = (
        test_state.get("live_chart_pump_token", 0) + 1
    )
    test_state.pop("pending_live_information", None)


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
        set_run_status("running")
        print("[主进程] 已有子进程，已发送恢复指令")
        return

    start_new_test_process(response_strategy, search_algorithm, problem_name, result_to_show, runtime_config)

def start_new_test_process(response_strategy, search_algorithm, problem_name, result_to_show: str, runtime_config: dict):
    """启动一个新的子进程并监听 Pipe"""
    delete_state_in_test_mode(clear_history=False)
    set_run_status("starting")
    manager = Manager()
    state = manager.Value('c', 'running')
    parent_conn, child_conn = Pipe()

    p = Process(
        target=run_in_test_mode_process,
        args=(response_strategy, search_algorithm, problem_name, result_to_show, runtime_config, state, child_conn),
        name="TestOptimizer"
    )

    save_state_in_test_mode(state, p, parent_conn,child_conn)
    global_vars['test_module']["worker_manager"] = manager
    global_vars['test_module']["run_process"] = p
    try:
        p.start()
    except Exception:
        delete_state_in_test_mode(clear_history=False)
        raise
    # The parent must not retain a writer; otherwise EOF never arrives on failure.
    child_conn.close()
    set_run_status("running")
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
        search_instance = SearchClass(**convert_config_to_numeric(runtime_config['selected_search']), state=state, pip=child_conn, mode='test')
        problem_instance = ProblemClass(**convert_config_to_numeric(runtime_config['selected_problem']))

        search_instance.optimize(problem_instance, response_instance)
    except Exception as error:
        print("[Error in subprocess]:")
        traceback.print_exc()
        try:
            child_conn.send({"status": "error", "error": f"{type(error).__name__}: {error}"})
        except (BrokenPipeError, EOFError, OSError):
            pass
        raise
    finally:
        child_conn.close()


def save_state_in_test_mode(state, p, parent_conn,child_conn):
    global_vars['test_module']["process_state"] = state
    global_vars['test_module']["current_process"] = p
    global_vars['test_module']["parent_conn"] = parent_conn
    global_vars['test_module']["child_conn"] = child_conn
    global_vars['process_manager'][p.name] = {"process_state": state, "current_process": p, "parent_conn": parent_conn, "child_conn":child_conn}
    with history_lock:
        global_vars['test_module']["runtime_populations"] = {}
        global_vars['test_module'].pop("pending_live_information", None)
    global_vars['test_module'].pop("replay_timeline", None)


def delete_state_in_test_mode(clear_history=True):
    """删除测试模式下的状态
    
    清理所有相关资源，包括进程、管道连接和全局变量
    """
    try:
        # 获取 test_module 字典，如果不存在则返回空字典
        test_module = global_vars.get('test_module', {})
        with history_lock:
            test_module['run_process'] = None
        parent_conn = test_module.get('parent_conn')
        
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
            if p.pid is not None:
                p.join(timeout=1)
            
            # 清理进程管理器中的记录
            if p.name in global_vars.get('process_manager', {}):
                global_vars['process_manager'][p.name] = None
        
        # 重置所有相关状态
        test_module["process_state"] = None
        test_module["current_process"] = None
        test_module["parent_conn"] = None
        test_module["child_conn"] = None
        if parent_conn is not None:
            parent_conn.close()
        manager = test_module.pop("worker_manager", None)
        if manager is not None:
            manager.shutdown()
        if clear_history:
            with history_lock:
                test_module["runtime_populations"] = {}
            test_module.pop("replay_timeline", None)
        test_module.pop("pending_live_information", None)
        
    except Exception as e:
        print(f"[错误] 清理状态时出错: {str(e)}")
        # Never discard widget references or existing replay data on cleanup failure.



# 主进程监听 pipe
def listen_pipe(parent_conn, process):
    print("[主进程] Pipe监听已启动")
    worker_error = None
    try:
        # 在启动时禁用进度条
        scale = global_vars['test_module'].get('scale')
        if scale:
            def disable_replay():
                if global_vars['test_module'].get('run_process', process) is process and scale.winfo_exists():
                    scale.configure(state='disabled')
            dispatch_ui(disable_replay)
            
        while True:

            # 检查子进程是否还活着
            if not process.is_alive() and not parent_conn.poll():
                print("[主进程] 子进程已结束，Pipe监听线程退出")
                break
            # 安全地 poll Pipe
            if parent_conn.poll(0.1):
                try:
                    information = parent_conn.recv()
                    if information.get("status") == "error":
                        worker_error = information.get("error", "子进程执行失败")
                        continue
                    with history_lock:
                        if global_vars['test_module'].get('run_process', process) is not process:
                            break
                        save_runtime_population_information(information)
                        queue_latest_chart(information)
                except EOFError:
                    print("[主进程] Pipe连接已关闭（EOF）")
                    break
    except (BrokenPipeError, OSError) as e:
        print(f"[主进程] Pipe监听异常中止: {e}")
    finally:
        if hasattr(process, 'join'):
            process.join(timeout=1)
        print("[主进程] close parent")
        # 在结束时启用进度条
        scale = global_vars['test_module'].get('scale')
        def finalize_ui():
            active_process = global_vars['test_module'].get('current_process')
            if active_process is not None and active_process is not process:
                return
            state = global_vars['test_module']
            if state.get('run_process', process) is not process:
                return
            if scale is not None and hasattr(scale, 'winfo_exists') and not scale.winfo_exists():
                return
            current_label = global_vars['test_module'].get('current_label')
            total_label = global_vars['test_module'].get('total_label')
            failed = worker_error or (getattr(process, 'exitcode', 0) not in (0, None))
            if state.get('run_status') != 'stopped':
                set_run_status('failed' if failed else 'completed',
                               worker_error or (f"子进程退出码：{process.exitcode}" if failed else None))
            try:
                save_result = global_vars['test_module'].get('save_result')
                if state.get('runtime_populations') and save_result is not None and save_result.get():
                    print("正在保存运行数据")
                    path = save_test_module_information_results()
                    set_run_status(state['run_status'],
                                   f"{worker_error + '；' if worker_error else ''}结果已保存：{path}")
            except Exception as e:
                print(f"[主进程] 保存数据异常: {e}")
                set_run_status(state['run_status'], f"自动保存失败：{e}；请手动保存")
            if scale:
                scale.configure(state='normal')
                if current_label is not None and total_label is not None:
                    # 延迟导入可避免 handler 与 executor 的模块级循环依赖。
                    from views.test_module.test_module_handler import (
                        update_progress_control,
                    )

                    update_progress_control(
                        scale,
                        current_label,
                        total_label,
                        start_at_end=True,
                        render_selected=True,
                    )

        dispatch_ui(finalize_ui)
        parent_conn.close()

def canvas_draw(canvas,canvas_version):
    lock = global_vars['test_module']['canvas_lock']
    with lock:
        canvas_version_after = global_vars['test_module']['canvas_version']
        if canvas_version == canvas_version_after:
            canvas.draw()


def save_runtime_population_information(information):
    t = information["t"]
    evaluate_times = information["evaluate_times"]

    with history_lock:
        history = global_vars['test_module'].setdefault("runtime_populations", {})
        history.setdefault(t, {})[evaluate_times] = information


def draw_chart(information):
    # 更新图表；调用方必须位于 Tk 主线程。
    canvas = global_vars['test_module'].get('canvas')
    if canvas is None or information is None:
        return
    fig = canvas.figure

    # 获取要显示的图表类型
    result_to_show = global_vars['test_module'].get('result_to_show', ['Pareto Front'])
    lock = global_vars['test_module']['canvas_lock']
    canvas_version = global_vars['test_module']['canvas_version']
    with lock:
        for ax, result_type in zip(fig.axes, result_to_show):
            draw_selected_chart(information, ax, result_type)
    canvas_draw(canvas, canvas_version)
