"""ADPS response adaptation of the public 2024 arXiv:2410.05787v1.

Dual-domain online clustering, causal second derivatives with sine-change
feedback, adaptive domain allocation, and counted Euclidean inverse search.
This is not a claim of exact reproduction of the later TEVC journal article.
See docs/algorithms/adps.md for explicit resolutions of v1 ambiguities.
"""

from __future__ import annotations

import numpy as np

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import quick_non_dominate_sort


class _ResponseStopped(Exception):
    """Internal cancellation; already consumed evaluations remain counted."""


def _checkpoint(algorithm):
    hook = getattr(algorithm, "control_process", None)
    if callable(hook) and not hook():
        raise _ResponseStopped


def online_centers(values, objectives, previous=None, passes=3, algorithm=None):
    """Algorithm 2: sequential means, M extrema plus the population mean.

    Keep M+1 slots even for singleton/duplicate data. Empty slots retain
    their anchors. Translated historical anchors preserve temporal labels.
    """
    values = np.asarray(values, dtype=float)
    objectives = np.asarray(objectives, dtype=float)
    if values.ndim != 2 or not len(values):
        raise ValueError("Clustering requires a nonempty matrix.")
    if objectives.ndim != 2 or len(objectives) != len(values):
        raise ValueError("Objectives must correspond to the clustered rows.")
    if not np.all(np.isfinite(values)) or not np.all(np.isfinite(objectives)):
        raise ValueError("Clustering data must be finite.")
    if int(passes) != passes or passes < 1:
        raise ValueError("passes must be a positive integer.")
    anchors = np.vstack((
        np.mean(values, axis=0),
        values[np.argmin(objectives, axis=0)],
    ))
    if previous is not None:
        previous = np.asarray(previous, dtype=float)
        if previous.shape != anchors.shape:
            raise ValueError("Historical centers have incompatible dimensions.")
        anchors = previous + np.mean(values, axis=0) - np.mean(previous, axis=0)
    centers = anchors.copy()
    for _ in range(int(passes)):
        _checkpoint(algorithm)
        counts = np.zeros(len(centers), dtype=int)
        for index, point in enumerate(values):
            if index % 64 == 0:
                _checkpoint(algorithm)
            label = np.argmin(np.linalg.norm(centers - point, axis=1))
            counts[label] += 1
            centers[label] += (point - centers[label]) / counts[label]
        labels = np.argmin(
            np.linalg.norm(values[:, None, :] - centers[None, :, :], axis=2),
            axis=1,
        )
        # Report actual current-cluster means (Eq. 6), not pseudocount means.
        for label in range(len(centers)):
            members = values[labels == label]
            if len(members):
                centers[label] = np.mean(members, axis=0)
    labels = np.argmin(
        np.linalg.norm(values[:, None, :] - centers[None, :, :], axis=2),
        axis=1,
    )
    return centers, labels


def derivative_displacement(center_history):
    """Causal Eqs. 7--9; return per-cluster shift and reversal flags.

    Three centers suffice for acceleration. Five suffice for the three
    successive accelerations in Eq. 8; no future environment is consulted.
    """
    history = np.asarray(center_history, dtype=float)
    if history.ndim != 3 or not len(history):
        raise ValueError("Expected nonempty (time, cluster, dimension) history.")
    if not np.all(np.isfinite(history)):
        raise ValueError("Center history must be finite.")
    velocity = np.zeros_like(history[-1])
    reversal = np.zeros(history.shape[1], dtype=bool)
    if len(history) >= 2:
        velocity = history[-1] - history[-2]
    if len(history) < 3:
        return velocity, reversal
    accelerations = history[2:] - 2.0 * history[1:-1] + history[:-2]
    acceleration = accelerations[-1].copy()
    if len(accelerations) >= 3:
        newest, middle, oldest = np.sin(accelerations[-3:][::-1])
        score = np.sum((newest - middle) * (middle - oldest), axis=1)
        reversal = score < 0.0
        # v1 specifies declining weights summing to one, but no values.
        smoothed = np.einsum(
            "t,tkd->kd", np.array([0.5, 0.3, 0.2]), accelerations[-3:][::-1]
        )
        acceleration[reversal] = smoothed[reversal]
    return velocity + acceleration, reversal


def prediction_noise(current, previous, rng, scale=1.0, algorithm=None):
    """Eq. 10 interpreted as a bound on isotropic perturbation magnitude."""
    current = np.asarray(current, dtype=float)
    previous = np.asarray(previous, dtype=float)
    distances = np.empty(len(current), dtype=float)
    for start in range(0, len(current), 64):
        _checkpoint(algorithm)
        distances[start:start + 64] = np.min(np.linalg.norm(
            current[start:start + 64, None, :] - previous[None, :, :], axis=2
        ), axis=1)
    maximum = float(np.max(distances))
    if maximum <= 1e-12 or scale == 0:
        return np.zeros_like(current)
    direction = rng.normal(size=current.shape)
    norms = np.linalg.norm(direction, axis=1, keepdims=True)
    direction /= np.maximum(norms, 1e-12)
    magnitude = scale * rng.uniform(1e-12, 1.0, len(current)) * distances / maximum
    return direction * magnitude[:, None]


def _prefer(candidate_cv, candidate_distance, current_cv, current_distance):
    """Feasibility first; Euclidean distance only among feasible points."""
    feasible = candidate_cv <= 1e-12
    current_feasible = current_cv <= 1e-12
    return (
        (feasible and not current_feasible)
        or (not feasible and not current_feasible and candidate_cv < current_cv)
        or (feasible and current_feasible and candidate_distance < current_distance)
    )


class ADPS(ResponseStrategy):
    """Optimizer-independent, NumPy-only ADPS response (2024 preprint)."""

    def __init__(self, weight_step=0.02, cluster_passes=3,
                 inverse_iterations=3, inverse_step=0.2,
                 perturbation_scale=1.0, evaluation_batch_size=128):
        super().__init__()
        self.weight_step = float(weight_step)
        self.inverse_step = float(inverse_step)
        self.perturbation_scale = float(perturbation_scale)
        for name, value, minimum in (
            ("cluster_passes", cluster_passes, 1),
            ("inverse_iterations", inverse_iterations, 1),
            ("evaluation_batch_size", evaluation_batch_size, 1),
        ):
            if not np.isfinite(value) or int(value) != value or value < minimum:
                raise ValueError(f"{name} must be an integer >= {minimum}.")
            setattr(self, name, int(value))
        for name in ("weight_step", "inverse_step", "perturbation_scale"):
            value = getattr(self, name)
            if not np.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"{name} must be finite and in [0, 1].")
        if self.inverse_step == 0:
            raise ValueError("inverse_step must be positive.")
        self.decision_weight = 0.5
        self.objective_weight = 0.5
        self._history = []
        self._origins = None
        self._context = None
        self._last_t = None
        self._last_evaluations = -1
        self._response_count = 0
        self.last_domain_counts = (0.0, 0.0)
        self.last_allocation = (0, 0)
        self.last_inverse_evaluations = 0
        self.last_inverse_iterations = 0
        self.last_budget_limited = False

    def _evaluate(self, decisions, problem, algorithm):
        """Count every evaluated row and never use detector semantics."""
        individuals = []
        for start in range(0, len(decisions), self.evaluation_batch_size):
            _checkpoint(algorithm)
            batch = Population(X=decisions[start:start + self.evaluation_batch_size],
                               xl=problem.xl, xu=problem.xu)
            # Default need_count=True is essential: False can advance t.
            batch.update_objective_constrain(problem)
            if not np.all(np.isfinite(batch.get_objective_matrix())):
                raise ValueError("ADPS requires finite objective evaluations.")
            if not np.all(np.isfinite(batch.get_constrain_matrix())):
                raise ValueError("ADPS requires finite constraint evaluations.")
            individuals.extend(batch.individuals)
        return Population(individuals=individuals, xl=problem.xl, xu=problem.xu)

    def _domain_counts(self, population, problem, algorithm):
        if self._origins is None:
            return 0.0, 0.0
        seeds, domains = self._origins
        if not np.any(domains == 0) or not np.any(domains == 1):
            return 0.0, 0.0
        span = np.asarray(problem.xu) - np.asarray(problem.xl)
        span = np.where(span > 0, span, 1.0)
        counts = np.zeros(2)
        for individual in population:
            _checkpoint(algorithm)
            if individual.rank != 1:
                continue
            distances = np.linalg.norm((seeds - individual.X) / span, axis=1)
            nearest = np.array([np.min(distances[domains == domain])
                                for domain in (0, 1)])
            if np.isclose(nearest[0], nearest[1], rtol=1e-10, atol=1e-12):
                counts += 0.5  # Duplicated seeds must not bias attribution.
            else:
                counts[np.argmin(nearest)] += 1.0
        return tuple(counts)

    def _inverse_map(self, targets, pool, problem, algorithm, iterations=None):
        """Bounded coordinate pattern search for Eq. 5, with counted trials."""
        F = pool.get_objective_matrix()
        cv = pool.get_constraint_violation_vector()
        selected = []
        for target in targets:
            _checkpoint(algorithm)
            distances = np.linalg.norm(F - target, axis=1)
            feasible = cv <= 1e-12
            if np.any(feasible):
                index = np.argmin(np.where(feasible, distances, np.inf))
            else:
                index = np.argmin(cv)
            selected.append(pool[index].copy())
        best = Population(individuals=selected, xl=problem.xl, xu=problem.xu)
        steps = np.tile(self.inverse_step * (problem.xu - problem.xl),
                        (len(targets), 1))
        used = 0
        iterations = self.inverse_iterations if iterations is None else iterations
        for iteration in range(iterations):
            _checkpoint(algorithm)
            column = iteration % problem.decision_num
            if problem.xu[column] == problem.xl[column]:
                continue
            current = best.get_decision_matrix()
            minus, plus = current.copy(), current.copy()
            minus[:, column] -= steps[:, column]
            plus[:, column] += steps[:, column]
            trials = self._evaluate(np.clip(np.vstack((minus, plus)),
                                           problem.xl, problem.xu), problem, algorithm)
            used += trials.n
            improved = np.zeros(len(targets), dtype=bool)
            for index, target in enumerate(targets):
                for trial_index in (index, index + len(targets)):
                    candidate, incumbent = trials[trial_index], best[index]
                    if _prefer(candidate.constraint_violation,
                               np.linalg.norm(candidate.F - target),
                               incumbent.constraint_violation,
                               np.linalg.norm(incumbent.F - target)):
                        best.individuals[index] = candidate.copy()
                        improved[index] = True
            steps[~improved, column] *= 0.5
        return best, used

    @staticmethod
    def _mapping_budget(problem):
        """Reserve the N-row base evaluation plus one static N-row generation.

        This is a response-local cap, NOT a strict global FE budget. Static
        generations may cross boundaries, and termination is environment-based.
        """
        period = int(problem.change_each_evaluations)
        if period <= 0:
            raise ValueError("change_each_evaluations must be positive.")
        elapsed = max(0, int(problem.evaluate_time - problem.initial_convergence))
        next_boundary = problem.initial_convergence + (elapsed // period + 1) * period
        remaining = next_boundary - problem.evaluate_time
        return max(0, int(remaining - 2 * problem.solution_num))

    def response(self, population, problem, algorithm):
        try:
            _checkpoint(algorithm)
            return self._respond(population, problem, algorithm)
        except _ResponseStopped:
            # Optimizers check the same stop hook on their next iteration.
            # Do not publish partial history or return unevaluated individuals.
            return population.copy()

    def _respond(self, population, problem, algorithm):
        lower, upper = np.asarray(problem.xl), np.asarray(problem.xu)
        if (lower.shape != (problem.decision_num,)
                or upper.shape != lower.shape
                or not np.all(np.isfinite(lower))
                or not np.all(np.isfinite(upper)) or np.any(lower > upper)):
            raise ValueError("ADPS requires finite, ordered decision bounds.")
        context = (id(problem), problem.decision_num, problem.n_obj,
                   problem.solution_num, tuple(lower), tuple(upper))
        reset = (context != self._context
                 or problem.t < (self._last_t if self._last_t is not None else problem.t)
                 or problem.evaluate_time < self._last_evaluations)
        history = [] if reset else list(self._history)
        weights = np.array([0.5, 0.5]) if reset else np.array(
            [self.decision_weight, self.objective_weight])
        seed = getattr(algorithm, "seed", None)
        count = 0 if reset else self._response_count
        rng = np.random.default_rng(None if seed is None else int(seed) + count)
        size = problem.solution_num
        archive = population.copy()
        counts = (0.0, 0.0)
        allocation = (size, 0)
        inverse_used = 0
        inverse_iterations = 0
        budget_limited = False
        if archive.n:
            # Preserve historical F/G BEFORE any new-environment evaluation.
            if any(ind.F is None for ind in archive):
                raise ValueError("Nonempty ADPS input must already be evaluated.")
            quick_non_dominate_sort(archive)
            if not reset and problem.t != self._last_t:
                counts = self._domain_counts(archive, problem, algorithm)
                if self._origins is not None and sum(counts) > 0:
                    weights[1 if counts[1] > counts[0] else 0] += self.weight_step
                    weights /= np.sum(weights)
            pareto = [ind for ind in archive if ind.rank == 1]
            X = np.asarray([ind.X for ind in pareto], dtype=float)
            F = np.asarray([ind.F for ind in pareto], dtype=float)
            prior = history[-1] if history else None
            # Repeat calls in one environment replace, not invent, a time step.
            if not reset and problem.t == self._last_t and history:
                history = history[:-1]
                prior = history[-1] if history else None
            Cx, labels_x = online_centers(X, F, None if prior is None else prior[2],
                                         self.cluster_passes, algorithm)
            Cf, labels_f = online_centers(F, F, None if prior is None else prior[3],
                                         self.cluster_passes, algorithm)
            history = (history + [(X.copy(), F.copy(), Cx, Cf)])[-5:]
        mapping_budget = self._mapping_budget(problem)
        # Without even one +/- trial, do not pretend a nearest-pool lookup is
        # the objective-domain prediction mechanism. Fall back transparently.
        budget_fallback = len(history) >= 3 and mapping_budget < 2
        if len(history) < 3 or not archive.n or budget_fallback:
            budget_limited = budget_fallback
            base = archive.get_decision_matrix() if archive.n else None
            random_count = min(size, max(1, int(np.floor(0.1 * size + 0.5))))
            decisions = rng.uniform(lower, upper, size=(size, problem.decision_num))
            if base is not None:
                indices = rng.choice(len(base), size=size - random_count,
                                     replace=len(base) < size - random_count)
                decisions[:size - random_count] = np.clip(base[indices], lower, upper)
            result = self._evaluate(decisions, problem, algorithm)
            origins = None
            if not archive.n:
                history = []
        else:
            _checkpoint(algorithm)
            shift_x, _ = derivative_displacement([snapshot[2] for snapshot in history])
            shift_f, _ = derivative_displacement([snapshot[3] for snapshot in history])
            predicted_x = np.clip(X + shift_x[labels_x] + prediction_noise(
                X, history[-2][0], rng, self.perturbation_scale, algorithm), lower, upper)
            predicted_f = F + shift_f[labels_f] + prediction_noise(
                F, history[-2][1], rng, self.perturbation_scale, algorithm)
            indices = rng.choice(len(X), size=size, replace=len(X) < size)
            pool = self._evaluate(predicted_x[indices], problem, algorithm)
            decision_count = int(np.floor(size * weights[0] + 0.5))
            if size >= 2:
                decision_count = int(np.clip(decision_count, 1, size - 1))
            else:
                decision_count = int(weights[0] >= weights[1])
            objective_count = size - decision_count
            if objective_count:
                requested = objective_count
                objective_count = min(objective_count, mapping_budget // 2)
                decision_count = size - objective_count
                inverse_iterations = min(self.inverse_iterations,
                                         mapping_budget // (2 * objective_count))
                budget_limited = (objective_count != requested
                                  or inverse_iterations < self.inverse_iterations)
            selected = rng.choice(size, size=decision_count, replace=False)
            individuals = [pool[index].copy() for index in selected]
            if objective_count:
                targets = predicted_f[rng.choice(len(F), size=objective_count,
                                                 replace=len(F) < objective_count)]
                mapped, inverse_used = self._inverse_map(
                    targets, pool, problem, algorithm, iterations=inverse_iterations)
                individuals.extend(ind.copy() for ind in mapped)
            result = Population(individuals=individuals, xl=lower, xu=upper)
            allocation = (decision_count, objective_count)
            origins = (result.get_decision_matrix().copy(),
                       np.concatenate((np.zeros(decision_count, dtype=int),
                                       np.ones(objective_count, dtype=int))))
        _checkpoint(algorithm)
        quick_non_dominate_sort(result)
        # Commit prediction/adaptation state only after successful completion.
        self._context, self._last_t = context, problem.t
        self._last_evaluations = problem.evaluate_time
        self._response_count = count + 1
        self._history, self._origins = history, origins
        self.decision_weight, self.objective_weight = map(float, weights)
        self.last_domain_counts = counts
        self.last_allocation = allocation
        self.last_inverse_evaluations = inverse_used
        self.last_inverse_iterations = inverse_iterations
        self.last_budget_limited = budget_limited
        return result
