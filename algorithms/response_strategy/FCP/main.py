"""FCP response, independently implemented from the released execution path.

Reference: Gong et al., TEVC (2025), doi:10.1109/TEVC.2025.3551399.
Source audit: zoujuan1/Q-Gong-FCP, commit 4e1f62fc389c5049d2b659d6e4e10ad5cd24cc26.
See docs/algorithms/fcp.md for source quirks and optimizer/repair differences.
No MATLAB sources or third-party clustering implementations are bundled.
"""

from __future__ import annotations

import numpy as np

from algorithms.response_strategy.ResponseStrategy import ResponseStrategy
from components.Population import Population
from utils.evolution_tools import crowding_distance, fast_non_dominated_sort


_FEASIBILITY_TOLERANCE = 1e-12


def _integer(name, value, minimum=1):
    try:
        number = float(value)
        if isinstance(value, (bool, np.bool_)) or not np.isfinite(number):
            raise ValueError
        integer = int(value)
        if integer != number or integer < minimum:
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} must be a finite integer >= {minimum}.") from None
    return integer


def _real(name, value, minimum=0.0, maximum=None):
    try:
        number = float(value)
        if isinstance(value, (bool, np.bool_)) or not np.isfinite(number):
            raise ValueError
        if number < minimum or (maximum is not None and number > maximum):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{name} is outside its finite parameter domain.") from None
    return number


def _matrix(name, values, columns=None):
    values = np.asarray(values, dtype=float)
    if (values.ndim != 2 or (columns is not None and values.shape[1] != columns)
            or not np.all(np.isfinite(values))):
        raise ValueError(f"{name} must be a finite two-dimensional matrix.")
    return values


def _bounds(lower, upper):
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    if (lower.ndim != 1 or upper.shape != lower.shape or not len(lower)
            or not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper))
            or np.any(lower > upper)):
        raise ValueError("Bounds must be finite, ordered decision vectors.")
    with np.errstate(over="ignore"):
        span = upper - lower
    if not np.all(np.isfinite(span)):
        raise ValueError("Bound spans must be representable as finite floats.")
    return lower, upper, span


def modify_objectives(objectives, constraints=None):
    """Actual ModifyObj.m penalty: its pre-normalization Y term is zero.

    CV is the mean of per-constraint positive violations normalized by their
    column maxima. With no feasible rows, every objective becomes that CV.
    Constant objectives normalize to ONE, as in the released code.
    """
    objectives = _matrix("objectives", objectives)
    n, m = objectives.shape
    if not m:
        raise ValueError("At least one objective is required.")
    if constraints is None:
        constraints = np.empty((n, 0))
    constraints = _matrix("constraints", constraints)
    if len(constraints) != n:
        raise ValueError("Objectives and constraints must have the same row count.")
    if not n:
        return objectives.copy()
    positive = np.maximum(constraints, 0.0)
    cv = np.zeros(n)
    if constraints.shape[1]:
        maxima = positive.max(axis=0)
        cv = np.mean(positive / np.where(maxima > 0.0, maxima, 1.0), axis=1)
    # Sum-based tolerance matches FlexDMO's feasible/constraint-domination rule.
    with np.errstate(over="ignore"):
        total = positive.sum(axis=1)
    if not np.all(np.isfinite(total)):
        raise ValueError("Total constraint violation overflowed.")
    feasible_ratio = np.mean(total <= _FEASIBILITY_TOLERANCE)
    if feasible_ratio == 0.0:
        return np.broadcast_to(cv[:, None], objectives.shape).copy()
    # Scaling first avoids overflow in finite but extreme objective ranges.
    scale = np.maximum(np.max(np.abs(objectives), axis=0), 1.0)
    scaled = objectives / scale
    span = np.ptp(scaled, axis=0)
    normalized = np.ones_like(objectives)
    varying = span > 0.0
    normalized[:, varying] = (
        (scaled[:, varying] - scaled[:, varying].min(axis=0)) / span[varying]
    )
    return np.hypot(normalized, cv[:, None]) + (1.0 - feasible_ratio) * cv[:, None]


def penalty_clustering(decisions, objectives, constraints, cluster_num, rng,
                       max_iter=100, check=None):
    """Cluster PENALTY vectors; average the associated decision rows.

    NumPy k-means++/Lloyd with unique-point cap and donor-based empty-cluster
    repair. This is not decision-space k-means or temporal cluster matching.
    """
    decisions = _matrix("decisions", decisions)
    penalty = modify_objectives(objectives, constraints)
    if not len(decisions) or len(decisions) != len(penalty):
        raise ValueError("Clustering requires matching non-empty population rows.")
    k = min(_integer("cluster_num", cluster_num), len(np.unique(penalty, axis=0)))
    max_iter = _integer("max_iter", max_iter)
    check = check or (lambda: None)
    check()
    means = [penalty[int(rng.integers(len(penalty)))].copy()]
    distance = np.sum((penalty - means[0]) ** 2, axis=1)
    for _ in range(1, k):
        check()
        means.append(penalty[rng.choice(len(penalty), p=distance / distance.sum())].copy())
        distance = np.minimum(distance, np.sum((penalty - means[-1]) ** 2, axis=1))
    means = np.asarray(means)
    previous_labels = None
    for _ in range(max_iter):
        check()
        distances = np.sum((penalty[:, None, :] - means[None, :, :]) ** 2, axis=2)
        labels = np.argmin(distances, axis=1)
        sizes = np.bincount(labels, minlength=k)
        # Split a donor cluster rather than taking the mean of an empty slice.
        for empty in np.flatnonzero(sizes == 0):
            check()
            donors = np.flatnonzero(sizes[labels] > 1)
            residual = distances[donors, labels[donors]]
            point = donors[int(np.argmax(residual))]
            sizes[labels[point]] -= 1
            labels[point] = empty
            sizes[empty] = 1
        means = np.vstack([penalty[labels == i].mean(axis=0) for i in range(k)])
        if previous_labels is not None and np.array_equal(labels, previous_labels):
            break
        previous_labels = labels.copy()
    centers = np.vstack([decisions[labels == i].mean(axis=0) for i in range(k)])
    check()
    return labels, centers


def predict_centers(decisions, previous_decisions, centers):
    """FCP.m: translate EVERY current center by the whole-population drift."""
    decisions = _matrix("decisions", decisions)
    previous_decisions = _matrix("previous_decisions", previous_decisions, decisions.shape[1])
    centers = _matrix("centers", centers, decisions.shape[1])
    if not len(decisions) or not len(previous_decisions):
        raise ValueError("Prediction needs two non-empty environment snapshots.")
    return centers + decisions.mean(axis=0) - previous_decisions.mean(axis=0)


def center_spacing(centers, rng):
    """ClassP/ClassDis2: random same-environment permutation, including self."""
    centers = _matrix("centers", centers)
    pairs = rng.permutation(len(centers))
    return np.abs(centers - centers[pairs]), pairs


def repair_bounds(decisions, lower, upper):
    """Finite, bounded triangular reflection; supports negative/fixed bounds."""
    lower, upper, span = _bounds(lower, upper)
    values = np.asarray(decisions, dtype=float).copy()
    if values.ndim != 2 or values.shape[1] != len(lower):
        raise ValueError("Decision shape does not match bounds.")
    values = np.where(np.isnan(values), lower * 0.5 + upper * 0.5, values)
    values = np.where(np.isposinf(values), upper, values)
    values = np.where(np.isneginf(values), lower, values)
    safe_span = np.where(span > 0.0, span, 1.0)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        unit = (values - lower) / safe_span
        folded = np.mod(unit, 2.0)
        repaired = lower + np.minimum(folded, 2.0 - folded) * span
    repaired = np.where(np.isfinite(repaired), repaired, np.clip(values, lower, upper))
    # Preserve in-bound rows exactly; their objectives may still be historical.
    repaired = np.where((values >= lower) & (values <= upper), values, repaired)
    return np.clip(repaired, lower, upper)


def generate_population(centers, spacing, count, lower, upper, rng, check=None):
    """exDiversity: center + independent U[-1,1] * coordinatewise spacing."""
    centers = _matrix("centers", centers)
    spacing = _matrix("spacing", spacing, centers.shape[1])
    count = _integer("count", count)
    if centers.shape != spacing.shape or not len(centers) or np.any(spacing < 0.0):
        raise ValueError("Centers and non-negative spacing must have matching shapes.")
    check = check or (lambda: None)
    blocks = []
    quotient, remainder = divmod(count, len(centers))
    for index, center in enumerate(centers):
        check()
        size = quotient + (index < remainder)
        blocks.append(center + rng.uniform(-1.0, 1.0, (size, len(center))) * spacing[index])
    return repair_bounds(np.vstack(blocks), lower, upper)


class _Cancelled(Exception):
    pass


class FCP(ResponseStrategy):
    """Penalty-assisted multicenter prediction, not the complete FCP optimizer.

    History is committed only after a successful response. A False return from
    algorithm.control_process() cancels and returns the caller's population.
    Exceptions raised by the hook propagate unchanged.
    """

    def __init__(self, cluster_num=10, max_iter=100, crossover_eta=20.0,
                 mutation_eta=20.0, diversity_floor=0.02, evaluation_batch_size=64):
        super().__init__()
        self.cluster_num = _integer("cluster_num", cluster_num)
        self.max_iter = _integer("max_iter", max_iter)
        self.crossover_eta = _real("crossover_eta", crossover_eta)
        self.mutation_eta = _real("mutation_eta", mutation_eta)
        self.diversity_floor = _real("diversity_floor", diversity_floor, maximum=1.0)
        self.evaluation_batch_size = _integer("evaluation_batch_size", evaluation_batch_size)
        self._history = []
        self._response_count = 0
        self._problem = None
        self._bound_key = None
        self._last_t = None
        self._last_evaluations = None

    @staticmethod
    def _arrays(population):
        objectives = _matrix("population objectives", population.get_objective_matrix())
        constraints = [individual.G for individual in population]
        if all(value is None for value in constraints):
            return objectives, None
        if any(value is None for value in constraints):
            raise ValueError("Population has inconsistent constraint metadata.")
        constraints = _matrix("population constraints", np.asarray(constraints, dtype=float))
        if len(constraints) != len(objectives):
            raise ValueError("Population objective and constraint row counts differ.")
        return objectives, constraints

    def _evaluate(self, decisions, problem, check):
        individuals = []
        for start in range(0, len(decisions), self.evaluation_batch_size):
            check()
            batch = Population(X=decisions[start:start + self.evaluation_batch_size].copy(),
                               xl=problem.xl, xu=problem.xu)
            batch.update_objective_constrain(problem)
            self._arrays(batch)
            if not np.all(np.isfinite(batch.get_constraint_violation_vector())):
                raise ValueError("Evaluation returned non-finite total constraint violation.")
            individuals.extend(batch.individuals)
            check()
        return Population(individuals=individuals, xl=problem.xl, xu=problem.xu)

    def _select(self, population, count, check):
        if count == 0:
            return Population(xl=population.xl, xu=population.xu)
        check()
        objectives, constraints = self._arrays(population)
        penalty = modify_objectives(objectives, constraints)
        fronts = fast_non_dominated_sort(objectives, population.get_constraint_violation_vector())
        selected = []
        for rank, indices in enumerate(fronts, start=1):
            check()
            distance = crowding_distance(penalty, indices)
            for index, crowd in zip(indices, distance):
                population[index].rank = rank
                population[index].crowding_distance = float(crowd)
            order = indices[np.argsort(-distance, kind="stable")]
            selected.extend(population[i] for i in order[:count - len(selected)])
            if len(selected) == count:
                break
        return Population(individuals=selected, xl=population.xl, xu=population.xu)

    def _variation(self, parents, lower, upper, rng, check):
        """Independent real-valued SBX + bounded polynomial mutation bootstrap."""
        check()
        span = upper - lower
        safe_span = np.where(span > 0.0, span, 1.0)
        unit = np.clip((parents - lower) / safe_span, 0.0, 1.0)
        # Pair by a random permutation; odd/single populations retain a parent.
        shuffled = unit[rng.permutation(len(unit))]
        pairs = len(shuffled) // 2
        first, second = shuffled[:pairs], shuffled[pairs:2 * pairs]
        draws = rng.random(first.shape)
        exponent = 1.0 / (self.crossover_eta + 1.0)
        beta = np.where(draws <= 0.5, (2.0 * draws) ** exponent,
                        (2.0 * np.maximum(1.0 - draws, np.finfo(float).eps)) ** (-exponent))
        beta *= rng.choice([-1.0, 1.0], size=beta.shape)
        beta[rng.random(beta.shape) < 0.5] = 1.0
        midpoint = 0.5 * (first + second)
        spread = 0.5 * beta * (first - second)
        children = np.vstack((midpoint + spread, midpoint - spread, shuffled[2 * pairs:]))
        children = np.clip(children, 0.0, 1.0)
        draws = rng.random(children.shape)
        sites = (rng.random(children.shape) < 1.0 / len(lower)) & (span > 0.0)
        power = 1.0 / (self.mutation_eta + 1.0)
        left = (2.0 * draws + (1.0 - 2.0 * draws)
                * (1.0 - children) ** (self.mutation_eta + 1.0))
        right = (2.0 * (1.0 - draws) + (2.0 * draws - 1.0)
                 * children ** (self.mutation_eta + 1.0))
        delta = np.where(draws <= 0.5, np.maximum(left, 0.0) ** power - 1.0,
                         1.0 - np.maximum(right, 0.0) ** power)
        children = np.clip(children + np.where(sites, delta, 0.0), 0.0, 1.0)
        check()
        return lower + children * span

    def _bootstrap(self, decisions, target, problem, lower, upper, rng, check):
        if len(decisions) < target:
            decisions = np.vstack((decisions, rng.uniform(lower, upper,
                                  size=(target - len(decisions), len(lower)))))
        base = self._select(self._evaluate(decisions, problem, check), target, check)
        feasible_ratio = np.mean(base.get_constraint_violation_vector() <= _FEASIBILITY_TOLERANCE)
        keep_count = 2 * int(np.floor(target * feasible_ratio / 2.0))
        retained = self._select(base, keep_count, check)
        retained_ids = {id(individual) for individual in retained}
        remaining = np.asarray([individual.X for individual in base
                                if id(individual) not in retained_ids]).reshape(-1, len(lower))
        newcomers = self._variation(remaining, lower, upper, rng, check)
        offspring = self._evaluate(newcomers, problem, check)
        combined = Population(individuals=base.individuals + retained.individuals + offspring.individuals,
                              xl=lower, xu=upper)
        return self._select(combined, target, check)

    def response(self, population, problem, algorithm):
        hook = getattr(algorithm, "control_process", None)

        def check():
            if callable(hook) and not hook():
                raise _Cancelled

        try:
            check()
            target = _integer("solution_num", problem.solution_num)
            dimension = _integer("decision_num", problem.decision_num)
            lower, upper, span = _bounds(problem.xl, problem.xu)
            if len(lower) != dimension:
                raise ValueError("Problem bounds do not match decision_num.")
            seed = getattr(algorithm, "seed", None)
            seed = 0 if seed is None else _integer("algorithm.seed", seed, minimum=0)
            bound_key = (lower.tobytes(), upper.tobytes())
            time = getattr(problem, "t", None)
            time = None if time is None else _integer("problem.t", time, minimum=0)
            evaluations = getattr(problem, "evaluate_time", None)
            evaluations = (None if evaluations is None
                           else _integer("problem.evaluate_time", evaluations, minimum=0))
            rollback = (
                (time is not None and self._last_t is not None and time < self._last_t)
                or (evaluations is not None and self._last_evaluations is not None
                    and evaluations < self._last_evaluations)
            )
            same_context = (self._problem is problem and self._bound_key == bound_key
                            and not rollback)
            history = self._history if same_context else []
            response_count = self._response_count if same_context else 0
            # One slot per distinct environment: never predict from a snapshot
            # recorded by a previous response to this SAME environment.
            repeated_environment = same_context and time is not None and time == self._last_t
            prediction_history = history[:-1] if repeated_environment else history
            rng = np.random.default_rng(np.random.SeedSequence([seed, response_count]))
            raw = (np.asarray(population.get_decision_matrix(), dtype=float)
                   if len(population) else np.empty((0, dimension)))
            decisions = repair_bounds(raw, lower, upper)
            has_old_values = (len(decisions) > 0 and np.array_equal(raw, decisions)
                              and all(individual.F is not None for individual in population))
            if not prediction_history or not has_old_values:
                result = self._bootstrap(decisions, target, problem, lower, upper, rng, check)
            else:
                objectives, constraints = self._arrays(population)
                _, centers = penalty_clustering(decisions, objectives, constraints,
                                                self.cluster_num, rng, self.max_iter, check)
                predicted = predict_centers(decisions, prediction_history[-1], centers)
                spacing, _ = center_spacing(centers, rng)
                if not np.any(spacing > 0.0):
                    # Degenerate-only safeguard; ordinary self-pair widths stay zero.
                    width = np.maximum(0.5 * np.ptp(decisions, axis=0), self.diversity_floor * span)
                    spacing = np.broadcast_to(width, centers.shape).copy()
                generated = generate_population(predicted, spacing, target, lower, upper, rng, check)
                result = self._select(self._evaluate(generated, problem, check), target, check)
            check()
            # No input individual, history array or RNG-global state is mutated.
            result = Population(individuals=[individual.copy() for individual in result], xl=lower, xu=upper)
            # Empty/unevaluated/repaired inputs cannot supply an old-environment snapshot.
            snapshot = decisions.copy() if has_old_values else result.get_decision_matrix().copy()
            self._history = (prediction_history + [snapshot])[-2:] if has_old_values else [snapshot]
            self._response_count = response_count + 1
            self._problem, self._bound_key = problem, bound_key
            self._last_t = time
            self._last_evaluations = getattr(problem, "evaluate_time", None)
            return result
        except _Cancelled:
            return population
