"""Original, local-only three-run panel analyzer. MIT, cubres 2026.

All files are data. This module makes no model, environment, network or process
calls. Supplied authority/pins require independent upstream authentication.
"""
import argparse
import ast
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

ARMS = ("C1", "C2", "T1")
MAX_BYTES = 12_000_000
SHA = re.compile(r"[0-9a-f]{64}\Z")


class ContractError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise ContractError(code)


def numeric(value, integer=False):
    if type(value) not in ((int,) if integer else (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def decode(raw):
    def invalid_constant(_):
        raise ContractError("nonfinite_json_constant")
    return json.loads(raw, object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def bound(spec):
    need(type(spec) is dict and type(spec.get("path")) is str
         and type(spec.get("sha256")) is str and SHA.fullmatch(spec["sha256"]),
         "file_descriptor")
    path = Path(spec["path"])
    need(path.is_file() and not path.is_symlink()
         and 0 < path.stat().st_size <= MAX_BYTES, "file_scope")
    raw = path.read_bytes()
    need(len(raw) <= MAX_BYTES
         and hashlib.sha256(raw).hexdigest() == spec["sha256"], "file_hash")
    if "bytes" in spec:
        need(type(spec["bytes"]) is int and spec["bytes"] == len(raw), "file_bytes")
    return decode(raw), raw


def action_name(action):
    if type(action) is str:
        need(len(action) <= 2048, "action_text_cap")
        try:
            action = ast.literal_eval(action)
        except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
            raise ContractError("action_literal") from None
    need(type(action) is dict and type(action.get("id")) is str
         and 0 < len(action["id"]) <= 64, "action_schema")
    return action["id"]


def token_count(value):
    if value is None:
        return 0
    need(numeric(value) and int(value) == value, "token_count")
    return int(value)


def iso(value):
    need(type(value) is str and 0 < len(value) <= 128, "time_schema")
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ContractError("time_parse") from None


def clock_span(start, end):
    a, b = iso(start), iso(end)
    need((a.tzinfo is None) == (b.tzinfo is None), "time_zone_mismatch")
    elapsed = (b - a).total_seconds()
    need(numeric(elapsed), "time_order")
    return elapsed


def raw_game(row, terminal_states):
    """Reconstruct emitted receipt observations from the retained raw history."""
    need(type(row) is dict and type(row.get("game_id")) is str
         and 0 < len(row["game_id"]) <= 128, "raw_game_id")
    need(row.get("state") in terminal_states, "raw_game_nonterminal")
    score = row.get("final_score")
    need(numeric(score) and score <= 100, "raw_score")
    completed, total = row.get("levels_completed"), row.get("number_of_levels")
    need(numeric(completed, True) and numeric(total, True)
         and 0 < total and completed <= total, "raw_levels")
    history = row.get("history")
    need(type(history) is list and 0 < len(history) <= 100_000, "raw_history")
    names, tokens, clocks = [], [], []
    for item in history:
        need(type(item) is dict, "history_row")
        names.append(action_name(item.get("action")))
        tokens.append(token_count(item.get("generated_tokens")))
        token_count(item.get("uncached_input_tokens"))
        value = item.get("wallclock_seconds")
        need(numeric(value), "history_clock")
        clocks.append(value)
    need(all(b >= a for a, b in zip(clocks, clocks[1:])), "history_clock_order")
    wall = row.get("final_wallclock_seconds")
    need(numeric(wall) and wall >= clocks[-1], "history_final_clock")
    note = row.get("solver_note")
    need(note is None or type(note) is str, "solver_note_schema")
    note_match = re.search(r"tokens=(\d+)", note or "")
    note_tokens = int(note_match.group(1)) if note_match else None
    played = sum(name != "RESET" for name in names)
    need(played > 0, "never_admitted")
    apl = row.get("actions_per_level")
    need(type(apl) is list and all(numeric(v, True) for v in apl), "actions_per_level")
    iso(row.get("started_at"))
    return {"game_id": row["game_id"], "state": row["state"], "score": score,
            "levels_completed": completed, "number_of_levels": total,
            "actions_per_level": apl, "actions": len(history), "tokens": sum(tokens),
            "tokens_solver_note": note_tokens,
            "tokens_per_action": round(sum(tokens) / played, 2),
            "action7_actions": names.count("ACTION7"), "undo_actions": names.count("UNDO"),
            "reset_actions": names.count("RESET"), "played_actions": played,
            "wallclock_s": wall, "started_at": row["started_at"],
            "admitted": True, "never_admitted": False, "admitted_without_actions": False}


def same_number(a, b):
    return numeric(a) and numeric(b) and abs(a - b) <= 1e-6


def receipt_equal(actual, expected):
    need(type(actual) is dict and set(actual) == set(expected), "receipt_game_schema")
    for key, value in expected.items():
        other = actual[key]
        if type(value) is bool:
            need(other is value, "receipt_game_boolean")
        elif type(value) is int:
            need(type(other) is int and other == value, "receipt_game_integer")
        elif type(value) is float:
            need(same_number(other, value), "receipt_game_number")
        else:
            need(type(other) is type(value) and other == value, "receipt_game_value")


def aggregate_check(receipt, rows):
    agg = receipt.get("aggregate")
    need(type(agg) is dict, "aggregate_schema")
    counts = {"games_admitted": len(rows), "games_never_admitted": 0,
              "admitted_without_actions": 0,
              "levels_available_total": sum(r["number_of_levels"] for r in rows),
              "levels_completed_total": sum(r["levels_completed"] for r in rows),
              "played_actions_total": sum(r["played_actions"] for r in rows),
              "tokens_total": sum(r["tokens"] for r in rows),
              "tokens_solver_note_total": sum(r["tokens_solver_note"] or 0 for r in rows),
              "action7_total": sum(r["action7_actions"] for r in rows),
              "undo_total": sum(r["undo_actions"] for r in rows)}
    for key, value in counts.items():
        need(type(agg.get(key)) is int and agg[key] == value, "aggregate_count")
    need(agg.get("never_admitted_ids") == [], "aggregate_never_admitted")
    for key, value in {"mean_score_over_listed": round(statistics.mean(r["score"] for r in rows), 4),
                       "wallclock_max_s": max(r["wallclock_s"] for r in rows),
                       "tokens_per_action": round(counts["tokens_total"] / counts["played_actions_total"], 2)}.items():
        need(same_number(agg.get(key), value), "aggregate_number")


def run_identity(binding, spec, source_raw):
    need(type(binding) is dict and type(spec) is dict
         and type(spec.get("version")) is int and spec["version"] > 0
         and type(binding.get("version")) is int and binding["version"] > 0
         and type(spec.get("native_session_id")) is str
         and spec["native_session_id"].isascii() and spec["native_session_id"].isdigit()
         and int(spec["native_session_id"]) > 0
         and type(binding.get("native_session_id")) is str
         and binding["native_session_id"].isascii() and binding["native_session_id"].isdigit()
         and int(binding["native_session_id"]) > 0, "positive_version_native_id")
    if binding.get("qualification") == "PASS_EXACT_NATIVE_OUTPUT_CAPTURE_ONLY":
        accepted, accepted_raw = bound(spec["files"]["accepted_receipt"])
        need(binding.get("status") == "COMPLETE" and binding.get("ref") == spec["identity"]["id"]
             and binding.get("index_complete") is True and binding.get("missing_required") == [], "capture_status_identity")
        need(type(binding.get("version")) is int and binding["version"] == spec["version"]
             and binding.get("native_session_id") == spec["native_session_id"], "capture_version_native_id")
        need(binding.get("accepted_receipt_sha256") == hashlib.sha256(accepted_raw).hexdigest()
             and accepted.get("result") == "PUSHED" and accepted.get("cells_identical") is True
             and type(accepted.get("version_number")) is int and accepted["version_number"] == spec["version"]
             and accepted.get("ref") == spec["identity"]["id"]
             and accepted.get("expected") == {k: v for k, v in spec["identity"].items() if k != "id"}, "capture_accepted_identity")
        post = accepted.get("postpush")
        need(type(post) is dict and hashlib.sha256(source_raw).hexdigest() == spec["source_sha256"]
             == binding.get("source_sha256") == post.get("source_sha256")
             and type(post.get("source_bytes")) is int and post["source_bytes"] == len(source_raw), "capture_exact_source")
        need({k: post.get("meta", {}).get(k) for k in spec["identity"]} == spec["identity"], "capture_post_identity")
        runtime_identity(post["meta"], spec)
        for name, basename in (("root", "BENCH_ROOT_" + spec["switch_set"] + ".json"),
                               ("receipt", "ARM_" + spec["switch_set"] + "_receipt.json"),
                               ("benchmark", "benchmark.json"), ("report", "v17_report.json")):
            if name in spec["files"]:
                record = binding["inventory"].get(basename)
                file = spec["files"][name]
                need(type(record) is dict and record.get("sha256") == file["sha256"]
                     and type(record.get("bytes")) is int and record["bytes"] == file.get("bytes"), "capture_file_inventory")
        return
    need(binding.get("status") == "COMPLETE" and binding.get("ref") == spec["identity"]["id"]
         and binding.get("identity") == spec["identity"], "terminal_identity")
    need(type(binding.get("version")) is int and binding["version"] == spec["version"], "terminal_version")
    need(type(binding.get("native_session_id")) is str
         and binding["native_session_id"] == spec["native_session_id"]
         and binding["native_session_id"].isdigit(), "terminal_native_id")
    pull = binding.get("terminal_pull")
    need(type(pull) is dict and pull.get("status") == "COMPLETE", "terminal_pull")
    need(hashlib.sha256(source_raw).hexdigest() == spec["source_sha256"]
         == binding.get("exact_version_source_sha256") == pull.get("source_sha256"), "terminal_source")
    need(type(pull.get("source_bytes")) is int and pull["source_bytes"] == len(source_raw), "terminal_source_bytes")
    runtime_identity(pull.get("meta", pull.get("full_api_metadata")), spec)


def runtime_report_observations(report):
    """Record transport diagnostics; these observations never admit a runtime."""
    need(type(report) is dict, "runtime_report_schema")
    result = {key: report.get(key) for key in ("server_when_released", "teardown", "warnings", "fallbacks")}
    timing = report.get("timing")
    if timing is not None:
        need(type(timing) is dict and type(timing.get("per_thread")) is dict
             and len(timing["per_thread"]) <= 500, "report_request_schema")
        counts = {key: timing.get(key) for key in ("records", "completed", "logging_errors")}
        need(all(numeric(value, True) for value in counts.values())
             and counts["completed"] <= counts["records"], "report_request_counts")
        threads = list(timing["per_thread"].values())
        need(all(type(row) is dict and numeric(row.get("requests"), True)
                 and numeric(row.get("errors"), True) and row["errors"] <= row["requests"]
                 for row in threads), "report_thread_counts")
        need(sum(row["requests"] for row in threads) == counts["records"], "report_request_denominator")
        result["logged_request_diagnostics"] = dict(counts,
            request_errors=sum(row["errors"] for row in threads),
            thread_count=len(threads), complete_logged_records=counts["completed"] == counts["records"],
            per_thread_labels_are_not_game_ids=True)
    return result


def runtime_identity(metadata, spec):
    if "runtime_identity" not in spec:
        return
    need(type(metadata) is dict, "runtime_metadata")
    camel = {"machine_shape": "machineShape", "docker_image": "dockerImage",
             "enable_gpu": "enableGpu", "enable_tpu": "enableTpu", "enable_internet": "enableInternet",
             "dataset_sources": "datasetDataSources", "model_sources": "modelDataSources",
             "competition_sources": "competitionDataSources", "is_private": "isPrivate"}
    for key, value in spec["runtime_identity"].items():
        other = metadata.get(key, metadata.get(camel.get(key)))
        need(type(other) is type(value) and other == value, "runtime_identity_drift")


def load_run(spec, panel, terminal_states):
    documents = {name: bound(spec["files"][name]) for name in ("binding", "source", "root", "receipt", "benchmark")}
    binding, source, root, receipt, benchmark = [documents[name][0] for name in documents]
    run_identity(binding, spec, documents["source"][1])
    need(type(source) is dict and type(source.get("cells")) is list, "source_notebook_data")
    need(root.get("schema") == "arc3_screen_pair_root_v1" and root.get("status") == "COMPLETE"
         and root.get("switch_set") == spec["switch_set"]
         and root.get("receipt") == Path(spec["files"]["receipt"]["path"]).name
         and root.get("receipt_sha256") == hashlib.sha256(documents["receipt"][1]).hexdigest(), "root_receipt_link")
    need(receipt.get("schema") == "arc3_screen_pair_session_receipt_v1"
         and receipt.get("worker") == spec["identity"]["id"]
         and receipt.get("switch_set") == spec["switch_set"], "receipt_identity")
    need(receipt.get("benchmark_json_sha256") == hashlib.sha256(documents["benchmark"][1]).hexdigest(), "receipt_benchmark_link")
    need(receipt.get("screen_shape") == spec["screen_shape"]
         and receipt.get("env_flag_values") == spec["env_flag_values"]
         and receipt.get("switch_overrides") == spec["switch_overrides"], "registered_settings")
    shape = receipt["screen_shape"]
    need(type(shape.get("games_listed")) is int and shape["games_listed"] == len(panel)
         and type(shape.get("passes")) is int and shape["passes"] == 1
         and type(benchmark.get("n_passes")) is int and benchmark["n_passes"] == 1, "complete_panel_denominator")
    raw_rows, recorded = benchmark.get("game_runs"), receipt.get("games")
    need(type(raw_rows) is list and type(recorded) is list
         and len(raw_rows) == len(recorded) == len(panel), "complete_panel_rows")
    need([r.get("game_id") for r in raw_rows if type(r) is dict] == panel
         and [r.get("game_id") for r in recorded if type(r) is dict] == panel, "registered_panel_order")
    rows = [raw_game(row, terminal_states) for row in raw_rows]
    for actual, expected in zip(recorded, rows):
        receipt_equal(actual, expected)
    aggregate_check(receipt, rows)
    need(sum(r["number_of_levels"] for r in rows) == spec["total_levels"], "registered_level_denominator")
    elapsed = clock_span(benchmark.get("start_time"), benchmark.get("end_time"))
    timing = receipt.get("timing")
    need(type(timing) is dict, "receipt_timing")
    release = timing.get("released_s_after_notebook_start")
    final = timing.get("seconds_since_notebook_start_at_receipt")
    need(numeric(release) and numeric(final) and release <= final, "receipt_timing_order")
    result = {"games": rows, "native_benchmark_span_seconds": elapsed,
              "release_seconds_since_notebook_start": release,
              "receipt_seconds_since_notebook_start": final,
              "max_reported_history_clock_seconds": max(r["wallclock_s"] for r in rows),
              "cold_first_answer_seconds": None, "isolated_game_cap_proved": False,
              "receipt_sha256": hashlib.sha256(documents["receipt"][1]).hexdigest()}
    if "report" in spec["files"]:
        report, _ = bound(spec["files"]["report"])
        result["runtime_report_observations"] = runtime_report_observations(report)
        result["runtime_report_version_is_not_native_binding"] = True
    return result


def summarize(panel, sessions, z_alpha=1.96, z_power=1.2816, private_rows=False):
    """Describe a fixed complete panel; the MDE formula is only a heuristic."""
    need(type(panel) is list and 2 <= len(panel) <= 500
         and all(type(x) is str and 0 < len(x) <= 128 for x in panel)
         and len(set(panel)) == len(panel), "registered_panel")
    need(type(sessions) is dict and set(sessions) == set(ARMS), "three_exact_arms")
    for arm in ARMS:
        need(type(sessions[arm]) is dict, "session_schema")
        rows = sessions[arm].get("games")
        need(type(rows) is list and len(rows) == len(panel)
             and all(type(r) is dict for r in rows)
             and [r.get("game_id") for r in rows] == panel, "all_panel_members")
        for row in rows:
            need(numeric(row.get("score")) and row["score"] <= 100
                 and type(row.get("played_actions")) is int and row["played_actions"] > 0,
                 "score_or_admission")
    for trio in zip(*(sessions[arm]["games"] for arm in ARMS)):
        need(len({row["number_of_levels"] for row in trio}) == 1, "paired_level_denominator")
    need(numeric(z_alpha) and numeric(z_power) and z_alpha > 0 and z_power > 0, "planning_z_values")
    scores = {arm: [r["score"] for r in sessions[arm]["games"]] for arm in ARMS}
    aa = [b - a for a, b in zip(scores["C1"], scores["C2"])]
    deltas = [t - (a + b) / 2 for a, b, t in zip(scores["C1"], scores["C2"], scores["T1"])]
    mean_aa, sd_aa = statistics.mean(aa), statistics.stdev(aa)
    se_game = math.sqrt(0.75) * sd_aa / math.sqrt(len(panel))
    se_drift = math.sqrt(0.75) * abs(mean_aa)
    heuristic_se = math.hypot(se_game, se_drift)
    leave_one_out = [(sum(deltas) - value) / (len(panel) - 1) for value in deltas]
    result = {"schema": "original-local-three-run-panel-analysis-v1",
              "qualification": "PASS_LOCAL_COMPLETE_PANEL_ANALYSIS_ONLY", "official_score": None,
              "strategy_adoption": "NO_AUTOMATIC_ADOPTION", "panel_items": len(panel),
              "panel_order_sha256": hashlib.sha256(json.dumps(panel, separators=(",", ":")).encode()).hexdigest(),
              "mean_native_scores": {arm: statistics.mean(v) for arm, v in scores.items()},
              "mean_T1_minus_average_controls_points": statistics.mean(deltas),
              "median_paired_delta_points": statistics.median(deltas),
              "paired_wins_ties_losses": {"wins": sum(v > 0 for v in deltas), "ties": sum(v == 0 for v in deltas), "losses": sum(v < 0 for v in deltas)},
              "leave_one_game_out_mean_range_points": [min(leave_one_out), max(leave_one_out)],
              "repeatability": {"C2_minus_C1_mean_points": mean_aa, "per_game_sample_sd_points": sd_aa,
                                "heuristic_game_SE_points": se_game, "heuristic_run_drift_SE_points": se_drift,
                                "heuristic_combined_SE_points": heuristic_se,
                                "registered_formula_MDE_points": (z_alpha + z_power) * heuristic_se,
                                "formula_z_alpha": z_alpha, "formula_z_power": z_power,
                                "inferential_MDE_identified": False, "controls_identical_observed": all(v == 0 for v in aa)},
              "runtime_by_arm": {arm: {k: v for k, v in sessions[arm].items() if k != "games"} for arm in ARMS},
              "limits": ["Local native visible-panel observations are not official competition scores or hidden-game evidence.",
                         "Complete fixed panel is retained; no failing games are dropped and no successful-game subset is scored.",
                         "Two sequential controls cannot identify a run-level variance distribution; stochastic seeds, dates and interference can matter.",
                         "The registered MDE combines game variation and observed run drift heuristically; it is not a calibrated significance test or power guarantee.",
                         "A small continuation threshold is a budget filter. It does not establish scientific adoption.",
                         "Leave-one-game-out ranges are sensitivity checks, not confidence intervals for this fixed panel.",
                         "Release timing is not measured cold first-answer readiness; cumulative history clocks do not prove isolated per-game admission caps.",
                         "Local byte pins require independent upstream source/native identity authority; this utility never authenticates remotely."]}
    if private_rows:
        result["private_per_game"] = [{"game_id": key, "C1": a, "C2": b, "T1": t,
                                       "T1_minus_average_controls": d, "C2_minus_C1": noise}
                                      for key, a, b, t, d, noise in zip(panel, scores["C1"], scores["C2"], scores["T1"], deltas, aa)]
    return result


def analyze(contract, private_rows=False):
    need(type(contract) is dict and contract.get("schema") == "original-three-run-panel-contract-v1", "contract_schema")
    panel = contract.get("panel")
    need(type(panel) is list and 2 <= len(panel) <= 500
         and all(type(x) is str and 0 < len(x) <= 128 for x in panel)
         and len(set(panel)) == len(panel), "registered_panel")
    states = contract.get("terminal_states")
    need(type(states) is list and bool(states) and all(type(v) is str and bool(v) for v in states), "terminal_states")
    specs = contract.get("runs")
    need(type(specs) is dict and set(specs) == set(ARMS), "run_specs")
    need(specs["C1"]["source_sha256"] == specs["C2"]["source_sha256"], "controls_source_mismatch")
    for field in ("identity", "screen_shape", "env_flag_values", "switch_overrides", "total_levels"):
        need(specs["C1"][field] == specs["C2"][field], "controls_settings_mismatch")
    if any("runtime_identity" in spec for spec in specs.values()):
        need(all("runtime_identity" in spec for spec in specs.values())
             and specs["C1"]["runtime_identity"] == specs["C2"]["runtime_identity"]
             == specs["T1"]["runtime_identity"], "paired_runtime_mismatch")
    sessions = {arm: load_run(specs[arm], panel, states) for arm in ARMS}
    return summarize(panel, sessions, contract.get("z_alpha", 1.96), contract.get("z_power", 1.2816), private_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--private-rows", action="store_true")
    args = parser.parse_args()
    need(args.output.suffix == ".json", "output_type")
    try:
        contract, raw = bound({"path": str(args.contract), "sha256": args.contract_sha256})
        result = analyze(contract, args.private_rows)
        result["contract_sha256"] = hashlib.sha256(raw).hexdigest()
    except (ContractError, KeyError, TypeError, ValueError, OSError, RecursionError, AttributeError, OverflowError) as exc:
        result = {"schema": "original-local-three-run-panel-analysis-v1", "qualification": "HOLD_LOCAL_RECEIPT_CONTRACT",
                  "official_score": None, "strategy_adoption": "NO_AUTOMATIC_ADOPTION",
                  "failure": str(exc) if type(exc) is ContractError else type(exc).__name__}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(result["qualification"])
    return 0 if result["qualification"] == "PASS_LOCAL_COMPLETE_PANEL_ANALYSIS_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
