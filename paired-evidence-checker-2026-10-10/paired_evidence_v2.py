"""Original offline ARC3 paired-evidence checker. MIT, cubres 2026.

Consumes normalized records only. No model, environment, network or subprocess
calls. Private joining fields never appear in the returned aggregate summary.
Hashes are declarations until independently bound to source receipts upstream.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

ARMS = ("steps3", "steps4")
IDENTITY_KEYS = {"target_sha", "draft_sha", "tokenizer_sha", "environment_sha", "policy_sha", "sampling_sha", "non_step_config_sha"}
BUDGET_KEYS = {"actions", "llm_calls", "input_tokens", "output_tokens", "total_wall_s"}
USAGE_KEYS = BUDGET_KEYS | {"startup_wall_s", "game_wall_s"}
ROW_KEYS = {"pair_id", "game_key", "game_seed", "llm_seed", "arm", "period", "startup_state", "spec_steps", "draft_tokens",
            "identity", "initial_observation_sha", "budgets", "usage", "evidence", "final_reward"}
EVIDENCE_KEYS = {"receipt_sha", "terminal_state_sha", "finalized", "terminal", "errors", "stragglers", "settled", "runtime_scope", "stop_reason", "metric"}
SCOPE = "first_statement_to_terminal"
METRIC = "terminal_native_reward_percent"


def digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def number(value, integer=False):
    if type(value) not in ((int,) if integer else (int, float)): return False
    try: return math.isfinite(value) and value >= 0
    except OverflowError: return False


def protocol_valid(protocol):
    keys = {"schema", "panel", "startup_states", "repetitions_per_order", "identity", "budgets", "runtime_scope", "metric"}
    if not isinstance(protocol, dict) or set(protocol) != keys: return False
    if protocol["schema"] != "original-paired-arc3-protocol-v1": return False
    if not isinstance(protocol["panel"], list) or not 1 <= len(protocol["panel"]) <= 500: return False
    seen = set()
    for item in protocol["panel"]:
        if not isinstance(item, dict) or set(item) != {"game_key", "game_seed", "llm_seed"}: return False
        if not isinstance(item["game_key"], str) or not 1 <= len(item["game_key"]) <= 100: return False
        if not number(item["game_seed"], True) or not number(item["llm_seed"], True): return False
        key = item["game_key"], item["game_seed"], item["llm_seed"]
        if key in seen: return False
        seen.add(key)
    if protocol["startup_states"] not in (["cold"], ["warm"], ["cold", "warm"]): return False
    if not number(protocol["repetitions_per_order"], True) or not 1 <= protocol["repetitions_per_order"] <= 10: return False
    if not isinstance(protocol["identity"], dict) or set(protocol["identity"]) != IDENTITY_KEYS: return False
    if not all(digest(v) for v in protocol["identity"].values()): return False
    if not isinstance(protocol["budgets"], dict) or set(protocol["budgets"]) != BUDGET_KEYS: return False
    if not all(number(v, k != "total_wall_s") and v > 0 for k, v in protocol["budgets"].items()): return False
    return protocol["runtime_scope"] == SCOPE and protocol["metric"] == METRIC


def row_reasons(row, protocol):
    if not isinstance(row, dict) or set(row) != ROW_KEYS: return {"record_schema"}
    reasons = set()
    if not isinstance(row["pair_id"], str) or not 1 <= len(row["pair_id"]) <= 120: reasons.add("pair_identifier")
    if not isinstance(row["game_key"], str) or not number(row["game_seed"], True) or not number(row["llm_seed"], True): reasons.add("join_identity")
    if row["arm"] not in ARMS or type(row["period"]) is not int or row["period"] not in (1, 2): reasons.add("arm_period")
    expected = 3 if row["arm"] == "steps3" else 4
    if type(row["spec_steps"]) is not int or type(row["draft_tokens"]) is not int or (row["spec_steps"], row["draft_tokens"]) != (expected, expected + 1): reasons.add("serving_treatment")
    if row["startup_state"] not in protocol["startup_states"]: reasons.add("startup_state")
    if row["identity"] != protocol["identity"]: reasons.add("model_environment_policy_sampling_mismatch")
    if not digest(row["initial_observation_sha"]): reasons.add("initial_observation")
    budgets = row["budgets"]
    if (not isinstance(budgets, dict) or set(budgets) != BUDGET_KEYS
            or not all(number(v, k != "total_wall_s") and v > 0 for k, v in budgets.items())
            or budgets != protocol["budgets"]): reasons.add("quota_mismatch")
    usage = row["usage"]
    if not isinstance(usage, dict) or set(usage) != USAGE_KEYS:
        reasons.add("usage_schema")
    elif not all(number(v, k in {"actions", "llm_calls", "input_tokens", "output_tokens"}) for k, v in usage.items()):
        reasons.add("usage_values")
    else:
        if any(usage[k] > protocol["budgets"][k] + (1e-6 if k == "total_wall_s" else 0) for k in BUDGET_KEYS): reasons.add("quota_exceeded")
        if usage["total_wall_s"] + 1e-6 < usage["startup_wall_s"] + usage["game_wall_s"]: reasons.add("runtime_accounting")
    evidence = row["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != EVIDENCE_KEYS:
        reasons.add("evidence_schema")
    else:
        if not digest(evidence["receipt_sha"]) or not digest(evidence["terminal_state_sha"]): reasons.add("unbound_terminal_receipt")
        if evidence["finalized"] is not True or evidence["terminal"] is not True: reasons.add("nonterminal_or_intermediate_reward")
        if not number(evidence["errors"], True) or evidence["errors"] != 0: reasons.add("errors")
        if not number(evidence["stragglers"], True) or evidence["stragglers"] != 0: reasons.add("stragglers")
        if evidence["settled"] is not True: reasons.add("unsettled_lifecycle")
        if evidence["runtime_scope"] != SCOPE or evidence["metric"] != METRIC: reasons.add("runtime_or_metric_scope")
        if evidence["stop_reason"] not in ("game_terminal", "budget_exhausted"): reasons.add("unfinished_stop_reason")
        if evidence["stop_reason"] == "budget_exhausted" and not reasons.intersection({"usage_schema", "usage_values"}):
            if not any(abs(usage[k] - protocol["budgets"][k]) <= (1e-3 if k == "total_wall_s" else 0) for k in BUDGET_KEYS): reasons.add("unsubstantiated_budget_stop")
    if not number(row["final_reward"]) or row["final_reward"] > 100: reasons.add("reward_values")
    return reasons


def summarize(protocol, records):
    """Validate the complete preregistered panel; return aggregates without IDs."""
    if not protocol_valid(protocol): raise ValueError("Invalid protocol contract")
    if not isinstance(records, list) or len(records) > 20000: raise ValueError("Invalid bounded record array")
    failures = Counter(); pairs = defaultdict(list); bad_rows = 0
    panel = {(p["game_key"], p["game_seed"], p["llm_seed"]) for p in protocol["panel"]}
    for row in records:
        reasons = row_reasons(row, protocol)
        if reasons:
            failures.update(reasons); bad_rows += 1; continue
        context = row["game_key"], row["game_seed"], row["llm_seed"]
        if context not in panel: failures["outside_registered_panel"] += 1; bad_rows += 1; continue
        pairs[row["pair_id"]].append(row)
    valid = []; invalid_pairs = 0; orders = defaultdict(Counter); init_by_stratum = defaultdict(set)
    for group in pairs.values():
        if len(group) != 2 or {r["arm"] for r in group} != set(ARMS):
            failures["missing_or_duplicate_arm"] += 1; invalid_pairs += 1; continue
        by_arm = {r["arm"]: r for r in group}; a, b = by_arm["steps3"], by_arm["steps4"]
        shared = ("game_key", "game_seed", "llm_seed", "startup_state", "initial_observation_sha")
        if any(a[k] != b[k] for k in shared) or {a["period"], b["period"]} != {1, 2}:
            failures["unmatched_pair_context_or_period"] += 1; invalid_pairs += 1; continue
        stratum = a["game_key"], a["game_seed"], a["llm_seed"], a["startup_state"]
        first = a["arm"] if a["period"] == 1 else b["arm"]
        orders[stratum][first] += 1; init_by_stratum[stratum].add(a["initial_observation_sha"])
        valid.append((stratum, a, b))
    required = {(*item, phase) for item in panel for phase in protocol["startup_states"]}
    for stratum in required:
        expected_orders = Counter({arm: protocol["repetitions_per_order"] for arm in ARMS})
        if orders[stratum] != expected_orders: failures["missing_or_unbalanced_counterbalance"] += 1
        if len(init_by_stratum[stratum]) != 1: failures["initial_observation_not_stable_across_orders"] += 1
    metrics = {}
    for phase in protocol["startup_states"]:
        members = [(s, a, b) for s, a, b in valid if s[-1] == phase]
        clusters = defaultdict(list)
        for stratum, a, b in members: clusters[stratum[:-1]].append(b["final_reward"] - a["final_reward"])
        means = [statistics.mean(values) for values in clusters.values()]
        metric = {"valid_pairs": len(members), "game_seed_llm_clusters": len(means),
            "mean_cluster_terminal_reward_delta_steps4_minus_steps3": statistics.mean(means) if means else None,
            "median_cluster_terminal_reward_delta": statistics.median(means) if means else None,
            "cluster_wins_ties_losses": {"wins": sum(x > 0 for x in means), "ties": sum(x == 0 for x in means), "losses": sum(x < 0 for x in means)}}
        for field in ("actions", "llm_calls", "input_tokens", "output_tokens", "total_wall_s", "startup_wall_s", "game_wall_s"):
            metric["mean_" + field + "_delta_steps4_minus_steps3"] = statistics.mean(b["usage"][field] - a["usage"][field] for _, a, b in members) if members else None
        metrics[phase] = metric
    return {"schema": "original-offline-arc3-paired-evidence-summary-v1", "official_score": None,
        "qualification_status": "HOLD_INCOMPLETE_OR_UNMATCHED" if failures else "PAIRED_DIAGNOSTIC_READY",
        "strategy_adoption": "NO_AUTOMATIC_ADOPTION", "records": len(records), "registered_panel_items": len(panel),
        "required_startup_states": protocol["startup_states"], "valid_pairs": len(valid), "invalid_pairs": invalid_pairs,
        "rejected_records": bad_rows, "failure_counts": dict(sorted(failures.items())), "metrics_by_startup_state": metrics,
        "limits": ["Normalized hash/evidence fields are declarations until independently checked against complete native receipts.",
            "This checks paired comparability; a passed contract is not causal, statistical, hidden or official score evidence.",
            "Cold and warm results remain separate; repeats within a game/seed cluster are not independent games.",
            "Input identities, private joins, payloads and individual outcomes are excluded from this summary."]}


def main():
    p = argparse.ArgumentParser()
    for name in ("protocol", "records", "output"): p.add_argument("--" + name, type=Path, required=True)
    a = p.parse_args(); protocol_raw, record_raw = a.protocol.read_bytes(), a.records.read_bytes()
    result = summarize(json.loads(protocol_raw), json.loads(record_raw))
    result["input_sha256"] = {"protocol": hashlib.sha256(protocol_raw).hexdigest(), "records": hashlib.sha256(record_raw).hexdigest()}
    with a.output.open("x") as f: json.dump(result, f, indent=2, sort_keys=True); f.write("\n")
    print(json.dumps({"qualification_status": result["qualification_status"], "valid_pairs": result["valid_pairs"], "failure_counts": result["failure_counts"]}))


if __name__ == "__main__": main()
