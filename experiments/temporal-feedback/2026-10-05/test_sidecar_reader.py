"""Standard-library CPU fixtures; no engine/model/network/notebook execution.

Set PYTHONPATH to the unchanged original watermark module directory. Optional
ARC3_NATIVE_METADATA_DIR enables two read-only, exact-hash native artifact tests.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import patch

import sidecar_reader as reader
from sidecar_reader import Limits, Provenance, SidecarContractError, parse_sidecar

PROVENANCE = Provenance("prvsiyan/zz-gpuchk-899422", 8, 355288162, "control4", "individual-run-a", "test-public-game", 0)
SENTINEL_BOARD = "SYNTHETIC_PRIVATE_BOARD_SENTINEL"
SENTINEL_TRANSCRIPT = "SYNTHETIC_PRIVATE_TRANSCRIPT_SENTINEL"


def initial():
    return {"board": [[0]], "board_ascii": SENTINEL_BOARD, "score": 0,
            "state": "NOT_FINISHED", "level": 1, "run_status": "playing",
            "type": "initial", "title": "Initial State", "action_num": 0,
            "analysis_step": None, "action_display": "RESET", "reward": 0.0}


def action(number=1, **changes):
    row = {**initial(), "type": "action", "title": f"Action {number}", "action_num": number,
           "analysis_step": 1, "action_name": "ACTION1", "action_display": "UP",
           "board_changed": False, "done": False, "level_completed": False,
           "game_over": False, "run_complete": False, "batch_index": 1, "batch_size": 1}
    return {**row, **changes}


def analysis(number=0):
    return {k: v for k, v in {**initial(), "type": "analysis", "title": "Analysis",
                              "action_num": number, "analysis_step": 1,
                              "transcript": SENTINEL_TRANSCRIPT}.items() if k not in ("action_display", "reward")}


def experiment(number=0):
    return {"type": "experiment", "experiment": "animation-awareness", "title": "Counters",
            "action_num": number, "analysis_step": 1, "animation_awareness": True, "counters": {}}


def viewer(rows, **changes):
    last = next((row for row in reversed(rows) if row["type"] == "action"), rows[-1])
    metadata = {k: v for k, v in last.items() if k not in ("board", "board_ascii", "transcript")}
    return {"game_id": PROVENANCE.game_id, "agent_name": "duck-harness", "status": "cancelled",
            "pass_index": 0, "pass_label": "0", "eventCount": len(rows), "lastEvent": metadata,
            "viewer_steps": [], "replay_url": "synthetic.html", "levels_completed": 0,
            "total_levels": 1, "actions_per_level": [], "final_score": 0.0, **changes}


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="arc3-retained-scalar-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)

    def files(self, rows, v=None, raw=None):
        side = self.folder / "events.jsonl"
        view = self.folder / "viewer.json"
        side.write_bytes(raw if raw is not None else ("\n".join(json.dumps(r) for r in rows) + "\n").encode())
        view.write_text(json.dumps(viewer(rows) if v is None else v))
        return side, view, hashlib.sha256(side.read_bytes()).hexdigest(), hashlib.sha256(view.read_bytes()).hexdigest()

    def parse(self, rows, v=None, **kwargs):
        side, view, hs, hv = self.files(rows, v)
        return parse_sidecar(side, view, expected_sidecar_sha256=hs, expected_viewer_sha256=hv,
                             provenance=PROVENANCE, **kwargs)

    def test_scalar_events_only_and_initial_reset_is_excluded(self):
        result = self.parse([initial(), analysis(), action(), analysis(1), experiment(1)])
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].revision, 1)
        self.assertEqual(result.events[0].action, "ACTION1")
        self.assertEqual(result.raw_event_count, 5)
        self.assertEqual(result.initial_anchor_count, 1)
        for secret in (SENTINEL_BOARD, SENTINEL_TRANSCRIPT, "board_ascii", "transcript"):
            self.assertNotIn(secret, repr(result))
            self.assertNotIn(secret, json.dumps(result.scalar_receipt()))

    def test_zero_actions_initial_and_fallback_metadata(self):
        for rows in ([initial()], [initial(), analysis()], [initial(), analysis(), experiment()]):
            with self.subTest(count=len(rows)):
                result = self.parse(rows)
                self.assertEqual(result.events, ())
                self.assertEqual(result.initial_anchor_count, 1)

    def test_real_static_actions_and_death_reset_and_win_flags(self):
        rows = [initial(), action(), action(2, state="GAME_OVER", game_over=True),
                action(3, action_name="RESET", action_display="RESET"),
                action(4, state="WIN", done=True, run_complete=True)]
        result = self.parse(rows)
        self.assertEqual([e.revision for e in result.events], [1, 2, 3, 4])
        self.assertTrue(result.events[1].game_over)
        self.assertEqual(result.events[2].action, "RESET")
        self.assertFalse(result.events[2].game_over)
        self.assertTrue(result.events[3].run_complete)

    def test_both_expected_file_hashes_are_required_before_json(self):
        side, view, hs, hv = self.files([initial(), action()])
        for a, b in (("0"*64, hv), (hs, "0"*64), ("bad", hv)):
            with self.subTest(a=a[:4], b=b[:4]), self.assertRaises(SidecarContractError):
                parse_sidecar(side, view, expected_sidecar_sha256=a, expected_viewer_sha256=b, provenance=PROVENANCE)

    def test_anchor_missing_duplicate_or_fabricated_action_zero_refused(self):
        cases = [[action()], [initial(), initial()], [initial(), action(0)],
                 [{**initial(), "analysis_step": 0}], [{**initial(), "action_display": "ACTION1"}]]
        for rows in cases:
            with self.subTest(case=rows[0]["type"]), self.assertRaises(SidecarContractError):
                self.parse(rows)

    def test_partial_gap_duplicate_and_nonaction_revision_refused(self):
        for rows in ([initial(), action(2)], [initial(), action(), action()],
                     [initial(), action(), action(3)], [initial(), action(), analysis(0)]):
            with self.subTest(count=len(rows)), self.assertRaises(SidecarContractError):
                self.parse(rows)

    def test_exact_boolean_integer_and_state_consistency(self):
        mutations = [{"done": 0}, {"game_over": 1}, {"run_complete": "false"},
                     {"level_completed": None}, {"board_changed": 1}, {"action_num": True},
                     {"level": True}, {"state": "WIN"}, {"done": True},
                     {"state": "GAME_OVER"}, {"game_over": True},
                     {"state": "WIN", "done": True, "run_complete": True, "level_completed": True},
                     {"state": "NOT_PLAYED", "level_completed": True}, {"state": "UNKNOWN"}]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(SidecarContractError):
                self.parse([initial(), action(**mutation)])

    def test_viewer_scope_count_last_event_and_historical_status(self):
        rows = [initial(), action()]
        for mutation in ({"game_id": "another-game"}, {"pass_index": True}, {"pass_index": 1},
                         {"pass_label": 0}, {"pass_label": "1"}, {"eventCount": True}, {"eventCount": 1},
                         {"lastEvent": {**viewer(rows)["lastEvent"], "action_num": 9}}):
            with self.subTest(mutation=mutation), self.assertRaises(SidecarContractError):
                self.parse(rows, viewer(rows, **mutation))
        # Cancelled final status need not equal last historical action's playing.
        self.assertEqual(len(self.parse(rows, viewer(rows, status="cancelled")).events), 1)

    def test_viewer_last_event_preserves_exact_boolean_and_number_types(self):
        rows = [initial(), action()]
        for name, replacement in (("done", 0), ("game_over", 0), ("run_complete", 0),
                                  ("level_completed", 0), ("action_num", True), ("score", 0.0)):
            broken = viewer(rows)
            broken["lastEvent"] = {**broken["lastEvent"], name: replacement}
            with self.subTest(name=name), self.assertRaises(SidecarContractError):
                self.parse(rows, broken)

    def test_fifo_without_writer_is_rejected_before_a_blocking_read(self):
        fifo = self.folder / "nonregular.pipe"
        os.mkfifo(fifo)
        module_dir = str(Path(__file__).resolve().parent)
        script = ("import sys; sys.path.insert(0, sys.argv[2]); "
                  "from sidecar_reader import _bounded_bytes, SidecarContractError\n"
                  "try:\n _bounded_bytes(sys.argv[1], 100)\n"
                  "except SidecarContractError:\n print('NONREGULAR_REFUSED')\n"
                  "else:\n raise AssertionError('FIFO was accepted')\n")
        completed = subprocess.run([sys.executable, "-c", script, str(fifo), module_dir],
                                   capture_output=True, text=True, timeout=2)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.strip(), "NONREGULAR_REFUSED")

    def test_external_identity_is_caller_attested_and_scope_is_unique(self):
        rows = [initial(), action()]
        side, view, hs, hv = self.files(rows)
        scopes = set()
        for p in (PROVENANCE, replace(PROVENANCE, arm="image10"), replace(PROVENANCE, session_id=355288163),
                  replace(PROVENANCE, run_token="individual-run-b"), replace(PROVENANCE, version=9)):
            result = parse_sidecar(side, view, expected_sidecar_sha256=hs, expected_viewer_sha256=hv, provenance=p)
            scopes.add(result.scope)
            self.assertIn("not internal fields", result.scalar_receipt()["external_identity_binding"])
            self.assertEqual(result.scalar_receipt()["external_provenance"], asdict(p))
        self.assertEqual(len(scopes), 5)

    def test_unknown_event_type_fields_and_partial_json_refused(self):
        for row in ({**action(), "type": "mystery"}, {**action(), "executed": False}, {**action(), "answer": "not allowed"}):
            with self.subTest(kind=row["type"]), self.assertRaises(SidecarContractError):
                self.parse([initial(), row])
        rows = [initial()]
        for raw in (b'{"secret":"' + SENTINEL_TRANSCRIPT.encode(), b'{}\n\n'):
            side, view, hs, hv = self.files(rows, raw=raw)
            with self.assertRaises(SidecarContractError) as error:
                parse_sidecar(side, view, expected_sidecar_sha256=hs, expected_viewer_sha256=hv, provenance=PROVENANCE)
            self.assertNotIn(SENTINEL_TRANSCRIPT, str(error.exception))

    def test_duplicate_keys_nonfinite_numbers_and_invalid_utf8_refused(self):
        rows = [initial()]
        ordinary = json.dumps(initial()).encode()
        for raw in (ordinary.replace(b'"action_num": 0', b'"action_num": 0, "action_num": 0'),
                    ordinary.replace(b'"reward": 0.0', b'"reward": NaN'),
                    ordinary.replace(b'"reward": 0.0', b'"reward": 1e999'), b'\xff'):
            side, view, hs, hv = self.files(rows, raw=raw)
            with self.subTest(size=len(raw)), self.assertRaises(SidecarContractError):
                parse_sidecar(side, view, expected_sidecar_sha256=hs, expected_viewer_sha256=hv, provenance=PROVENANCE)

    def test_file_line_event_and_hard_upper_bounds(self):
        rows = [initial(), action()]
        for limits in (Limits(file_bytes=64, line_bytes=64), Limits(line_bytes=64), Limits(events=1),
                       Limits(file_bytes=9*1024*1024), Limits(events=True)):
            with self.subTest(limits=limits), self.assertRaises(SidecarContractError):
                self.parse(rows, limits=limits)

    def test_symlink_and_growth_during_read_are_refused_without_overread(self):
        side, view, hs, hv = self.files([initial(), action()])
        link = self.folder / "linked.jsonl"
        link.symlink_to(side)
        with self.assertRaises(SidecarContractError):
            parse_sidecar(link, view, expected_sidecar_sha256=hs, expected_viewer_sha256=hv, provenance=PROVENANCE)
        real_read = reader.os.read
        original_size = side.stat().st_size
        received = []
        def grow_after_read(descriptor, count):
            data = real_read(descriptor, count)
            received.append(len(data))
            if len(received) == 1:
                with side.open("ab") as output:
                    output.write(b"x" * 100)
            return data
        with patch.object(reader.os, "read", side_effect=grow_after_read), self.assertRaises(SidecarContractError):
            parse_sidecar(side, view, expected_sidecar_sha256=hs, expected_viewer_sha256=hv, provenance=PROVENANCE)
        self.assertLessEqual(sum(received), original_size)


@unittest.skipUnless(os.environ.get("ARC3_NATIVE_METADATA_DIR"), "optional exact native sidecar pair not supplied")
class RetainedNativeTests(unittest.TestCase):
    def verify(self, arm, count, raw_count, side_hash, viewer_hash):
        folder = Path(os.environ["ARC3_NATIVE_METADATA_DIR"]) / arm / "artifacts"
        p = replace(PROVENANCE, arm=arm, game_id="tu93-0768757b", run_token="native-v8-resolution-pair")
        result = parse_sidecar(folder/"tu93-0768757b_p0_events.jsonl", folder/"tu93-0768757b_p0_viewer_data.json",
            expected_sidecar_sha256=side_hash, expected_viewer_sha256=viewer_hash, provenance=p)
        self.assertEqual(len(result.events), count)
        self.assertEqual(result.raw_event_count, raw_count)
        self.assertEqual([e.revision for e in result.events], list(range(1, count+1)))
        self.assertTrue(result.events[21].game_over)
        self.assertEqual(result.events[22].action, "RESET")
        self.assertFalse(result.events[22].game_over)
        self.assertFalse(result.events[22].run_complete)

    def test_actual_control4_all34_actions(self):
        self.verify("control4",34,51,"c118c17e0d8921f71052572ce4fad8444316431114477b077c5f76d6c830034d","42321ecdbea37d09b8cd97ee4845c6d791e01ca21a34eb24f08fc59896b56055")

    def test_actual_image10_all39_actions(self):
        self.verify("image10",39,58,"b88a7173ad8837cf2b350fbe401166681e3c5ec50e352f58983b30aa9f4db4e2","6461cfff6d7a4dc45261d6184b5ddd668d3f3da4961e46dd3ffcc2e207718314")


if __name__ == "__main__":
    unittest.main(verbosity=2)
