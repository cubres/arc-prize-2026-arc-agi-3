"""Bounded retrospective audit of post-action visible event snapshots.

Reads JSONL only. Does not run a game, import agent code, infer latent state,
change actions, or estimate the score under an alternative policy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

from repeat_adviser import _action, _grid, _level, visible_digest

MAX_FILES = 32
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
MAX_LINES_PER_FILE = 20000
RECOVERY = frozenset(("RESET", "UNDO"))
FLAGS = ("done", "game_over", "run_complete", "level_completed")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _invalid_number(value):
    raise ValueError("nonfinite JSON number")


def _finite_float(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("nonfinite JSON number")
    return value


def read_records(path):
    """Validate size before and during a read; arbitrary concurrent rewrites
    remain outside this offline audit. Use hash-pinned immutable snapshots."""
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("file bound exceeded")
    total = 0
    with path.open("rb") as stream:
        for line_no in range(1, MAX_LINES_PER_FILE + 2):
            line = stream.readline(MAX_LINE_BYTES + 1)
            if not line:
                break
            if line_no > MAX_LINES_PER_FILE or len(line) > MAX_LINE_BYTES:
                raise ValueError("record/line bound exceeded")
            total += len(line)
            if total > MAX_FILE_BYTES:
                raise ValueError("file grew beyond bound")
            item = json.loads(line, object_pairs_hook=_unique,
                              parse_constant=_invalid_number, parse_float=_finite_float)
            if type(item) is not dict:
                raise ValueError("event must be a JSON object")
            yield item


def _metadata(item):
    board = _grid(item.get("board"))
    level = _level(item.get("level"))
    for flag in FLAGS:
        if flag in item and type(item[flag]) is not bool:
            raise ValueError("terminal markers must be booleans")
    return board, level


def audit_records(records):
    counts = Counter()
    # Seen evidence is per attempt and level. RESET, UNDO, terminal and level
    # changes clear it. Only the immediately previous verdict for a key is
    # counted; this is a description of records, not a guard simulation.
    previous = None
    seen = {}
    last_action_num = 0
    levels2_seen = {}
    for event in records:
        typ = event.get("type")
        if typ == "initial":
            previous = _metadata(event)
            seen.clear(); levels2_seen.clear(); last_action_num = 0
            continue
        if typ != "action":
            continue
        after, after_level = _metadata(event)
        action = _action(event.get("action_display"))
        num = event.get("action_num")
        if type(num) is not int or num <= last_action_num:
            raise ValueError("action numbers must increase inside an attempt")
        last_action_num = num
        counts["action_records"] += 1
        counts["animation_summary_present"] += type(event.get("animation")) is dict
        # The event logger did not preserve complete intermediate grids. A
        # summary or absence of a summary cannot be promoted to complete capture.
        counts["complete_animation_chains_available"] += 0
        if previous is None:
            counts["actions_without_predecessor"] += 1
            previous = (after, after_level)
            continue
        before, before_level = previous
        if len(before) != len(after) or len(before[0]) != len(after[0]):
            counts["dimension_boundaries"] += 1
            seen.clear(); levels2_seen.clear()
            previous = (after, after_level)
            continue
        terminal = any(event.get(flag, False) for flag in FLAGS)
        if action in RECOVERY or terminal or before_level != after_level:
            counts["recovery_terminal_or_level_boundaries"] += 1
            seen.clear(); levels2_seen.clear()
            previous = (after, after_level)
            continue
        key = (before_level, visible_digest(before), action)
        unchanged = before == after
        counts["eligible_same_level_nonterminal_transitions"] += 1
        counts["unchanged_final_visible_frame"] += unchanged
        crop = lambda b: tuple(tuple(row[4:-4]) for row in b[4:-4])
        # Hypothetical border=4 comparison. It does not recreate every active
        # harness condition. Tiny boards are never cropped by this diagnostic.
        if len(before) > 8 and len(before[0]) > 8:
            counts["crop4_same_but_full_frame_changed"] += (crop(before) == crop(after) and not unchanged)
        if key in seen:
            counts["same_visible_key_revisited"] += 1
            counts["revisited_after_previous_unchanged"] += seen[key]
            counts["changed_after_previous_unchanged"] += seen[key] and not unchanged
        seen[key] = unchanged
        if before_level >= 2:
            counts["level2plus_transitions"] += 1
            counts["level2plus_unchanged_final_frame"] += unchanged
            if key in levels2_seen:
                counts["level2plus_revisited_after_unchanged"] += levels2_seen[key]
                counts["level2plus_changed_after_unchanged"] += levels2_seen[key] and not unchanged
            levels2_seen[key] = unchanged
        previous = (after, after_level)
    return dict(counts)


def audit_one(path):
    counts = audit_records(read_records(path))
    # A second pass hashes the exact retained file. Mutation between passes is
    # detected by the caller's source pin, not solved by this helper.
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size,
            "counts": counts}


def audit_files(paths):
    if not 1 <= len(paths) <= MAX_FILES:
        raise ValueError("provide 1..32 files")
    if sum(p.stat().st_size for p in paths) > MAX_TOTAL_BYTES:
        raise ValueError("total input bound exceeded")
    start = time.process_time()
    rows = [audit_one(path) for path in paths]
    if len(set(row["sha256"] for row in rows)) != len(rows):
        raise ValueError("duplicate source streams are not independent evidence")
    counts = Counter()
    for row in rows:
        counts.update(row["counts"])
    # File names, game IDs, boards, actions, prompts and per-game tactics are
    # omitted. Corpus pin hashes sorted SHA256+byte pairs, not local paths.
    pin = hashlib.sha256(json.dumps(sorted((r["sha256"], r["bytes"]) for r in rows),
                                     separators=(",", ":")).encode()).hexdigest()
    return {"schema": "visible_repeat_retrospective_v1", "streams": len(rows),
            "corpus_sha256": pin, "source_bytes": sum(r["bytes"] for r in rows),
            "counts": dict(counts), "cpu_s": time.process_time() - start,
            "scope": "descriptive post-action snapshots; no policy replay or score inference",
            "complete_animation_evidence": "UNAVAILABLE",
            "input_files": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event_files", nargs="+", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit_files(args.event_files), indent=2, sort_keys=True))
