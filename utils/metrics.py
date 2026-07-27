import numpy as np


def calculate_IGD(pop_y, pf):
    """计算反向世代距离(IGD)
    
    Args:
        pop_y: 种群的目标值
        pf: 真实Pareto前沿
        
    Returns:
        float: IGD值
    """
    pop_y = np.asarray(pop_y, dtype=float)
    pf = np.asarray(pf, dtype=float)
    if pf.size == 0:
        return 0.0
    if pf.ndim != 2:
        raise ValueError("真实 Pareto 前沿必须是二维矩阵")
    if pop_y.size == 0:
        return float("inf")
    if pop_y.ndim != 2 or pop_y.shape[1] != pf.shape[1]:
        raise ValueError("种群目标矩阵与 Pareto 前沿的目标维度必须一致")

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
    pop_y = np.asarray(pop_y, dtype=float)
    ref_point = np.asarray(ref_point, dtype=float)
    if ref_point.shape != (2,):
        raise ValueError("当前超体积实现仅支持二维目标，参考点必须包含两个值")

    # 确保所有点都被参考点支配
    if pop_y.size == 0:
        return 0.0
    if pop_y.ndim != 2 or pop_y.shape[1] != 2:
        raise ValueError("当前超体积实现仅支持形状为 (n, 2) 的目标矩阵")
    mask = np.all(pop_y <= ref_point, axis=1)
    points = pop_y[mask]
    if len(points) == 0:
        return 0.0
    
    # 按第一个目标升序扫描；只有第二个目标继续改善的点才扩展超体积。
    # 这种写法会自然忽略重复点和被支配点。
    points = points[np.argsort(points[:, 0], kind="stable")]

    hv = 0.0
    current_y = ref_point[1]
    for current_x, candidate_y in points:
        if candidate_y < current_y:
            hv += (ref_point[0] - current_x) * (current_y - candidate_y)
            current_y = candidate_y
    
    return hv


def _iter_last_snapshots(runtime_populations):
    """按数值时间顺序返回每个环境中评估次数最大的快照。"""
    for time_key in sorted(runtime_populations, key=lambda key: int(key)):
        populations = runtime_populations[time_key]
        if not populations:
            continue
        last_key = max(populations, key=lambda key: int(key))
        yield populations[last_key]

def calculate_MIGD(runtime_populations):
    """计算平均反向世代距离(MIGD)
    
    Args:
        runtime_populations: 运行时种群数据
        
    Returns:
        float: MIGD值
    """
    time_metric_values = []
    
    for last_env in _iter_last_snapshots(runtime_populations):
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
    time_metric_values = []
    
    for last_env in _iter_last_snapshots(runtime_populations):
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
    time_metric_values = []
    
    for last_env in _iter_last_snapshots(runtime_populations):
        if 'POF' not in last_env or 'population' not in last_env:
            continue
            
        pof = np.array(last_env['POF'])
        pop_y = np.array([ind.F for ind in last_env['population']])
        ref_point = pof.max(axis=0) + 0.5
        value = calculate_HV(pop_y, ref_point)
        time_metric_values.append(value)
    
    return np.mean(time_metric_values) if time_metric_values else 0.0
