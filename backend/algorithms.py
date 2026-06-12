"""
PSR Algorithms - Van der Merwe, Kruger & Du Toit (2018)
Implements Algorithms 1, 2, and 3 from the paper using SciPy linprog.
"""
import numpy as np
from scipy.optimize import linprog, minimize
from itertools import product


def algorithm1_linear_pmark(factor_averages: list[float], weights_bounds: tuple = (0.01, 0.40),
                             priority_order: bool = True) -> dict:
    """
    Algorithm 1: Linear model for p-mark calculation.
    Computes min/max p-marks and average for a single student.

    factor_averages: list of factor averages (e.g. [F1, F2, F3, F4]) as percentages
    weights_bounds: (lower, upper) bounds for each weight
    priority_order: if True, enforce w1 >= w2 >= w3 >= ... (priority sequence)

    Returns dict with min_pmark, max_pmark, avg_pmark, weights_min, weights_max
    """
    n = len(factor_averages)
    y = np.array(factor_averages)
    l_bound, u_bound = weights_bounds

    # ---- Constraints shared by min and max ----
    # sum(w) = 1  =>  A_eq, b_eq
    A_eq = np.ones((1, n))
    b_eq = np.array([1.0])

    # Bounds per weight: l_bound <= w_j <= u_bound
    bounds = [(l_bound, u_bound)] * n

    # Priority sequence: w_j >= w_{j+1}  =>  w_j - w_{j+1} >= 0
    # As inequality: -w_j + w_{j+1} <= 0
    if priority_order and n > 1:
        A_ub = []
        b_ub = []
        for j in range(n - 1):
            row = [0.0] * n
            row[j] = -1.0
            row[j + 1] = 1.0
            A_ub.append(row)
            b_ub.append(0.0)
        A_ub = np.array(A_ub)
        b_ub = np.array(b_ub)
    else:
        A_ub = None
        b_ub = None

    # ---- Minimise p-mark: minimise w^T y ----
    res_min = linprog(c=y, A_ub=A_ub, b_ub=b_ub,
                      A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                      method='highs')
    if res_min.success:
        min_pmark = float(res_min.fun)
        weights_min = res_min.x.tolist()
    else:
        # Fallback: equal weights
        weights_min = [1 / n] * n
        min_pmark = float(np.dot(y, weights_min))

    # ---- Maximise p-mark: minimise -w^T y ----
    res_max = linprog(c=-y, A_ub=A_ub, b_ub=b_ub,
                      A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                      method='highs')
    if res_max.success:
        max_pmark = float(-res_max.fun)
        weights_max = res_max.x.tolist()
    else:
        weights_max = [1 / n] * n
        max_pmark = float(np.dot(y, weights_max))

    avg_pmark = (min_pmark + max_pmark) / 2.0

    return {
        "min_pmark": round(min_pmark, 2),
        "max_pmark": round(max_pmark, 2),
        "avg_pmark": round(avg_pmark, 2),
        "weights_min": [round(w, 4) for w in weights_min],
        "weights_max": [round(w, 4) for w in weights_max],
    }


def rank_students(students: list[dict]) -> list[dict]:
    """
    Run Algorithm 1 for all students and return ranked list.
    Each student dict must have: id, name, factor_averages (list)
    """
    results = []
    for s in students:
        psr = algorithm1_linear_pmark(s["factor_averages"])
        results.append({
            "id": s["id"],
            "name": s["name"],
            "factor_averages": s["factor_averages"],
            **psr
        })
    # Rank by avg_pmark descending
    results.sort(key=lambda x: x["avg_pmark"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1
    return results


def algorithm2_participation_plan(factor_averages: list[float],
                                   remaining_assessments: list[int],
                                   total_assessments: list[int],
                                   delta: float = 5.0,
                                   weights_min: list[float] = None) -> dict:
    """
    Algorithm 2: Potential participation plan.
    Calculates improvement scenarios and required scores.

    factor_averages: current averages per factor
    remaining_assessments: remaining assessment count per factor
    total_assessments: total planned assessments for semester per factor
    delta: required % improvement target
    weights_min: weights used for minimum p-mark (from Algorithm 1)

    Returns dict with scenarios, required scores, and projected p-mark changes.
    """
    n = len(factor_averages)
    y = np.array(factor_averages)
    e = np.array(remaining_assessments)   # e_j: remaining
    t = np.array(total_assessments)        # t_j: total

    if weights_min is None:
        weights_min = [1 / n] * n

    w = np.array(weights_min)

    # Current min p-mark
    current_min_pmark = float(np.dot(y, w))

    # Generate participation scenarios (truth-table style)
    # For each factor, student can participate in 0..e_j assessments
    factor_options = [list(range(int(ei) + 1)) for ei in e]
    all_combos = list(product(*factor_options))

    # Remove duplicate patterns and impossible ones
    seen = set()
    scenarios = []
    for combo in all_combos:
        key = tuple(combo)
        if key not in seen:
            seen.add(key)
            scenarios.append(list(combo))

    results = []
    for scenario in scenarios:
        eta = np.array(scenario, dtype=float)  # assessments to attempt
        required_scores = []
        feasible = True

        new_avg = y.copy()
        for j in range(n):
            if eta[j] == 0:
                required_scores.append(None)
                continue
            # Equation (22): marks_j = (delta*t_j + e_j*y_j) / eta_j
            # For attendance factors (binary 0/100) use eq (23)
            score = (delta * t[j] / 100.0 + e[j] * y[j] / 100.0) * 100.0 / eta[j] if eta[j] > 0 else None

            # Adjusted: marks_j = (delta*t_j + e_j*y_j) / eta_j  [as in eq 22]
            score = ((delta / 100.0) * t[j] + y[j] * e[j] / 100.0) * (100.0 / eta[j]) if eta[j] > 0 else None

            if score is not None and score > 100.0:
                feasible = False
                required_scores.append(None)
            else:
                required_scores.append(round(score, 2) if score else None)
                if score is not None:
                    # New average if this scenario is followed
                    completed = t[j] - e[j]
                    new_avg[j] = (y[j] * completed + score * eta[j]) / (completed + eta[j])

        if feasible:
            new_min_pmark = float(np.dot(new_avg, w))
            pmark_change = round(new_min_pmark - current_min_pmark, 2)
            results.append({
                "scenario": scenario,
                "required_scores": required_scores,
                "new_avg": [round(float(v), 2) for v in new_avg],
                "pmark_change": pmark_change,
                "new_min_pmark": round(new_min_pmark, 2)
            })

    # Sort by pmark_change descending (best scenarios first)
    results.sort(key=lambda x: x["pmark_change"], reverse=True)

    # Limit to top 10 most meaningful scenarios
    top_results = results[:10]

    return {
        "current_min_pmark": round(current_min_pmark, 2),
        "delta": delta,
        "scenarios": top_results,
        "total_scenarios": len(results)
    }


def algorithm3_weight_selection(all_factor_averages: list[list[float]],
                                 target_class_average: float,
                                 weights_bounds: tuple = (0.01, 0.40),
                                 priority_order: bool = True) -> dict:
    """
    Algorithm 3: Non-linear model for weight selection.
    Finds weights that produce a p-mark class average closest to target.

    all_factor_averages: list of factor averages for all students
    target_class_average: desired class p-mark average
    """
    n = len(all_factor_averages[0])
    m = len(all_factor_averages)
    Y = np.array(all_factor_averages)
    l_bound, u_bound = weights_bounds

    def objective(w):
        pa = np.mean(Y @ w)
        return abs(target_class_average - pa)

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    if priority_order and n > 1:
        for j in range(n - 1):
            idx = j
            constraints.append({
                "type": "ineq",
                "fun": lambda w, i=idx: w[i] - w[i + 1]
            })

    bounds = [(l_bound, u_bound)] * n
    w0 = np.array([1 / n] * n)

    res = minimize(objective, w0, method='SLSQP',
                   bounds=bounds, constraints=constraints,
                   options={"maxiter": 1000, "ftol": 1e-9})

    if res.success or res.fun < 1.0:
        weights = res.x
        actual_average = float(np.mean(Y @ weights))
    else:
        weights = w0
        actual_average = float(np.mean(Y @ weights))

    return {
        "target_average": round(target_class_average, 2),
        "achieved_average": round(actual_average, 2),
        "weights": [round(float(w), 4) for w in weights],
        "deviation": round(abs(target_class_average - actual_average), 2)
    }


def compute_dea_classes(students: list[dict]) -> list[dict]:
    """
    Outputs-only DEA class ranking.
    Groups students into efficiency classes based on Pareto dominance.
    """
    data = [(s["id"], s["name"], np.array(s["factor_averages"])) for s in students]
    n = len(data)
    classes = {}
    remaining = list(range(n))
    cls = 1

    while remaining:
        # Find Pareto-optimal students among remaining
        pareto = []
        for i in remaining:
            dominated = False
            for j in remaining:
                if i == j:
                    continue
                yi = data[i][2]
                yj = data[j][2]
                # j dominates i if yj >= yi in all factors and yj > yi in at least one
                if np.all(yj >= yi) and np.any(yj > yi):
                    dominated = True
                    break
            if not dominated:
                pareto.append(i)
        for i in pareto:
            sid = data[i][0]
            classes[sid] = cls
            remaining.remove(i)
        cls += 1

    result = []
    for s in students:
        result.append({**s, "dea_class": classes.get(s["id"], cls)})
    result.sort(key=lambda x: (x["dea_class"], -x.get("avg_pmark", 0)))
    return result
