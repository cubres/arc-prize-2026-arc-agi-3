"""Original stdlib-only diagnostic of existing public-demo request receipts.

No games, model, imports from campaign code, network calls, or mutations of
campaign artifacts occur. Same action counters do not imply wasted reasoning.
The aggregate includes all recorded responses, potentially including late output
after a scoring cutoff; it is not a replacement for benchmark accounting.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def analyze(path: Path) -> dict:
    groups: list[dict] = []
    n_responses = 0
    n_missing_usage = 0
    reasons: dict[str, int] = {}
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for raw in stream:
            digest.update(raw)
            record = json.loads(raw)
            if record.get("event") != "response":
                continue
            action = record.get("action")
            usage = record.get("usage", {})
            tokens = usage.get("completion_tokens")
            if not isinstance(action, int) or isinstance(action, bool):
                raise ValueError("Missing integer action counter")
            if tokens is None:
                n_missing_usage += 1
                tokens = 0
            if not isinstance(tokens, int) or isinstance(tokens, bool) or tokens < 0:
                raise ValueError("Invalid recorded completion count")
            if not groups or groups[-1]["action"] != action:
                groups.append({"action": action, "responses": 0, "completion_tokens": 0})
            groups[-1]["responses"] += 1
            groups[-1]["completion_tokens"] += tokens
            n_responses += 1
            reason = str(record.get("finish_reason"))
            reasons[reason] = reasons.get(reason, 0) + 1
    if not n_responses:
        raise ValueError("No recorded response events")
    if sum(group["responses"] for group in groups) != n_responses:
        raise ValueError("Group count does not cover response events")
    return {
        "input_name": path.name,
        "input_bytes": path.stat().st_size,
        "input_sha256": digest.hexdigest(),
        "response_events": n_responses,
        "responses_without_completion_usage": n_missing_usage,
        "recorded_completion_tokens": sum(g["completion_tokens"] for g in groups),
        "additional_responses_at_same_action_counter": sum(g["responses"] - 1 for g in groups),
        "max_responses_at_same_action_counter": max(g["responses"] for g in groups),
        "max_completion_tokens_at_same_action_counter": max(g["completion_tokens"] for g in groups),
        "largest_groups": sorted(groups, key=lambda g: g["completion_tokens"], reverse=True)[:3],
        "finish_reasons": reasons,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    paths = sorted(args.input_dir.glob("*_p0_requests.jsonl"))
    if len(paths) != 10:
        raise ValueError("Expected exactly the ten existing V17 demo streams")
    result = {
        "scope": "retrospective recorded response events from public-demo streams",
        "official_score": None,
        "counterfactual_strategy_gain": None,
        "warning": "Same action counter can include valuable inspection and search; this does not establish waste.",
        "games": [analyze(path) for path in paths],
    }
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"files": len(paths), "output": str(args.output)}))


if __name__ == "__main__":
    main()
