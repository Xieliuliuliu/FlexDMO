from matplotlib import pyplot as plt
import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.patches import Circle
from matplotlib.layout_engine import ConstrainedLayoutEngine

from utils.metrics import calculate_IGD
from views.common.GlobalVar import global_vars


def fit_chart_layout(figure):
    """Lay out the embedded figure, ignoring transient tiny resize frames."""
    for ax in figure.axes:
        ax.tick_params(axis='both', labelsize=9)
    if isinstance(figure.get_layout_engine(), ConstrainedLayoutEngine):
        return
    width, height = figure.get_size_inches() * figure.dpi
    if width >= 250 and height >= 180 * max(1, len(figure.axes)):
        figure.tight_layout(pad=0.8)


def get_feasible_mask(population):
    """Return a boolean mask aligned with the population matrices."""
    return np.asarray(
        [bool(getattr(individual, "feasible", True)) for individual in population],
        dtype=bool,
    )


def shade_infeasible_region(information, ax):
    """Shade objective-space regions described by the current problem."""
    constraints = information.get("objective_constraints", [])
    original_xlim = ax.get_xlim()
    original_ylim = ax.get_ylim()
    label_pending = True
    for constraint in constraints:
        kind = constraint.get("kind", "axis")
        label = "Infeasible region" if label_pending else None

        if kind == "circle":
            try:
                center = constraint["center"]
                radius = float(constraint["radius"])
                if len(center) != 2 or radius <= 0:
                    continue
                patch = Circle(
                    (float(center[0]), float(center[1])),
                    radius,
                    facecolor="gray",
                    edgecolor="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
            except (KeyError, TypeError, ValueError):
                continue
            ax.add_patch(patch)
            label_pending = False
            continue

        if kind == "interval":
            try:
                axis = int(constraint.get("axis", -1))
                region_lower = float(constraint["lower"])
                region_upper = float(constraint["upper"])
            except (KeyError, TypeError, ValueError):
                continue
            if region_lower >= region_upper:
                continue
            if axis == 0:
                lower, upper = original_xlim
                if region_upper <= lower or region_lower >= upper:
                    continue
                ax.axvspan(
                    max(region_lower, lower),
                    min(region_upper, upper),
                    color="gray",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
                ax.axvline(
                    region_lower,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
                ax.axvline(
                    region_upper,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
            elif axis == 1:
                lower, upper = original_ylim
                if region_upper <= lower or region_lower >= upper:
                    continue
                ax.axhspan(
                    max(region_lower, lower),
                    min(region_upper, upper),
                    color="gray",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
                ax.axhline(
                    region_lower,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
                ax.axhline(
                    region_upper,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
            else:
                continue
            label_pending = False
            continue

        try:
            axis = int(constraint.get("axis", -1))
            operator = constraint.get("operator")
            threshold = float(constraint["threshold"])
        except (KeyError, TypeError, ValueError):
            continue

        if axis == 0:
            lower, upper = original_xlim
            if operator in (">=", ">") and threshold > lower:
                ax.axvspan(
                    lower,
                    min(threshold, upper),
                    color="gray",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
                ax.axvline(
                    threshold,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
            elif operator in ("<=", "<") and threshold < upper:
                ax.axvspan(
                    max(threshold, lower),
                    upper,
                    color="gray",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
                ax.axvline(
                    threshold,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
            else:
                continue
        elif axis == 1:
            lower, upper = original_ylim
            if operator in (">=", ">") and threshold > lower:
                ax.axhspan(
                    lower,
                    min(threshold, upper),
                    color="gray",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
                ax.axhline(
                    threshold,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
            elif operator in ("<=", "<") and threshold < upper:
                ax.axhspan(
                    max(threshold, lower),
                    upper,
                    color="gray",
                    alpha=0.2,
                    zorder=0,
                    label=label,
                )
                ax.axhline(
                    threshold,
                    color="dimgray",
                    linewidth=0.8,
                    linestyle="--",
                    zorder=1,
                )
            else:
                continue
        else:
            continue

        label_pending = False

    # Background spans and boundary lines must not expand the data viewport.
    ax.set_xlim(original_xlim)
    ax.set_ylim(original_ylim)


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
    
    # 只取当前时间步之前的4个时间步
    recent_times = [t for t in history if t < t_now][-4:] if len(history) > 4 else [t for t in history if t < t_now]
    # --- 绘制历史 PF（灰色，变淡） ---
    for t_hist in recent_times:
        try:
            info_hist = history[t_hist]
            last_key, last_value = list(info_hist.items())[-1]
            pf_hist = last_value["population"].get_objective_matrix()
            pof_hist = last_value["POF"]
            if pof_hist[:, 0] is not None:
                ax.scatter(pof_hist[:, 0], pof_hist[:, 1],
                        s=10, color='gray', alpha=0.2, marker='.')
            ax.scatter(pf_hist[:, 0], pf_hist[:, 1],
                       s=6, alpha=0.2, color='gray')
        except Exception as e:
            print(f"[绘制错误] t={t_hist}, error={e}")
            continue

    # --- 当前 PF ---
    feasible = get_feasible_mask(population)
    if np.any(feasible):
        ax.scatter(
            pf_matrix[feasible, 0],
            pf_matrix[feasible, 1],
            s=10,
            label="Feasible solutions",
            alpha=0.7,
            color="blue",
        )
    if np.any(~feasible):
        ax.scatter(
            pf_matrix[~feasible, 0],
            pf_matrix[~feasible, 1],
            s=14,
            label="Infeasible solutions",
            alpha=0.7,
            color="crimson",
            marker="x",
        )

    # --- 当前 POF（理论） ---
    if true_PF is not None:
        ax.scatter(true_PF[:, 0], true_PF[:, 1],
                s=10, label="Current True POF", color='orange', alpha=0.9, marker='.')

    shade_infeasible_region(information, ax)

    # 图标题增加 evaluate_time
    ax.set_title(f"Dynamic PF (t={t_now}, evaluations={evaluate_time})", fontsize=10)
    ax.set_xlabel("f1", fontsize=9)
    ax.set_ylabel("f2", fontsize=9)
    ax.legend(fontsize=8)
    ax.grid(True)
    fit_chart_layout(ax.figure)


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
                pop_y = last_env['population'].get_feasible_objective_matrix()
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
                pop_y = current_env['population'].get_feasible_objective_matrix()
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
        fit_chart_layout(ax.figure)
        
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

    # 获取决策变量的维度
    num_decision = ps_matrix.shape[1]
    decision = list(range(1, num_decision + 1))

    ax.clear()

    # --- 获取历史信息 ---
    history = global_vars['test_module'].get("runtime_populations", {})
    
    # 只取当前时间步之前的4个时间步
    recent_times = [t for t in history if t < t_now][-4:] if len(history) > 4 else [t for t in history if t < t_now]

    # --- 绘制历史 PS（变淡） ---
    for t_hist in recent_times:
        try:
            info_hist = history[t_hist]
            last_key, last_value = list(info_hist.items())[-1]
            # 先画POS
            pos_hist = last_value["POS"]
            if pos_hist[:, 0] is not None:
                lines = [list(zip(decision, individual)) for individual in pos_hist]
                lc = LineCollection(lines, colors='orange', alpha=0.1)
                ax.add_collection(lc)
            # 再画求解的PS
            ps_hist = last_value["population"].get_decision_matrix()
            lines = [list(zip(decision, individual)) for individual in ps_hist]
            lc = LineCollection(lines, colors='gray', alpha=0.1)
            ax.add_collection(lc)
        except Exception as e:
            print(f"[绘制错误] t={t_hist}, error={e}")
            continue

    # --- 当前 POS（理论） ---
    # 如果有理论 Pareto 集，绘制理论 Pareto 集
    if true_PS is not None:
        lines = [list(zip(decision, individual)) for individual in true_PS]
        lc = LineCollection(lines, colors='red', alpha=1)
        ax.add_collection(lc)
        ax.plot([], [], alpha=0.9, color='red', label="True POS")  # 添加图例

    # --- 当前 PS ---
    lines = [list(zip(decision, individual)) for individual in ps_matrix]
    lc = LineCollection(lines, colors='blue', alpha=1)
    ax.add_collection(lc)
    ax.plot([], [], alpha=0.6, color='blue', label="Current PS")

    # 图标题增加 evaluate_time
    ax.set_title(f"Dynamic PS (t={t_now}, evaluations={evaluate_time})", fontsize=10)
    ax.set_xlabel("Decision", fontsize=9)
    ax.set_ylabel("Value", fontsize=9)
    ax.autoscale_view()
    ax.set_xlim(
        (1, num_decision)
        if num_decision > 1
        else (0.5, 1.5)
    )
    ax.set_xticks(decision)
    ax.legend(fontsize=8)
    ax.grid(True)
    fit_chart_layout(ax.figure)


def draw_constraint_violation(information, ax):
    population = information["population"]
    violations = population.get_constraint_violation_vector()
    ax.clear()
    colors = np.where(violations <= 1e-12, "seagreen", "crimson")
    ax.bar(np.arange(len(violations)), violations, color=colors, width=0.8)
    ax.axhline(0.0, color="black", linewidth=0.8)
    ax.set_title(
        "Constraint Violation "
        f"(t={information.get('t', '?')}, "
        f"evaluations={information.get('evaluate_times', '?')})",
        fontsize=10,
    )
    ax.set_xlabel("Individual", fontsize=9)
    ax.set_ylabel("Total positive violation", fontsize=9)
    ax.grid(True, axis="y", linestyle="--", alpha=0.4)
    fit_chart_layout(ax.figure)


def draw_selected_chart(information, ax, chart_type='Pareto Front'):
    """根据选择的类型绘制相应的图表
    
    Args:
        information: 当前时间步的信息
        ax: matplotlib 的轴对象
        chart_type: 图表类型，可选 'Pareto Front' 或 'IGD'
    """
    if chart_type == 'Pareto Front':
        draw_PF(information, ax)
    elif chart_type == 'IGD':
        draw_IGD_curve(information, ax)
    elif chart_type == 'Pareto Set':
        draw_PS(information, ax)
    elif chart_type == 'Constraint Violation':
        draw_constraint_violation(information, ax)
    else:
        raise ValueError(f"未知的图表类型: {chart_type}")
