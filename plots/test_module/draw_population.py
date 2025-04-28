from matplotlib import pyplot as plt
import numpy as np

from utils.metrics import calculate_IGD
from views.common.GlobalVar import global_vars


def draw_PF(information, ax):
    # 当前时间步 & 当前评估次数
    t_now = information.get("t", '?')
    evaluate_time = information["evaluate_times"]

    # 当前种群与目标函数值
    population = information["population"]
    pf_matrix = population.get_objective_matrix()
    true_PF = information.get("POF", None)

    ax.clear()

    # --- 获取历史信息 ---
    history = global_vars['test_module'].get("runtime_populations", {})

    # --- 绘制历史 PF（灰色，变淡） ---
    for t_hist, info_hist in history.items():
        if t_hist >= t_now:
            continue
        try:
            last_key, last_value = list(info_hist.items())[-1]
            pf_hist = last_value["population"].get_objective_matrix()
            pof_hist = last_value["POF"]
            if pof_hist[:, 0] is not None:
                ax.plot(pof_hist[:, 0], pof_hist[:, 1],
                        linestyle='--', linewidth=1, color='orange', alpha=0.2)
            ax.scatter(pf_hist[:, 0], pf_hist[:, 1],
                       s=6, alpha=0.2, color='gray')
        except Exception as e:
            print(f"[绘制错误] t={t_hist}, error={e}")
            continue

    # --- 当前 PF ---
    ax.scatter(pf_matrix[:, 0], pf_matrix[:, 1],
               s=10, label="Current PF", alpha=0.6, color='blue')

    # --- 当前 POF（理论） ---
    if true_PF is not None:
        ax.plot(true_PF[:, 0], true_PF[:, 1],
                linestyle='--', label="Current True POF", linewidth=1, color='orange', alpha=0.9)

    # 图标题增加 evaluate_time
    ax.set_title(f"Dynamic PF (t={t_now}, evaluations={evaluate_time})", fontsize=10)
    ax.set_xlabel("f1", fontsize=9)
    ax.set_ylabel("f2", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True)
    plt.tight_layout()


def draw_IGD_curve(information, ax):
    """绘制 IGD 随时间变化的曲线
    
    Args:
        information: 当前时间步的信息，可以是整数（表示时间步）或字典（包含种群信息）
        ax: matplotlib 的轴对象，用于绘制图表
    """
    # ===== 1. 初始化参数 =====
    # 确保时间步为整数
    t_now = int(float(information)) if isinstance(information, (int, float, str)) else int(float(information.get("t", 0)))
    evaluate_time = information["evaluate_times"] if isinstance(information, dict) else 0

    # ===== 2. 准备数据 =====
    # 获取历史信息并初始化数据收集列表
    history = global_vars['test_module'].get("runtime_populations", {})
    times = []          # 存储时间步
    igd_values = []     # 存储对应的 IGD 值
    
    # 清空当前图表
    ax.clear()
    
    # ===== 3. 处理历史数据 =====
    for t_hist_str, info_hist in history.items():
        # 将时间步转换为整数
        t_hist = int(float(t_hist_str))
        
        # 跳过当前及之后的时间点
        if t_hist >= t_now:
            continue
            
        try:
            # 获取最后一个环境的种群数据
            last_env = list(info_hist.values())[-1]
            if 'POF' in last_env and 'population' in last_env:
                # 计算并存储 IGD 值
                pof = last_env['POF']
                pop_y = np.array([ind.F for ind in last_env['population']])
                igd = calculate_IGD(pop_y, pof)
                times.append(t_hist)  # 已经确保是整数
                igd_values.append(igd)
        except Exception as e:
            print(f"[绘制错误] t={t_hist}, error={e}")
            continue
    
    # ===== 4. 处理当前时间点数据 =====
    try:
        if isinstance(information, dict):
            current_env = information
            if 'POF' in current_env and 'population' in current_env:
                # 计算并存储当前时间点的 IGD 值
                pof = current_env['POF']
                pop_y = np.array([ind.F for ind in current_env['population']])
                igd = calculate_IGD(pop_y, pof)
                times.append(t_now)
                igd_values.append(igd)
    except Exception as e:
        print(f"[绘制错误] 当前时间点, error={e}")
    
    # ===== 5. 绘制图表 =====
    if times and igd_values:
        # 绘制 IGD 曲线
        ax.plot(times, igd_values, 
                linestyle='-',          # 实线
                marker='o',             # 圆形标记
                markersize=4,           # 标记大小
                linewidth=1,            # 线宽
                color='blue',           # 蓝色
                label='IGD')            # 图例标签
    
        # 设置图表属性
        ax.set_title(f"IGD Curve (t={t_now}, evaluations={evaluate_time})", 
                    fontsize=10)
        ax.set_xlabel("Time Step", fontsize=9)
        ax.set_ylabel("IGD Value", fontsize=9)
        ax.legend(fontsize=8)
        ax.grid(True, linestyle='--', alpha=0.7)  # 添加网格线
        
        # 设置 x 轴为整数刻度
        ax.xaxis.set_major_locator(plt.MaxNLocator(integer=True))
        
        # 优化布局
        plt.tight_layout()
        
        # 设置刻度字体大小
        ax.tick_params(axis='both', labelsize=8)


def draw_PS(information, ax):
    # 当前时间步 & 当前评估次数
    t_now = information.get("t", '?')
    evaluate_time = information["evaluate_times"]

    # 当前种群与目标函数值
    population = information["population"]
    ps_matrix = population.get_decision_matrix()
    true_PS = information.get("POS", None)

    ax.clear()

    # --- 当前 PS ---
    # 获取决策变量的维度
    num_decision = ps_matrix.shape[1]
    decision = list(range(1, num_decision + 1))

    # 绘制每个个体的决策变量
    for individual in ps_matrix:
        ax.plot(decision, individual, alpha=0.6, color='blue')

    # --- 当前 POS（理论） ---
    # 如果有理论 Pareto 集，绘制理论 Pareto 集
    if true_PS is not None:
        for individual in true_PS:
            ax.plot(decision, individual, alpha=0.9, color='red')

    # 图标题增加 evaluate_time
    ax.set_title(f"Dynamic PS (t={t_now}, evaluations={evaluate_time})", fontsize=10)
    ax.set_xlabel("Decision", fontsize=9)
    ax.set_ylabel("Value", fontsize=9)
    ax.legend(["Current PS", "True POS"], fontsize=8)
    ax.grid(True)
    plt.tight_layout()


def draw_selected_chart(information, ax, chart_type='Population'):
    """根据选择的类型绘制相应的图表
    
    Args:
        information: 当前时间步的信息
        ax: matplotlib 的轴对象
        chart_type: 图表类型，可选 'Population' 或 'IGD'
    """
    if chart_type == 'Population':
        draw_PF(information, ax)
    elif chart_type == 'IGD':
        draw_IGD_curve(information, ax)
    elif chart_type == 'Pareto Set':
        draw_PS(information, ax)
    else:
        raise ValueError(f"未知的图表类型: {chart_type}")
