"""Exact, geometry-only assignment ambiguity certificates. Python 3.9+, stdlib.

MIT licensed. A separated cost assignment does not prove physical identity.
Bounding boxes use inclusive integer extrema (xmin, ymin, xmax, ymax).
"""

import re

MAX_OBJECTS = 16
MAX_ABS_COORDINATE = 1_000_000_000
ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}\Z")


class InputHold(ValueError):
    """An input cannot safely receive a correspondence certificate."""

    def __init__(self, code, detail):
        self.code = code
        self.detail = detail
        super().__init__(detail)


def _integer(value, name, bound=None):
    if type(value) is not int:
        raise InputHold("INVALID_INTEGER", name + " must be an exact Python int")
    if bound is not None and abs(value) > bound:
        raise InputHold("COORDINATE_LIMIT", name + " exceeds the coordinate limit")
    return value


def _frame(objects, name):
    if type(objects) not in (list, tuple):
        raise InputHold("INVALID_FRAME", name + " must be a list or tuple")
    if len(objects) > MAX_OBJECTS:
        raise InputHold("OBJECT_LIMIT", name + " exceeds 16 objects")
    seen = set()
    validated = []
    for index, obj in enumerate(objects):
        label = name + "[" + str(index) + "]"
        if type(obj) is not dict or set(obj) != {"id", "bbox"}:
            raise InputHold("INVALID_OBJECT", label + " needs exactly id and bbox")
        object_id = obj["id"]
        if type(object_id) is not str or ID_PATTERN.fullmatch(object_id) is None:
            raise InputHold("INVALID_ID", label + " id must be 1-64 ASCII ID characters")
        if object_id in seen:
            raise InputHold("DUPLICATE_ID", name + " repeats the exact ID " + object_id)
        seen.add(object_id)
        bbox = obj["bbox"]
        if type(bbox) not in (list, tuple) or len(bbox) != 4:
            raise InputHold("INVALID_BOX", label + " bbox needs four integer extrema")
        values = tuple(_integer(v, label + " bbox", MAX_ABS_COORDINATE) for v in bbox)
        x0, y0, x1, y1 = values
        if x0 > x1 or y0 > y1:
            raise InputHold("INVALID_BOX", label + " has reversed extrema")
        validated.append({"id": object_id, "bbox": values, "center2": (x0 + x1, y0 + y1)})
    return sorted(validated, key=lambda obj: obj["id"])


def _matrix(costs):
    if type(costs) not in (list, tuple) or not 1 <= len(costs) <= MAX_OBJECTS:
        raise ValueError("cost matrix must have 1-16 rows")
    n = len(costs)
    result = []
    for row in costs:
        if type(row) not in (list, tuple) or len(row) != n:
            raise ValueError("cost matrix must be square")
        if any(type(c) is not int or c < 0 for c in row):
            raise ValueError("costs must be nonnegative exact Python integers")
        result.append(tuple(row))
    return tuple(result)


def solve_assignment(costs, forbidden_edge=None):
    """Return an exact primal-dual certificate, or None if no perfect matching.

    The O(n^3) shortest-augmenting-path Hungarian method uses integer potentials.
    A forbidden edge is skipped, with no artificial cost or infinity value.
    Equal slacks choose the lowest column index deterministically. This does not
    promise the lexicographically smallest optimal permutation.
    """
    costs = _matrix(costs)
    n = len(costs)
    if forbidden_edge is not None:
        if (type(forbidden_edge) is not tuple or len(forbidden_edge) != 2
                or any(type(v) is not int or not 0 <= v < n for v in forbidden_edge)):
            raise ValueError("forbidden edge must be a pair of valid integer indices")
    # Index zero is a temporary root column; p[j] stores its matched row.
    u, v, p, predecessor = ([0] * (n + 1) for _ in range(4))
    for row in range(1, n + 1):
        p[0] = row
        current = 0
        slack = [None] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[current] = True
            active_row = p[current]
            next_column, delta = None, None
            for column in range(1, n + 1):
                if used[column]:
                    continue
                if forbidden_edge != (active_row - 1, column - 1):
                    reduced = costs[active_row - 1][column - 1] - u[active_row] - v[column]
                    if slack[column] is None or reduced < slack[column]:
                        slack[column] = reduced
                        predecessor[column] = current
                # Earlier visited rows may provide this slack even if the
                # current row's edge is forbidden; retain that valid path.
                if slack[column] is not None and (delta is None or slack[column] < delta):
                    delta, next_column = slack[column], column
            if next_column is None:
                return None
            for column in range(n + 1):
                if used[column]:
                    u[p[column]] += delta
                    v[column] -= delta
                elif slack[column] is not None:
                    slack[column] -= delta
            current = next_column
            if p[current] == 0:
                break
        while current != 0:
            previous = predecessor[current]
            p[current] = p[previous]
            current = previous
    columns = [None] * n
    for column in range(1, n + 1):
        columns[p[column] - 1] = column - 1
    if forbidden_edge is not None and columns[forbidden_edge[0]] == forbidden_edge[1]:
        raise RuntimeError("internal solver error: forbidden edge selected")
    total = sum(costs[row][columns[row]] for row in range(n))
    return {"columns": columns, "total_cost": total,
            "row_potentials": u[1:], "column_potentials": v[1:],
            "forbidden_edge": list(forbidden_edge) if forbidden_edge is not None else None}


def qualify_correspondence(before, after, threshold2=0):
    """Certify ambiguity under a doubled-center Manhattan assignment objective.

    Supply threshold2 before inspecting this pair. A finite edge exclusion
    regret <= threshold2 abstains. HOLD results contain no partial mapping.
    """
    try:
        threshold2 = _integer(threshold2, "threshold2")
        if threshold2 < 0:
            raise InputHold("INVALID_THRESHOLD", "threshold2 must be nonnegative")
        left = _frame(before, "before")
        right = _frame(after, "after")
        if not left or not right:
            raise InputHold("EMPTY_FRAME", "both frames must contain at least one object")
        if len(left) != len(right):
            raise InputHold("UNEQUAL_COUNTS", "births, deaths, splits and merges require another model")
    except InputHold as error:
        return {"schema_version": 1, "status": "HOLD", "reason": error.code, "detail": error.detail}
    n = len(left)
    costs = [[sum(abs(a - b) for a, b in zip(old["center2"], new["center2"]))
              for new in right] for old in left]
    primary = solve_assignment(costs)
    if primary is None:
        raise RuntimeError("internal solver error: complete matrix has no assignment")
    edges, finite_gaps = [], []
    for row, column in enumerate(primary["columns"]):
        alternative = solve_assignment(costs, (row, column))
        if alternative is None:
            if n != 1:
                raise RuntimeError("internal solver error: an alternative exists for n>=2")
            regret = None
            decision = "ONLY_FEASIBLE_ASSIGNMENT"
        else:
            regret = alternative["total_cost"] - primary["total_cost"]
            if regret < 0:
                raise RuntimeError("internal solver error: negative exclusion regret")
            finite_gaps.append(regret)
            decision = ("ABSTAIN_TIE" if regret == 0 else
                        "ABSTAIN_NEAR_TIE" if regret <= threshold2 else
                        "SEPARATED_UNDER_COST_MODEL")
        delta2 = [b - a for a, b in zip(left[row]["center2"], right[column]["center2"])]
        edges.append({"before_id": left[row]["id"], "after_id": right[column]["id"],
                      "selected_cost2": costs[row][column],
                      "candidate_displacement2": delta2, "exclusion_regret2": regret,
                      "decision": decision, "abstain": regret is not None and regret <= threshold2,
                      "alternative_certificate": alternative})
    global_gap = min(finite_gaps) if finite_gaps else None
    return {"schema_version": 1, "status": "CERTIFIED_UNDER_COST_MODEL",
            "cost_units": "twice_center_coordinate_L1", "threshold2": threshold2,
            "before_ids": [obj["id"] for obj in left], "after_ids": [obj["id"] for obj in right],
            "before_centers2": [list(obj["center2"]) for obj in left],
            "after_centers2": [list(obj["center2"]) for obj in right],
            "cost_matrix2": costs, "primary_certificate": primary,
            "global_best_distinct_gap2": global_gap,
            "has_alternative_assignment": bool(finite_gaps),
            "edges": edges,
            "interpretation": "Assignment ambiguity only; no physical identity or motion truth guarantee."}
