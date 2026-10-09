"""Original invented fixtures for the offline paired checker. MIT, cubres 2026."""
import copy
import hashlib
import json
from pathlib import Path
import time
from paired_evidence_v2 import IDENTITY_KEYS, SCOPE, METRIC, summarize


def sha(text): return hashlib.sha256(text.encode()).hexdigest()


def fixture():
    identity = {k: sha("invented-" + k) for k in IDENTITY_KEYS}
    budgets = {"actions": 100, "llm_calls": 50, "input_tokens": 100000, "output_tokens": 10000, "total_wall_s": 120}
    panel = [{"game_key": "invented-a", "game_seed": 101, "llm_seed": 901}, {"game_key": "invented-b", "game_seed": 202, "llm_seed": 902}]
    protocol = {"schema": "original-paired-arc3-protocol-v1", "panel": panel, "startup_states": ["cold", "warm"],
        "repetitions_per_order": 1, "identity": identity, "budgets": budgets, "runtime_scope": SCOPE, "metric": METRIC}
    rows = []
    for item in panel:
        for phase in ("cold", "warm"):
            for order in ("steps3", "steps4"):
                pair_id = item["game_key"] + "-" + phase + "-" + order
                for arm in ("steps3", "steps4"):
                    startup = (20 if arm == "steps4" else 10) if phase == "cold" else 1
                    game = 10 if arm == "steps4" else 12
                    rows.append({**item, "pair_id": pair_id, "arm": arm, "period": 1 if arm == order else 2, "startup_state": phase,
                        "spec_steps": 3 if arm == "steps3" else 4, "draft_tokens": 4 if arm == "steps3" else 5,
                        "identity": copy.deepcopy(identity), "initial_observation_sha": sha(item["game_key"] + "initial"),
                        "budgets": copy.deepcopy(budgets), "usage": {"actions": 20 if arm == "steps3" else 18, "llm_calls": 10,
                            "input_tokens": 5000, "output_tokens": 1000, "startup_wall_s": startup, "game_wall_s": game, "total_wall_s": startup + game},
                        "evidence": {"receipt_sha": sha(pair_id + arm), "terminal_state_sha": sha("invented terminal"),
                            "finalized": True, "terminal": True, "errors": 0, "stragglers": 0, "settled": True,
                            "runtime_scope": SCOPE, "stop_reason": "game_terminal", "metric": METRIC},
                        "final_reward": 60 if arm == "steps4" else 50})
    return protocol, rows


def main():
    start = time.process_time(); protocol, rows = fixture(); checks = []
    def check(name, value):
        if not value: raise AssertionError(name)
        checks.append(name)
    result = summarize(protocol, rows)
    check("balanced invented panel passes comparability contract", result["qualification_status"] == "PAIRED_DIAGNOSTIC_READY" and result["valid_pairs"] == 8)
    cold, warm = result["metrics_by_startup_state"]["cold"], result["metrics_by_startup_state"]["warm"]
    check("startup cost reverses invented cold total-runtime direction", cold["mean_total_wall_s_delta_steps4_minus_steps3"] == 8 and warm["mean_total_wall_s_delta_steps4_minus_steps3"] == -2)
    check("startup phases remain separate", cold["mean_startup_wall_s_delta_steps4_minus_steps3"] == 10 and warm["mean_startup_wall_s_delta_steps4_minus_steps3"] == 0)
    check("repeats cluster rather than multiplying game count", cold["game_seed_llm_clusters"] == 2 and cold["valid_pairs"] == 4)
    check("record ordering has no effect", summarize(protocol, list(reversed(rows))) == result)
    mutations = [
        ("different target model", lambda x: x[0]["identity"].update(target_sha=sha("other"))),
        ("different initial observation", lambda x: x[0].update(initial_observation_sha=sha("other"))),
        ("unequal action quota", lambda x: x[0]["budgets"].update(actions=90)),
        ("exceeded output-token budget", lambda x: x[0]["usage"].update(output_tokens=10001)),
        ("intermediate reward without terminal evidence", lambda x: x[0]["evidence"].update(terminal=False)),
        ("unsettled lifecycle", lambda x: x[0]["evidence"].update(settled=False)),
        ("straggler", lambda x: x[0]["evidence"].update(stragglers=1)),
        ("runtime scope mismatch", lambda x: x[0]["evidence"].update(runtime_scope="ready_to_terminal")),
        ("unsubstantiated budget stop", lambda x: x[0]["evidence"].update(stop_reason="budget_exhausted")),
        ("nonfinite reward", lambda x: x[0].update(final_reward=float("nan"))),
        ("overflow-sized numeric usage", lambda x: x[0]["usage"].update(actions=1 << 4096)),
        ("unexpected prompt payload", lambda x: x[0].update(prompt="invented raw text")),
        ("missing arm", lambda x: x.pop()),
        ("duplicate arm", lambda x: x.append(copy.deepcopy(x[0]))),
        ("missing preregistered game", lambda x: x.__setitem__(slice(None), [r for r in x if r["game_key"] != "invented-b"])),
        ("fixed arm order", lambda x: [r.update(period=1 if r["arm"] == "steps4" else 2) for r in x]),
    ]
    for name, mutate in mutations:
        bad = copy.deepcopy(rows); mutate(bad)
        check("hold " + name, summarize(protocol, bad)["qualification_status"] == "HOLD_INCOMPLETE_OR_UNMATCHED")
    bool_protocol = copy.deepcopy(protocol); bool_protocol["budgets"]["actions"] = 1
    bool_rows = copy.deepcopy(rows)
    for row in bool_rows:
        row["budgets"]["actions"] = 1; row["usage"]["actions"] = 1
    bool_rows[0]["budgets"]["actions"] = True
    check("bool quota cannot impersonate integer quota one", summarize(bool_protocol, bool_rows)["qualification_status"] == "HOLD_INCOMPLETE_OR_UNMATCHED")
    check("empty records fail closed", summarize(protocol, [])["qualification_status"] == "HOLD_INCOMPLETE_OR_UNMATCHED")
    check("aggregate excludes private joins", "invented-a" not in json.dumps(result) and "pair_id" not in json.dumps(result))
    check("no automatic strategy adoption or official score", result["strategy_adoption"] == "NO_AUTOMATIC_ADOPTION" and result["official_score"] is None)
    output = {"schema": "invented-arc3-paired-checks-v2", "passed": len(checks), "checks": checks,
        "cpu_seconds": time.process_time() - start, "fixture_only": True,
        "invented_counterbalanced_pairs": result["valid_pairs"],
        "invented_cold_total_runtime_delta_seconds": cold["mean_total_wall_s_delta_steps4_minus_steps3"],
        "invented_warm_total_runtime_delta_seconds": warm["mean_total_wall_s_delta_steps4_minus_steps3"],
        "limits": "All rewards and runtime values are invented fixtures. No model/environment/API calls or campaign performance evidence."}
    with (Path(__file__).resolve().parent / "INVENTED_FIXTURE_CHECKS_V2.json").open("x") as f: json.dump(output, f, indent=2); f.write("\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__": main()
