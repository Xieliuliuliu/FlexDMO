import numpy as np


def calculate_IGD(pop_y, pf):
    """计算反向世代距离(IGD)
    
    Args:
        pop_y: 种群的目标值
        pf: 真实Pareto前沿
        
    Returns:
        float: IGD值
    """
    # 计算每个PF点到最近种群点的距离
    distances = np.min(np.sqrt(np.sum((pf[:, np.newaxis] - pop_y)**2, axis=2)), axis=1)
    return np.mean(distances)

def calculate_HV(pop_y, ref_point):
    """计算超体积(HV)
    
    Args:
        pop_y: 种群的目标值，形状为(n, m)，其中m为目标数
        ref_point: 参考点，形状为(m,)
        
    Returns:
        float: HV值
    """
    # 确保所有点都被参考点支配
    if pop_y.size == 0:
        return 0.0
    mask = np.all(pop_y <= ref_point, axis=1)
    points = pop_y[mask]
    if len(points) == 0:
        return 0.0
    
    # 按第一个目标降序排序
    points = points[points[:, 0].argsort()[::-1]]
    
    # 筛选出在第二个目标上严格递增的点（二维情况）
    filtered = []
    max_y = -np.inf
    for p in points:
        if p[1] > max_y:  # 只保留严格递增的点
            filtered.append(p)
            max_y = p[1]
    points = np.array(filtered)
    
    # 计算超体积
    hv = 0.0
    prev_x = ref_point[0]
    for p in points:
        current_x = p[0]
        current_y = p[1]
        hv += (prev_x - current_x) * (ref_point[1] - current_y)
        prev_x = current_x
    
    return hv

def calculate_MIGD(runtime_populations):
    """计算平均反向世代距离(MIGD)
    
    Args:
        runtime_populations: 运行时种群数据
        
    Returns:
        float: MIGD值
    """
    time_points = sorted(map(int, runtime_populations.keys()))
    time_metric_values = []
    
    for time in time_points:
        populations = runtime_populations[time]
        last_env = list(populations.values())[-1]
        
        if 'POF' not in last_env or 'population' not in last_env:
            continue
            
        pof = np.array(last_env['POF'])
        pop_y = np.array([ind.F for ind in last_env['population']])
        value = calculate_IGD(pop_y, pof)
        time_metric_values.append(value)
    
    return np.mean(time_metric_values) if time_metric_values else 0.0

def calculate_MGD(runtime_populations):
    """计算平均世代距离(MGD)
    
    Args:
        runtime_populations: 运行时种群数据
        
    Returns:
        float: MGD值
    """
    time_points = sorted(map(int, runtime_populations.keys()))
    time_metric_values = []
    
    for time in time_points:
        populations = runtime_populations[time]
        last_env = list(populations.values())[-1]
        
        if 'POF' not in last_env or 'population' not in last_env:
            continue
            
        pof = np.array(last_env['POF'])
        pop_y = np.array([ind.F for ind in last_env['population']])
        value = calculate_IGD(pof, pop_y)
        time_metric_values.append(value)
    
    return np.mean(time_metric_values) if time_metric_values else 0.0

def calculate_MHV(runtime_populations):
    """计算平均超体积(MHV)
    
    Args:
        runtime_populations: 运行时种群数据
        
    Returns:
        float: MHV值
    """
    time_points = sorted(map(int, runtime_populations.keys()))
    time_metric_values = []
    
    for time in time_points:
        populations = runtime_populations[time]
        last_env = list(populations.values())[-1]
        
        if 'POF' not in last_env or 'population' not in last_env:
            continue
            
        pof = np.array(last_env['POF'])
        pop_y = np.array([ind.F for ind in last_env['population']])
        ref_point = pof.max(axis=0) + 0.5
        value = calculate_HV(pop_y, ref_point)
        time_metric_values.append(value)
    
    return np.mean(time_metric_values) if time_metric_values else 0.0