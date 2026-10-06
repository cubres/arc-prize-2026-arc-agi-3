"""Independent permutation oracle and exact primal-dual checks; no assert."""

import argparse
import copy
import itertools
import json
import random
from pathlib import Path

from correspondence import qualify_correspondence, solve_assignment


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def check_certificate(costs, certificate, forbidden=None):
    """Check optimality directly, without calling the assignment solver."""
    require(type(costs) in (list, tuple) and 1 <= len(costs) <= 16, "cost matrix size outside 1-16")
    n = len(costs)
    for row in costs:
        require(type(row) in (list, tuple) and len(row) == n, "cost matrix must be square")
        require(all(type(value) is int and value >= 0 for value in row), "costs must be nonnegative exact integers")
    if forbidden is not None:
        require(type(forbidden) is tuple and len(forbidden) == 2 and
                all(type(index) is int and 0 <= index < n for index in forbidden), "invalid forbidden indices")
    require(type(certificate) is dict, "missing certificate")
    columns = certificate.get("columns")
    require(type(columns) is list and len(columns) == n, "wrong assignment length")
    require(all(type(c) is int for c in columns), "noninteger assignment")
    require(sorted(columns) == list(range(n)), "not a permutation")
    require(certificate.get("forbidden_edge") == (list(forbidden) if forbidden is not None else None),
            "wrong forbidden edge binding")
    if forbidden is not None:
        require(columns[forbidden[0]] != forbidden[1], "forbidden edge selected")
    row_u, column_v = certificate.get("row_potentials"), certificate.get("column_potentials")
    require(type(row_u) is list and type(column_v) is list and len(row_u) == len(column_v) == n,
            "wrong potential length")
    require(all(type(value) is int for value in row_u + column_v), "noninteger potentials")
    total = sum(costs[i][columns[i]] for i in range(n))
    require(type(certificate.get("total_cost")) is int and certificate["total_cost"] == total,
            "wrong primal total")
    require(sum(row_u) + sum(column_v) == total, "primal-dual mismatch")
    for row in range(n):
        for column in range(n):
            if forbidden != (row, column):
                require(row_u[row] + column_v[column] <= costs[row][column], "dual infeasibility")
    return total


def oracle(costs, forbidden=None):
    options = [(sum(costs[i][p[i]] for i in range(len(costs))), p)
               for p in itertools.permutations(range(len(costs)))
               if forbidden is None or p[forbidden[0]] != forbidden[1]]
    return min(options) if options else None


def check_matrix(costs):
    primary = solve_assignment(costs)
    require(primary is not None, "complete matrix reported infeasible")
    base = check_certificate(costs, primary)
    require(base == oracle(costs)[0], "wrong optimum against permutation oracle")
    all_distinct = [sum(costs[i][p[i]] for i in range(len(costs)))
                    for p in itertools.permutations(range(len(costs)))
                    if list(p) != primary["columns"]]
    regrets = []
    for row, column in enumerate(primary["columns"]):
        alternative = solve_assignment(costs, (row, column))
        expected = oracle(costs, (row, column))
        if expected is None:
            require(len(costs) == 1 and alternative is None, "invalid no-alternative result")
        else:
            total = check_certificate(costs, alternative, (row, column))
            require(total == expected[0], "wrong forbidden-edge optimum")
            regrets.append(total - base)
    require((min(regrets) if regrets else None) ==
            (min(all_distinct) - base if all_distinct else None), "global gap identity failed")


def points(values, prefix):
    return [{"id": prefix + str(i), "bbox": [x, y, x, y]} for i, (x, y) in enumerate(values)]


def check_geometry(before, after, threshold2=0):
    report = qualify_correspondence(before, after, threshold2)
    require(report["status"] == "CERTIFIED_UNDER_COST_MODEL", "valid geometry held")
    old = sorted(before, key=lambda o: o["id"])
    new = sorted(after, key=lambda o: o["id"])
    centers = lambda frame: [(o["bbox"][0] + o["bbox"][2], o["bbox"][1] + o["bbox"][3]) for o in frame]
    a, b = centers(old), centers(new)
    costs = [[abs(x[0] - y[0]) + abs(x[1] - y[1]) for y in b] for x in a]
    require(report["before_ids"] == [o["id"] for o in old] and
            report["after_ids"] == [o["id"] for o in new], "ID binding failed")
    require(report["cost_matrix2"] == costs, "cost construction failed")
    require(report["before_centers2"] == [list(c) for c in a] and
            report["after_centers2"] == [list(c) for c in b], "center binding failed")
    primary = report["primary_certificate"]
    base = check_certificate(costs, primary)
    require(base == oracle(costs)[0], "geometry optimum wrong")
    regrets = []
    for row, edge in enumerate(report["edges"]):
        column = primary["columns"][row]
        require(edge["before_id"] == old[row]["id"] and edge["after_id"] == new[column]["id"], "edge ID mismatch")
        require(edge["selected_cost2"] == costs[row][column], "edge cost mismatch")
        require(edge["candidate_displacement2"] == [b[column][k] - a[row][k] for k in range(2)], "displacement mismatch")
        expected = oracle(costs, (row, column))
        if expected is None:
            require(edge["alternative_certificate"] is None and edge["exclusion_regret2"] is None and
                    edge["decision"] == "ONLY_FEASIBLE_ASSIGNMENT" and edge["abstain"] is False, "singleton semantics wrong")
        else:
            alternative = check_certificate(costs, edge["alternative_certificate"], (row, column))
            require(alternative == expected[0], "wrong geometry alternative")
            regret = alternative - base
            require(edge["exclusion_regret2"] == regret and regret % 2 == 0, "regret/parity mismatch")
            require(edge["abstain"] == (regret <= threshold2), "threshold policy mismatch")
            decision = "ABSTAIN_TIE" if regret == 0 else "ABSTAIN_NEAR_TIE" if regret <= threshold2 else "SEPARATED_UNDER_COST_MODEL"
            require(edge["decision"] == decision, "decision mismatch")
            # The exact cost-budget statement is checked against all permutations.
            for permutation in itertools.permutations(range(len(costs))):
                total = sum(costs[i][permutation[i]] for i in range(len(costs)))
                if regret > threshold2 and total <= base + threshold2:
                    require(permutation[row] == column, "budget robustness statement failed")
            regrets.append(regret)
    require(report["global_best_distinct_gap2"] == (min(regrets) if regrets else None), "global report gap wrong")
    require(report["has_alternative_assignment"] == bool(regrets), "alternative flag wrong")
    return report


def run_checks():
    counts = {}
    # These matrices are not produced by the geometric implementation.
    matrices = [[[0]], [[10**40]], [[0, 0], [0, 0]], [[10**40, 0], [0, 10**40]]]
    for flat in itertools.product(range(3), repeat=4):
        matrices.append([list(flat[:2]), list(flat[2:])])
    for flat in itertools.product(range(2), repeat=9):
        matrices.append([list(flat[i:i + 3]) for i in range(0, 9, 3)])
    rng = random.Random(20261006)
    for n, repeats in ((4, 100), (5, 20), (6, 5)):
        for _ in range(repeats):
            matrices.append([[rng.randrange(11) for _ in range(n)] for _ in range(n)])
    for matrix in matrices:
        check_matrix(matrix)
    counts["matrix_permutation_oracles"] = len(matrices)
    lattice = list(itertools.product(range(3), repeat=2))
    frame_pairs = list(itertools.combinations_with_replacement(lattice, 2))
    total = 0
    for before in frame_pairs:
        for after in frame_pairs:
            check_geometry(points(before, "A"), points(after, "B"))
            total += 1
    lattice3 = [(0, 0), (0, 1), (1, 0), (1, 1)]
    triples = list(itertools.combinations_with_replacement(lattice3, 3))
    for before in triples:
        for after in triples:
            check_geometry(points(before, "A"), points(after, "B"))
            total += 1
    for n, repeats in ((4, 40), (5, 10), (6, 2)):
        for _ in range(repeats):
            check_geometry(points([(rng.randrange(-4, 5), rng.randrange(-4, 5)) for _ in range(n)], "A"),
                           points([(rng.randrange(-4, 5), rng.randrange(-4, 5)) for _ in range(n)], "B"))
            total += 1
    counts["geometry_permutation_oracles"] = total
    before = points([(0, 0), (2, 0), (10, 0)], "A")
    after = points([(1, -1), (1, 1), (10, 0)], "B")
    tied = check_geometry(before, after)
    require([e["abstain"] for e in tied["edges"]] == [True, True, False], "stable anchor wrongly abstained")
    require(tied["global_best_distinct_gap2"] == 0 and tied["edges"][2]["exclusion_regret2"] > 0, "local/global distinction lost")
    for bp in itertools.permutations(before):
        for ap in itertools.permutations(after):
            require(qualify_correspondence(list(bp), list(ap)) == tied, "input permutation changed report")
    counts["input_permutations"] = 36
    near_before = points([(0, 0), (2, 0)], "A")
    near_after = points([(1, 0), (2, 0)], "B")
    for threshold in (0, 1, 3, 4, 5):
        report = check_geometry(near_before, near_after, threshold)
        require(all(e["exclusion_regret2"] == 4 and e["abstain"] == (threshold >= 4) for e in report["edges"]), "near-tie boundary failed")
    counts["threshold_boundaries"] = 5
    def transform(frame, scale, tx, ty):
        return [{"id": o["id"], "bbox": [scale * o["bbox"][0] + tx, scale * o["bbox"][1] + ty,
                                            scale * o["bbox"][2] + tx, scale * o["bbox"][3] + ty]} for o in frame]
    translated = qualify_correspondence(transform(before, 1, 73, -91), transform(after, 1, 73, -91))
    for key in ("cost_matrix2", "primary_certificate", "edges", "global_best_distinct_gap2"):
        require(translated[key] == tied[key], "common translation changed costs or certificate")
    scaled = check_geometry(transform(near_before, 3, 0, 0), transform(near_after, 3, 0, 0), 12)
    require(scaled["global_best_distinct_gap2"] == 12, "integer scaling failed")
    boxes = [{"id": "A", "bbox": [-1, -2, 0, 1]}]
    single = check_geometry(boxes, [{"id": "B", "bbox": [0, -1, 3, 2]}])
    require(single["before_centers2"] == [[-1, -1]], "half-integer center lost")
    edge_limit = check_geometry(points([(-10**9, 10**9)], "A"), points([(10**9, -10**9)], "B"))
    require(edge_limit["primary_certificate"]["total_cost"] == 8 * 10**9, "coordinate boundary arithmetic failed")
    # n=16 has factorially many assignments; certify by exact dual inequalities.
    for centers in ([(0, 0)] * 16, [(i * 10, 0) for i in range(16)]):
        big = qualify_correspondence(points(centers, "A"), points(centers, "B"))
        check_certificate(big["cost_matrix2"], big["primary_certificate"])
        for row, edge in enumerate(big["edges"]):
            check_certificate(big["cost_matrix2"], edge["alternative_certificate"], (row, big["primary_certificate"]["columns"][row]))
    counts["invariance_and_boundary_cases"] = 6
    bad_inputs = [( [], [], 0, "EMPTY_FRAME"), (points([(0, 0)], "A"), points([(0, 0), (1, 1)], "B"), 0, "UNEQUAL_COUNTS"),
                  (points([(0, 0)] * 17, "A"), points([(0, 0)] * 17, "B"), 0, "OBJECT_LIMIT"),
                  (points([(0, 0)], "A"), points([(0, 0)], "B"), -1, "INVALID_THRESHOLD"),
                  (points([(0, 0)], "A"), points([(0, 0)], "B"), True, "INVALID_INTEGER"),
                  ([{"id": "A", "bbox": [0, 0, True, 0]}], points([(0, 0)], "B"), 0, "INVALID_INTEGER"),
                  ([{"id": "A", "bbox": [0, 0, 0.0, 0]}], points([(0, 0)], "B"), 0, "INVALID_INTEGER"),
                  ([{"id": "A", "bbox": [1, 0, 0, 0]}], points([(0, 0)], "B"), 0, "INVALID_BOX"),
                  ([{"id": "A", "bbox": [0, 0, 10**9 + 1, 0]}], points([(0, 0)], "B"), 0, "COORDINATE_LIMIT"),
                  ([{"id": "A", "bbox": [0, 0, 0, 0]}, {"id": "A", "bbox": [1, 0, 1, 0]}], points([(0, 0), (1, 0)], "B"), 0, "DUPLICATE_ID"),
                  ([{"id": " A", "bbox": [0, 0, 0, 0]}], points([(0, 0)], "B"), 0, "INVALID_ID"),
                  ([{"id": "A", "bbox": [0, 0, 0, 0], "extra": 1}], points([(0, 0)], "B"), 0, "INVALID_OBJECT"),
                  (points([(0, 0)], "A") + [{"id": "Z", "bbox": [0, 0, 0]}], points([(0, 0), (1, 0)], "B"), 0, "INVALID_BOX"),
                  (points([(0, 0)], "A"), points([(0, 0)], "B"), 0.0, "INVALID_INTEGER"),
                  ("bad", points([(0, 0)], "B"), 0, "INVALID_FRAME")]
    for before_bad, after_bad, threshold, reason in bad_inputs:
        held = qualify_correspondence(before_bad, after_bad, threshold)
        require(held["status"] == "HOLD" and held["reason"] == reason and "edges" not in held, "bad input produced mapping")
    counts["input_refusals"] = len(bad_inputs)
    certificate = solve_assignment([[0, 3], [4, 0]])
    tampered = []
    for key, value in (("columns", [0, 0]), ("columns", [True, 0]), ("total_cost", 1),
                       ("row_potentials", [1, 0]), ("column_potentials", [0.0, 0]),
                       ("forbidden_edge", [0, 0])):
        bad = copy.deepcopy(certificate)
        bad[key] = value
        tampered.append(bad)
    for bad in tampered:
        failed = False
        try:
            check_certificate([[0, 3], [4, 0]], bad)
        except ValueError:
            failed = True
        require(failed, "tampered certificate passed")
    counts["certificate_tamper_refusals"] = len(tampered)
    # These witnesses would satisfy the arithmetic without schema validation.
    zero = {"columns": [0], "total_cost": 0, "row_potentials": [0],
            "column_potentials": [0], "forbidden_edge": None}
    negative = dict(zero, total_cost=-1, row_potentials=[-1])
    empty = {"columns": [], "total_cost": 0, "row_potentials": [],
             "column_potentials": [], "forbidden_edge": None}
    over_cap = {"columns": list(range(17)), "total_cost": 0, "row_potentials": [0] * 17,
                "column_potentials": [0] * 17, "forbidden_edge": None}
    invalid_checker_inputs = [([[False]], zero, None), ([[0.0]], zero, None),
                              ([[-1]], negative, None), ([], empty, None),
                              ([[0] * 17 for _ in range(17)], over_cap, None),
                              ([[0, 0]], zero, None), ([[0]], zero, [0, 0]),
                              ([[0]], zero, (True, 0)), ([[0]], zero, (1, 0))]
    for matrix, witness, forbidden in invalid_checker_inputs:
        failed = False
        try:
            check_certificate(matrix, witness, forbidden)
        except ValueError:
            failed = True
        require(failed, "invalid checker input passed")
    counts["checker_schema_refusals"] = len(invalid_checker_inputs)
    return {"status": "PASS", "seed": 20261006, "counts": counts,
            "total_cases": sum(counts.values()), "scope": "synthetic CPU exact assignment mathematics only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, help="create a new verification JSON file")
    args = parser.parse_args()
    result = run_checks()
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.report is not None:
        with args.report.open("x", encoding="utf-8") as stream:
            stream.write(encoded)
    print(encoded, end="")


if __name__ == "__main__":
    main()
