"""Runnable code-interface demonstration, not a published search algorithm."""
import numpy as np


def step(population, problem, scale: float = 0.05):
    if scale < 0:
        raise ValueError("scale 不能为负数")
    X = population.get_decision_matrix()
    noise = np.random.normal(0, scale, X.shape) * (problem.xu - problem.xl)
    return np.clip(X + noise, problem.xl, problem.xu)
