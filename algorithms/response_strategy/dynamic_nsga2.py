"""Shared utilities for D-NSGA-II response strategies."""

import numpy as np

from components.Population import Population
from utils.evolution_tools import crowd_selection, quick_non_dominate_sort


def validate_rate(name, value):
    value = float(value)
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in the interval (0, 1].")
    return value


def replacement_count(population_size, replacement_rate):
    if population_size <= 0:
        raise ValueError("population_size must be positive.")
    return max(
        1,
        min(population_size, int(round(population_size * replacement_rate))),
    )


def select_survivors(population, count):
    if count <= 0 or not population.individuals:
        return []
    quick_non_dominate_sort(population)
    selected = crowd_selection(population, min(count, population.n))
    return [individual.copy() for individual in selected.individuals]


def random_population(problem, count):
    population = Population(
        xl=problem.xl,
        xu=problem.xu,
        n_init=count,
    )
    population.update_objective_constrain(problem)
    return population


def finish_population(problem, survivors, newcomers):
    individuals = survivors + [
        individual.copy() for individual in newcomers.individuals
    ]
    population = Population(
        individuals=individuals,
        xl=problem.xl,
        xu=problem.xu,
    )
    if population.n != problem.solution_num:
        raise RuntimeError(
            "Dynamic response produced an invalid population size: "
            f"{population.n}, expected {problem.solution_num}."
        )
    quick_non_dominate_sort(population)
    return population


def polynomial_mutation(
    decisions,
    lower,
    upper,
    probability,
    distribution_index,
):
    decisions = np.atleast_2d(np.asarray(decisions, dtype=float)).copy()
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    if decisions.shape[1] != len(lower) or len(lower) != len(upper):
        raise ValueError("Mutation bounds do not match decision dimensions.")

    span = upper - lower
    mutable = span > 0.0
    decisions = np.clip(decisions, lower, upper)
    sites = np.random.random(decisions.shape) < probability
    sites &= mutable[None, :]

    mutable_indices = np.flatnonzero(mutable)
    if mutable_indices.size:
        for row in range(len(decisions)):
            if not np.any(sites[row]):
                sites[row, np.random.choice(mutable_indices)] = True

    random_values = np.random.random(decisions.shape)
    safe_span = np.where(mutable, span, 1.0)
    delta1 = (decisions - lower) / safe_span
    delta2 = (upper - decisions) / safe_span
    mutation_power = 1.0 / (distribution_index + 1.0)

    lower_side = sites & (random_values <= 0.5)
    if np.any(lower_side):
        value = (
            2.0 * random_values
            + (1.0 - 2.0 * random_values)
            * np.power(1.0 - delta1, distribution_index + 1.0)
        )
        delta = np.power(value, mutation_power) - 1.0
        decisions[lower_side] += (
            delta[lower_side]
            * np.broadcast_to(span, decisions.shape)[lower_side]
        )

    upper_side = sites & (random_values > 0.5)
    if np.any(upper_side):
        value = (
            2.0 * (1.0 - random_values)
            + 2.0
            * (random_values - 0.5)
            * np.power(1.0 - delta2, distribution_index + 1.0)
        )
        delta = 1.0 - np.power(value, mutation_power)
        decisions[upper_side] += (
            delta[upper_side]
            * np.broadcast_to(span, decisions.shape)[upper_side]
        )

    return np.clip(decisions, lower, upper)
