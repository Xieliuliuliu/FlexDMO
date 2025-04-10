from matplotlib import pyplot as plt


def draw_PF(population, ax):
    objective_matrix = population.get_objective_matrix()
    ax.clear()  # 清空当前图表
    ax.scatter(objective_matrix[:, 0], objective_matrix[:, 1], label="Objective Data")
    ax.set_title("Dynamic Analysis Result", fontsize=10)
    ax.set_xlabel("X Axis", fontsize=9)
    ax.set_ylabel("Y Axis", fontsize=9)
    ax.legend(fontsize=8)
    plt.tight_layout()
