"""Independent, NumPy-only VARE response implementation.

Jiang et al., arXiv:2305.12752v2, equations (1)--(8), and the author
repository at 8bf41fe1ada20b1ed2ae143b0f38d059d2b0dfad were consulted.
No third-party source is included. See docs/algorithms/vare.md for the
Gaussian-prior VAR estimator and MOEA/D response-only compatibility limits.
"""

from __future__ import annotations

from itertools import combinations
import copy
import math

import numpy as np

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import quick_non_dominate_sort


class _ResponseStopped(Exception):
    """Cancellation; completed evaluations stay counted, state is not committed."""


def _checkpoint(algorithm):
    hook = getattr(algorithm, "control_process", None)
    if callable(hook) and not hook():
        raise _ResponseStopped


def _positive_integer(name, value):
    try:
        valid = not isinstance(value, bool) and np.isfinite(value) and int(value) == value and value >= 1
    except (TypeError, ValueError, OverflowError):
        valid = False
    if not valid:
        raise ValueError(f"{name} must be a positive integer.")
    return int(value)


def reference_directions(count, objectives, algorithm=None):
    """Deterministic simplex lattice, thinned by farthest-point sampling."""
    count = _positive_integer("count", count)
    objectives = _positive_integer("objectives", objectives)
    if count == 1:
        return np.full((1, objectives), 1.0 / objectives)
    if objectives == 1:
        return np.ones((count, 1))
    if objectives == 2:
        first = np.linspace(0.0, 1.0, count)
        return np.column_stack((first, 1.0 - first))
    divisions = 1
    while math.comb(divisions + objectives - 1, objectives - 1) < count:
        divisions += 1
    lattice = np.array([
        np.diff((-1, *bars, divisions + objectives - 1)) - 1
        for bars in combinations(range(divisions + objectives - 1), objectives - 1)
    ], dtype=float) / divisions
    chosen = []
    distance = np.full(len(lattice), np.inf)
    next_index = 0
    for _ in range(count):
        _checkpoint(algorithm)
        chosen.append(next_index)
        distance = np.minimum(distance, np.sum((lattice - lattice[next_index]) ** 2, axis=1))
        distance[chosen] = -1.0
        next_index = int(np.argmax(distance))
    return lattice[chosen]


def associate_reference(objectives, directions, violations=None, decisions=None, algorithm=None):
    """Closest angular representative per direction (duplicates are allowed).

    As in the author code, objectives are ideal-translated, not range-scaled.
    Feasibility-first filtering and deterministic zero-vector/tie handling
    extend the originally unconstrained association to FlexDMO problems.
    """
    values = np.asarray(objectives, dtype=float)
    weights = np.asarray(directions, dtype=float)
    if values.ndim != 2 or not len(values) or not np.all(np.isfinite(values)):
        raise ValueError("objectives must be a nonempty finite matrix.")
    if (weights.ndim != 2 or weights.shape[1] != values.shape[1]
            or not np.all(np.isfinite(weights)) or np.any(weights < 0)
            or np.any(np.sum(weights, axis=1) <= 0)):
        raise ValueError("Invalid reference directions.")
    violation = np.zeros(len(values)) if violations is None else np.asarray(violations, dtype=float)
    if (violation.shape != (len(values),) or not np.all(np.isfinite(violation))
            or np.any(violation < 0)):
        raise ValueError("Invalid constraint violations.")
    eligible = np.flatnonzero(violation <= 1e-12)
    if not len(eligible):
        eligible = np.flatnonzero(violation == violation.min())
    # Canonical ordering means a static optimizer can reorder its population
    # without silently replacing the reference-wise historical trajectories.
    keys = values if decisions is None else np.column_stack((values, decisions))
    eligible = eligible[np.lexsort(tuple(keys[eligible, j] for j in reversed(range(keys.shape[1]))))]
    translated = values[eligible] - values[eligible].min(axis=0)
    # Rescaling by one common factor prevents overflow without changing angles.
    translated /= max(float(np.max(np.abs(translated))), 1.0)
    lengths = np.linalg.norm(translated, axis=1)
    unit = translated / np.where(lengths > 0, lengths, 1.0)[:, None]
    weights = weights / np.linalg.norm(weights, axis=1)[:, None]
    cosine = unit @ weights.T
    cosine[lengths == 0] = 1.0
    result = []
    for column in range(len(weights)):
        _checkpoint(algorithm)
        ties = np.flatnonzero(np.isclose(cosine[:, column], cosine[:, column].max(), rtol=0, atol=1e-12))
        ties = ties[np.isclose(lengths[ties], lengths[ties].min(), rtol=0, atol=1e-12)]
        result.append(eligible[ties[column % len(ties)]])
    return np.asarray(result, dtype=int)


def fit_vector_autoregression(series, lag_order=5, regularization=1e-6):
    """Joint VAR with intercept; Gaussian slope prior (ridge posterior mode).

    All lagged components predict all current components, including cross-
    component terms. No independent per-coordinate AR fits are performed.
    Intercept is unpenalized. Zero regularization gives ordinary least squares.
    """
    values = np.asarray(series, dtype=float)
    lag = _positive_integer("lag_order", lag_order)
    if values.ndim != 2 or not values.shape[1] or len(values) <= lag or not np.all(np.isfinite(values)):
        raise ValueError("VAR requires a finite matrix with more observations than lags.")
    if not np.isfinite(regularization) or regularization < 0:
        raise ValueError("regularization must be finite and nonnegative.")
    design = np.array([values[t-lag:t][::-1].reshape(-1) for t in range(lag, len(values))])
    target = values[lag:]
    x_mean, y_mean = design.mean(axis=0), target.mean(axis=0)
    centered_x, centered_y = design - x_mean, target - y_mean
    if regularization:
        centered_x = np.vstack((centered_x, np.sqrt(regularization) * np.eye(design.shape[1])))
        centered_y = np.vstack((centered_y, np.zeros((design.shape[1], values.shape[1]))))
    slopes = np.linalg.lstsq(centered_x, centered_y, rcond=None)[0]
    intercept = y_mean - x_mean @ slopes
    coefficients = np.vstack((intercept, slopes))
    prediction = intercept + values[-lag:][::-1].reshape(-1) @ slopes
    residual = target - (intercept + design @ slopes)
    covariance = residual.T @ residual / len(residual)
    return prediction, coefficients, covariance


def pca_var_predict(history, lag_order=5, explained_variance=0.8, regularization=1e-6):
    """PCA on one direction's *temporal* decision series, then joint VAR."""
    values = np.asarray(history, dtype=float)
    lag = _positive_integer("lag_order", lag_order)
    if (values.ndim != 2 or not values.shape[1] or len(values) <= lag
            or not np.all(np.isfinite(values))):
        raise ValueError("Invalid temporal decision history.")
    if not np.isfinite(explained_variance) or not 0 < explained_variance <= 1:
        raise ValueError("explained_variance must be in (0, 1].")
    if not np.isfinite(regularization) or regularization < 0:
        raise ValueError("regularization must be finite and nonnegative.")
    mean = values.mean(axis=0)
    if np.all(values == values[0]):
        return values[-1].copy(), 0
    centered = values - mean
    _, singular, vectors = np.linalg.svd(centered, full_matrices=False)
    tolerance = np.finfo(float).eps * max(centered.shape) * (singular[0] if len(singular) else 0)
    rank = int(np.sum(singular > tolerance))
    if rank == 0:
        return values[-1].copy(), 0
    energy = (singular[:rank] / singular[0]) ** 2
    components = min(rank, int(np.searchsorted(np.cumsum(energy) / energy.sum(), explained_variance)) + 1)
    basis = vectors[:components].T
    predicted, _, _ = fit_vector_autoregression(centered @ basis, lag, regularization)
    reconstructed = mean + predicted @ basis.T
    if not np.all(np.isfinite(reconstructed)):
        raise np.linalg.LinAlgError("Nonfinite PCA/VAR forecast.")
    return reconstructed, components


def _beta_fraction(a, b, x):
    """Continued fraction for the regularized incomplete beta function."""
    tiny = 1e-300
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    d = 1.0 / (d if abs(d) > tiny else tiny)
    value = d
    for m in range(1, 201):
        for coefficient in (
            m * (b - m) * x / ((a + 2*m - 1) * (a + 2*m)),
            -(a + m) * (a + b + m) * x / ((a + 2*m) * (a + 2*m + 1)),
        ):
            d = 1.0 + coefficient * d
            c = 1.0 + coefficient / c
            d = 1.0 / (d if abs(d) > tiny else tiny)
            c = c if abs(c) > tiny else tiny
            change = c * d
            value *= change
        if abs(change - 1.0) < 1e-13:
            return value
    raise ArithmeticError("Student-t beta fraction did not converge.")


def _student_t_right_tail(statistic, degrees):
    x = degrees / (degrees + statistic * statistic)
    if x <= 0:
        return 0.0
    if x >= 1:
        return 0.5
    a, b = degrees / 2.0, 0.5
    factor = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                      + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1) / (a + b + 2):
        beta = factor * _beta_fraction(a, b, x) / a
    else:
        beta = 1.0 - factor * _beta_fraction(b, a, 1.0 - x) / b
    return 0.5 * beta


def significant_decision_change(difference):
    """Right-tailed one-sample Student t test against zero, alpha=0.05.

    Flatten absolute differences as in the paper/source's proposed test.
    A singleton cannot support a t test; positive zero-variance samples
    are treated as the limiting significant case, all-zero samples are not.
    """
    values = np.abs(np.asarray(difference, dtype=float)).reshape(-1)
    if not np.all(np.isfinite(values)):
        raise ValueError("Decision differences must be finite.")
    if len(values) < 2 or not np.any(values):
        return False
    values = values / values.max()
    deviation = float(np.std(values, ddof=1))
    if deviation == 0:
        return True
    statistic = float(values.mean()) * math.sqrt(len(values)) / deviation
    return _student_t_right_tail(statistic, len(values) - 1) < 0.05


def environment_mutation_index(old_decisions, reassociated_decisions, old_objectives, reevaluated_objectives):
    """Paper equations (4)--(7), with epsilon=1e-6 and eta in [2, 20]."""
    old_x, new_x = np.asarray(old_decisions, dtype=float), np.asarray(reassociated_decisions, dtype=float)
    old_f, new_f = np.asarray(old_objectives, dtype=float), np.asarray(reevaluated_objectives, dtype=float)
    if (old_x.shape != new_x.shape or old_f.shape != new_f.shape
            or not old_x.size or not old_f.size
            or not all(np.all(np.isfinite(v)) for v in (old_x, new_x, old_f, new_f))):
        raise ValueError("EAH requires matching finite old/new decision and objective matrices.")
    delta_f = float(np.mean(np.abs(new_f - old_f) / (np.abs(old_f) + 1e-6)))
    delta_x = float(np.mean(np.abs(new_x - old_x) / (np.abs(old_x) + 1e-6)))
    significant = significant_decision_change(new_x - old_x)
    eta = 20.0 * max(math.exp(-(delta_f + delta_x)), 0.1) if significant else 20.0
    return eta, delta_f, delta_x, significant


def repair_bounds(decisions, lower, upper):
    """Author's upper reflection, lower reflection, then final clipping."""
    values = np.asarray(decisions, dtype=float).copy()
    lower, upper = np.asarray(lower, dtype=float), np.asarray(upper, dtype=float)
    values = np.where(np.isnan(values), lower + (upper - lower) / 2, values)
    values = np.where(np.isposinf(values), upper, values)
    values = np.where(np.isneginf(values), lower, values)
    values = np.where(values > upper, 2 * upper - values, values)
    values = np.where(values < lower, 2 * lower - values, values)
    return np.clip(values, lower, upper)


def adaptive_polynomial_mutation(decisions, lower, upper, eta, rng):
    """Bound-aware polynomial mutation, per-variable probability 1/D.

    No forced mutation: an unchanged row is possible in the original EAH.
    Zero-width coordinates are never mutated and never divide by zero.
    """
    values = np.clip(np.asarray(decisions, dtype=float), lower, upper)
    span = np.asarray(upper, dtype=float) - np.asarray(lower, dtype=float)
    safe_span = np.where(span > 0, span, 1.0)
    sites = (rng.random(values.shape) < 1.0 / values.shape[1]) & (span > 0)
    u = rng.random(values.shape)
    power = 1.0 / (eta + 1.0)
    distance_lower = (values - lower) / safe_span
    distance_upper = (upper - values) / safe_span
    left = (2*u + (1-2*u) * (1-distance_lower) ** (eta+1))
    right = (2*(1-u) + 2*(u-0.5) * (1-distance_upper) ** (eta+1))
    delta = np.where(u <= 0.5, np.maximum(left, 0) ** power - 1,
                     1 - np.maximum(right, 0) ** power)
    return np.clip(values + np.where(sites, delta * span, 0), lower, upper)


def adaptive_prediction_probability(attempts, successes):
    """Equation (8): success *rates*, not counts, within the lag window."""
    attempted = np.asarray(attempts, dtype=bool)
    survived = np.asarray(successes, dtype=bool)
    if attempted.ndim != 2 or attempted.shape != survived.shape or not len(attempted):
        raise ValueError("Matching nonempty attempt/success windows are required.")
    prediction_rate = np.sum(survived & attempted, axis=0) / (1e-6 + attempted.sum(axis=0))
    mutation_rate = np.sum(survived & ~attempted, axis=0) / (1e-6 + (~attempted).sum(axis=0))
    total = prediction_rate + mutation_rate
    probability = np.divide(prediction_rate, total, out=np.full(total.shape, 0.5), where=total > 0)
    return np.clip(probability, 0.1, 0.9)


class VARE(ResponseStrategy):
    """Reference-wise PCA/VAR + environment-aware adaptive hypermutation."""

    def __init__(self, lag_order=5, explained_variance=0.8, regularization=1e-6, history_length=100):
        super().__init__()
        self.lag_order = _positive_integer("lag_order", lag_order)
        self.history_length = _positive_integer("history_length", history_length)
        self.explained_variance = float(explained_variance)
        self.regularization = float(regularization)
        if self.history_length < 4 * self.lag_order:
            raise ValueError("history_length must be at least 4 * lag_order (author's VAR warmup).")
        if not np.isfinite(self.explained_variance) or not 0 < self.explained_variance <= 1:
            raise ValueError("explained_variance must be in (0, 1].")
        if not np.isfinite(self.regularization) or self.regularization < 0:
            raise ValueError("regularization must be finite and nonnegative.")
        self._problem = None
        self._signature = None
        self._last_time = None
        self._last_evaluations = None
        self._rng = None
        self._history = []
        self._attempts = []
        self._successes = []
        self._probability = np.empty(0)
        self.last_diagnostics = {}

    def _reset(self, problem, signature, algorithm, objectives):
        seed = getattr(algorithm, "seed", 0)
        self._rng = np.random.default_rng(seed)
        self._problem, self._signature = problem, signature
        self._history, self._attempts, self._successes = [], [], []
        self._probability = np.full(problem.solution_num, 0.5)
        self._directions = reference_directions(problem.solution_num, objectives, algorithm)
        self._last_time = None
        self._last_evaluations = None

    @staticmethod
    def _evaluate(decisions, problem, algorithm):
        individuals = []
        # Bound the number of evaluations consumed after the last stop check.
        # Never call detection/need_count=False: counted evaluation does not
        # advance Problem.t even when the pending change flag is already set.
        for start in range(0, len(decisions), 64):
            _checkpoint(algorithm)
            batch = Population(X=decisions[start:start + 64], xl=problem.xl, xu=problem.xu)
            batch.update_objective_constrain(problem)
            if (not np.all(np.isfinite(batch.get_objective_matrix()))
                    or not np.all(np.isfinite(batch.get_constrain_matrix()))):
                raise ValueError("VARE requires finite objective and constraint evaluations.")
            individuals.extend(batch.individuals)
        return Population(individuals=individuals, xl=problem.xl, xu=problem.xu)

    def response(self, population, problem, algorithm):
        state = self.__dict__.copy()
        rng_state = copy.deepcopy(self._rng.bit_generator.state) if self._rng is not None else None
        try:
            _checkpoint(algorithm)
            result = self._respond(population, problem, algorithm)
            self._last_evaluations = getattr(problem, "evaluate_time", None)
            return result
        except Exception as error:
            # Lists/arrays below are replaced, not mutated, until completion.
            # Roll back temporal/adaptive state and RNG, not consumed budget.
            self.__dict__.clear()
            self.__dict__.update(state)
            if rng_state is not None:
                self._rng.bit_generator.state = rng_state
            if isinstance(error, _ResponseStopped):
                return population.copy()
            raise

    def _respond(self, population, problem, algorithm):
        lower, upper = np.asarray(problem.xl, dtype=float), np.asarray(problem.xu, dtype=float)
        dimensions = _positive_integer("decision_num", problem.decision_num)
        count = _positive_integer("solution_num", problem.solution_num)
        if (lower.shape != (dimensions,) or upper.shape != lower.shape
                or not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper))
                or np.any(lower > upper)):
            raise ValueError("VARE requires finite ordered decision bounds.")
        objectives = getattr(problem, "n_obj", getattr(problem, "objective_num", None))
        if objectives is None and population.n and population[0].F is not None:
            objectives = len(population[0].F)
        objectives = _positive_integer("objective count", objectives)
        signature = (count, dimensions, objectives, tuple(lower), tuple(upper))
        time = getattr(problem, "t", 0)
        evaluations = getattr(problem, "evaluate_time", None)
        if (self._problem is not problem or self._signature != signature
                or (self._last_time is not None and time < self._last_time)
                or (evaluations is not None and self._last_evaluations is not None
                    and evaluations < self._last_evaluations)):
            self._reset(problem, signature, algorithm, objectives)
        if population.n == 0:
            self._history, self._attempts, self._successes = [], [], []
            self._probability = np.full(count, 0.5)
            result = self._evaluate(self._rng.uniform(lower, upper, (count, dimensions)), problem, algorithm)
            _checkpoint(algorithm)
            quick_non_dominate_sort(result)
            self.last_diagnostics = {"stage": "empty", "history_size": 0}
            self._last_time = time
            return result

        raw_x = population.get_decision_matrix()
        if raw_x.shape != (population.n, dimensions):
            raise ValueError("Population decision dimension does not match the problem.")
        clean_x = repair_bounds(raw_x, lower, upper)
        # An unevaluated/repaired input has no reliable old-environment F/G.
        # Evaluate it now and use that baseline; do not invent old objectives.
        old = population
        baseline_known = (np.array_equal(raw_x, clean_x)
                          and all(ind.F is not None for ind in population))
        if not baseline_known:
            old = self._evaluate(clean_x, problem, algorithm)
        old_f = old.get_objective_matrix()
        if old_f.shape != (old.n, objectives):
            raise ValueError("Population objective dimension does not match the problem.")
        indices = associate_reference(old_f, self._directions, old.get_constraint_violation_vector(), clean_x, algorithm)
        archived_x, archived_f = clean_x[indices].copy(), old_f[indices].copy()
        if self._last_time == time:
            # A second call/probe in the same environment is not another
            # temporal observation and must not update adaptive success rates.
            result = self._evaluate(archived_x, problem, algorithm)
            _checkpoint(algorithm)
            quick_non_dominate_sort(result)
            self.last_diagnostics = {"stage": "same_environment", "history_size": len(self._history)}
            return result
        self._history = (self._history + [archived_x])[-self.history_length:]
        reevaluated = self._evaluate(archived_x, problem, algorithm)
        partners = associate_reference(reevaluated.get_objective_matrix(), self._directions,
                                       reevaluated.get_constraint_violation_vector(), archived_x, algorithm)
        mutation_parents = archived_x[partners]
        eta, delta_f, delta_x, significant = environment_mutation_index(
            archived_x, mutation_parents, archived_f, reevaluated.get_objective_matrix())
        use_prediction = self._rng.random(count) < self._probability
        if len(self._history) == 1:
            use_prediction[:] = False
        proposed = adaptive_polynomial_mutation(mutation_parents, lower, upper, eta, self._rng)
        modes = np.full(count, "eah", dtype="<U8")
        components = np.zeros(count, dtype=int)
        # Stack once, not once per direction (which would copy O(H*N*D)
        # values N times for a large population/high-dimensional problem).
        temporal_decisions = np.asarray(self._history)
        for i in np.flatnonzero(use_prediction):
            _checkpoint(algorithm)
            trajectory = temporal_decisions[:, i, :]
            if len(trajectory) >= 4 * self.lag_order:
                try:
                    proposed[i], components[i] = pca_var_predict(
                        trajectory, self.lag_order, self.explained_variance, self.regularization)
                    modes[i] = "pca_var"
                    continue
                except np.linalg.LinAlgError:
                    # Isolate numerical failure to this direction, not all N.
                    pass
            displacement = trajectory[-1] - trajectory[-2]
            proposed[i] = trajectory[-1] + displacement + self._rng.normal() * (
                np.linalg.norm(displacement) / (2 * math.sqrt(dimensions)))
            modes[i] = "linear"
        offspring = self._evaluate(repair_bounds(proposed, lower, upper), problem, algorithm)
        _checkpoint(algorithm)

        # Response-only MOEA/D comparison, independent of optimizer internals.
        # Never carry a stale ideal point or stale parent constraint flags.
        parent_f, child_f = reevaluated.get_objective_matrix(), offspring.get_objective_matrix()
        ideal = np.minimum(parent_f.min(axis=0), child_f.min(axis=0))
        parent_score = np.max(np.abs(parent_f - ideal) * self._directions, axis=1)
        child_score = np.max(np.abs(child_f - ideal) * self._directions, axis=1)
        parent_cv = reevaluated.get_constraint_violation_vector()
        child_cv = offspring.get_constraint_violation_vector()
        parent_feasible, child_feasible = parent_cv <= 1e-12, child_cv <= 1e-12
        survived = ((child_feasible & ~parent_feasible)
                    | (~child_feasible & ~parent_feasible & (child_cv < parent_cv))
                    | (child_feasible & parent_feasible & (child_score < parent_score)))
        result = Population(individuals=[
            (offspring[i] if survived[i] else reevaluated[i]).copy() for i in range(count)
        ], xl=lower, xu=upper)
        self._attempts = (self._attempts + [use_prediction.copy()])[-self.lag_order:]
        self._successes = (self._successes + [survived.copy()])[-self.lag_order:]
        if len(self._attempts) == self.lag_order:
            self._probability = adaptive_prediction_probability(self._attempts, self._successes)
        quick_non_dominate_sort(result)
        _checkpoint(algorithm)
        self.last_diagnostics = {
            "stage": "response", "history_size": len(self._history),
            "modes": modes.tolist(), "pca_components": components.tolist(),
            "prediction_probability": self._probability.tolist(),
            "predicted": use_prediction.tolist(), "survived": survived.tolist(),
            "eta": eta, "delta_f": delta_f, "delta_x": delta_x,
            "significant_decision_change": significant, "old_baseline_known": baseline_known,
        }
        self._last_time = time
        return result
