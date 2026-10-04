"""Original ARC3 public-game evidence exporter; never a submission writer."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


def canonical_sha256(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def collect_terminal_evidence(benchmark_bytes: bytes, expected_ids: list[str], *, arm: str):
    """Bind actual scores/actions/states to every frozen game, including cancellations."""
    benchmark = json.loads(benchmark_bytes)
    if len(expected_ids) != 25 or len(set(expected_ids)) != 25:
        raise ValueError("Expected-game contract must contain exactly 25 unique IDs.")
    runs = benchmark.get("game_runs")
    if not isinstance(runs, list) or len(runs) != 25:
        raise ValueError("Actual benchmark must contain all 25 game runs.")
    ids = [run.get("game_id") for run in runs]
    if ids != expected_ids or len(set(ids)) != 25:
        raise ValueError("Actual run IDs/order differ from the frozen public panel.")
    if benchmark.get("n_passes") != 1 or benchmark.get("game_weights") is not None:
        raise ValueError("One pass and uniform game weights are required.")
    rows = []
    for index, run in enumerate(runs):
        state = run.get("state")
        score = run.get("final_score")
        history = run.get("history")
        levels = run.get("levels_completed")
        total_levels = run.get("number_of_levels")
        if state not in {"won", "gave_up", "cancelled", "crashed"}:
            raise ValueError(f"Nonterminal state at {ids[index]}: {state!r}")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise ValueError(f"Missing/nonfinite actual final score at {ids[index]}")
        if not isinstance(history, list):
            raise ValueError(f"Missing actual history at {ids[index]}")
        for entry in history:
            if not isinstance(entry, dict) or not isinstance(entry.get("action"), dict):
                raise ValueError(f"Missing action in actual history at {ids[index]}")
            if not isinstance(entry["action"].get("id"), str):
                raise ValueError(f"Missing engine action ID at {ids[index]}")
        if type(levels) is not int or type(total_levels) is not int or not 0 <= levels <= total_levels:
            raise ValueError(f"Invalid actual level counters at {ids[index]}")
        rows.append({
            "panel_index": index, "arm": arm, "game_id": run["game_id"],
            "state": state, "final_score": float(score),
            "levels_completed": levels, "number_of_levels": total_levels,
            "history_action_count": len(history), "history_sha256": canonical_sha256(history),
            "actual_game_run_sha256": canonical_sha256(run),
            "source_run_index": index,
        })
    actions = sum(row["history_action_count"] for row in rows)
    if actions <= 0:
        raise ValueError("A zero-action output cannot attest a real solver run.")
    counts = {state: sum(row["state"] == state for row in rows)
              for state in ("won", "gave_up", "cancelled", "crashed")}
    return {
        "schema": "arc3_actual_terminal_evidence_v1", "arm": arm,
        "purpose": "LOCAL_REUSED_PUBLIC25_DIAGNOSTIC_NEVER_KAGGLE_SUBMISSION",
        "official_score": False, "independent_quality_validation": False,
        "benchmark_sha256": hashlib.sha256(benchmark_bytes).hexdigest(),
        "expected_ids_sha256": canonical_sha256(expected_ids),
        "panel_denominator": 25, "pass_count": 1,
        "state_counts": counts, "history_action_count": actions,
        "completed_levels": sum(row["levels_completed"] for row in rows),
        "available_levels": sum(row["number_of_levels"] for row in rows),
        "uniform_mean_actual_final_score": sum(row["final_score"] for row in rows) / 25,
        "no_crashed_runs": counts["crashed"] == 0,
        "usage_warning": "Final summary usage fields can be zero; no throughput claim is inferred.",
        "games": rows,
    }


def export_terminal_evidence(benchmark_path, expected_ids, output_dir, *, arm):
    benchmark_path, output_dir = Path(benchmark_path), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"Evidence directory already exists: {output_dir}")
    evidence = collect_terminal_evidence(benchmark_path.read_bytes(), list(expected_ids), arm=arm)
    output_dir.mkdir(parents=True, exist_ok=False)
    target = output_dir / "terminal_games.json"
    target.write_text(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
    receipt = {
        "benchmark_path": str(benchmark_path), "benchmark_sha256": evidence["benchmark_sha256"],
        "terminal_games_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "actual_rows": 25, "no_submission_file_written": True,
        "eligibility": "MECHANICS_COMPLETE" if evidence["no_crashed_runs"] else "CRASHED_RUNS_RETAINED",
    }
    (output_dir / "terminal_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return evidence, receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--arm", required=True)
    args = parser.parse_args()
    protocol = json.loads(Path(args.protocol).read_text())
    evidence, receipt = export_terminal_evidence(args.benchmark, protocol["public_game_ids"],
                                                args.output, arm=args.arm)
    print(json.dumps(receipt, sort_keys=True))
