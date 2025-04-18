from matplotlib import pyplot as plt

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
