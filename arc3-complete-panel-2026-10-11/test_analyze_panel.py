"""Invented evidence controls; no competition, model or environment execution."""
import copy
import contextlib
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import analyze_panel as a


@contextlib.contextmanager
def retained_directory():
    """Keep every invented record for inspection; no fixture cleanup."""
    parent = Path(__file__).resolve().parent / "PRIVATE_TEST_FIXTURES"
    parent.mkdir(exist_ok=True)
    yield tempfile.mkdtemp(prefix="invented-records-", dir=parent)


def fake_row(key, score=10.0):
    return {"game_id": key, "state": "gave_up", "final_score": score,
            "levels_completed": 1, "number_of_levels": 4, "actions_per_level": [2],
            "started_at": "2020-01-01T00:00:01Z", "final_wallclock_seconds": 3.0,
            "solver_note": "step tokens=5; step tokens=7",
            "history": [{"action": {"id": "RESET"}, "generated_tokens": 2,
                         "uncached_input_tokens": 0, "wallclock_seconds": 1.0},
                        {"action": {"id": "ACTION7"}, "generated_tokens": 5,
                         "uncached_input_tokens": 0, "wallclock_seconds": 2.0},
                        {"action": "{'id': 'UNDO'}", "generated_tokens": 7,
                         "uncached_input_tokens": 0, "wallclock_seconds": 3.0}]}


def aggregate(rows):
    return {"games_admitted": len(rows), "games_never_admitted": 0, "admitted_without_actions": 0,
            "levels_available_total": sum(r["number_of_levels"] for r in rows),
            "levels_completed_total": sum(r["levels_completed"] for r in rows),
            "played_actions_total": sum(r["played_actions"] for r in rows),
            "tokens_total": sum(r["tokens"] for r in rows),
            "tokens_solver_note_total": sum(r["tokens_solver_note"] or 0 for r in rows),
            "action7_total": len(rows), "undo_total": len(rows), "never_admitted_ids": [],
            "mean_score_over_listed": round(sum(r["score"] for r in rows) / len(rows), 4),
            "wallclock_max_s": 3.0, "tokens_per_action": 7.0}


def fixture(directory):
    panel = ["invented-circle", "invented-square", "invented-wave", "invented-dot"]
    identity = {"id": "invented/bench", "id_no": 7, "title": "Invented bench", "code_file": "example.ipynb"}
    source = {"cells": []}; source_sha = hashlib.sha256(json.dumps(source).encode()).hexdigest()
    runs = {}
    for arm, values in {"C1": [10., 20., 30., 40.], "C2": [12., 19., 33., 38.], "T1": [15., 25., 35., 45.]}.items():
        raw_rows = [fake_row(k, value) for k, value in zip(panel, values)]
        rows = [a.raw_game(row, ["won", "gave_up"]) for row in raw_rows]
        switch = "B" if arm == "T1" else "A"
        shape = {"games_listed": len(panel), "passes": 1, "concurrency": 2}
        bm = {"n_passes": 1, "start_time": "2020-01-01T00:00:00Z",
              "end_time": "2020-01-01T00:00:05Z", "game_runs": raw_rows}
        docs = {"source": source, "benchmark": bm}
        files = {}
        def put(name, value):
            path = directory / (arm + "_" + name + ".json")
            raw = json.dumps(value).encode(); path.write_bytes(raw)
            files[name] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        for name, value in docs.items(): put(name, value)
        receipt = {"schema": "arc3_screen_pair_session_receipt_v1", "worker": identity["id"],
                   "switch_set": switch, "benchmark_json_sha256": files["benchmark"]["sha256"],
                   "screen_shape": shape, "env_flag_values": {}, "switch_overrides": {},
                   "games": rows, "aggregate": aggregate(rows),
                   "timing": {"released_s_after_notebook_start": 2., "seconds_since_notebook_start_at_receipt": 7.}}
        put("receipt", receipt)
        put("root", {"schema": "arc3_screen_pair_root_v1", "status": "COMPLETE", "switch_set": switch,
                     "receipt": Path(files["receipt"]["path"]).name, "receipt_sha256": files["receipt"]["sha256"]})
        put("binding", {"status": "COMPLETE", "ref": identity["id"], "identity": identity, "version": 2,
                        "native_session_id": "123", "exact_version_source_sha256": source_sha,
                        "terminal_pull": {"status": "COMPLETE", "source_sha256": source_sha,
                                          "source_bytes": files["source"]["bytes"]}})
        runs[arm] = {"identity": identity, "version": 2, "native_session_id": "123", "source_sha256": source_sha,
                     "switch_set": switch, "screen_shape": shape, "env_flag_values": {}, "switch_overrides": {},
                     "total_levels": 16, "files": files}
    return {"schema": "original-three-run-panel-contract-v1", "panel": panel,
            "terminal_states": ["won", "gave_up"], "runs": runs}


class EvidenceControls(unittest.TestCase):
    def test_complete_invented_pipeline_and_private_opt_in(self):
        with retained_directory() as temp:
            contract = fixture(Path(temp)); out = a.analyze(contract)
            self.assertEqual(out["qualification"], "PASS_LOCAL_COMPLETE_PANEL_ANALYSIS_ONLY")
            self.assertAlmostEqual(out["mean_T1_minus_average_controls_points"], 4.75)
            self.assertIsNone(out["official_score"])
            self.assertNotIn("private_per_game", out)
            self.assertFalse(out["repeatability"]["inferential_MDE_identified"])
            self.assertEqual(len(a.analyze(contract, True)["private_per_game"]), 4)

    def test_raw_schema_negative_controls(self):
        alterations = [lambda r: r.update(final_score=float("inf")), lambda r: r.update(final_score=True),
                       lambda r: r.update(state="active"), lambda r: r.update(number_of_levels=True),
                       lambda r: r.update(levels_completed=5), lambda r: r.update(final_wallclock_seconds=1.0),
                       lambda r: r["history"][2].update(wallclock_seconds=.5),
                       lambda r: r["history"][1].update(generated_tokens=3.5),
                       lambda r: r["history"][1].update(generated_tokens=True),
                       lambda r: [h.update(action={"id": "RESET"}) for h in r["history"]],
                       lambda r: r["history"][1].update(action="__import__('not_a_module')"),
                       lambda r: r.update(started_at="bad-time")]
        for mutate in alterations:
            with self.subTest(mutate=mutate):
                row = fake_row("invented"); mutate(row)
                with self.assertRaises(a.ContractError): a.raw_game(row, ["won", "gave_up"])

    def test_repeated_json_keys_and_nonfinite_constants(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(a.ContractError): a.decode(raw)

    def test_registered_aggregate_mean_rounding(self):
        rows = [a.raw_game(fake_row("invented-a", 1.234567), ["gave_up"]),
                a.raw_game(fake_row("invented-b", 2.345678), ["gave_up"])]
        agg = aggregate(rows)
        a.aggregate_check({"aggregate": agg}, rows)
        agg["mean_score_over_listed"] += .001
        with self.assertRaises(a.ContractError): a.aggregate_check({"aggregate": agg}, rows)

    def test_integrity_and_native_identity_fail_closed(self):
        with retained_directory() as temp:
            contract = fixture(Path(temp))
            for field, bad in (("version", True), ("native_session_id", "999"), ("source_sha256", "0" * 64)):
                c = copy.deepcopy(contract); c["runs"]["T1"][field] = bad
                with self.assertRaises(a.ContractError): a.analyze(c)
            c = copy.deepcopy(contract); c["runs"]["T1"]["files"]["receipt"]["sha256"] = "0" * 64
            with self.assertRaises(a.ContractError): a.analyze(c)

    def test_panel_and_settings_fail_closed(self):
        with retained_directory() as temp:
            contract = fixture(Path(temp))
            mutations = [lambda c: c["panel"].pop(), lambda c: c["panel"].reverse(),
                         lambda c: c["panel"].append(c["panel"][0]),
                         lambda c: c["runs"]["C2"].update(env_flag_values={"changed": 1}),
                         lambda c: c["runs"]["T1"].update(total_levels=15),
                         lambda c: c["runs"].pop("C2")]
            for mutate in mutations:
                c = copy.deepcopy(contract); mutate(c)
                with self.assertRaises(a.ContractError): a.analyze(c)

    def test_mde_is_heuristic_even_for_identical_controls(self):
        panel = ["invented-a", "invented-b"]
        rows = [a.raw_game(fake_row(k), ["gave_up"]) for k in panel]
        sessions = {arm: {"games": copy.deepcopy(rows)} for arm in a.ARMS}
        out = a.summarize(panel, sessions)
        self.assertEqual(out["repeatability"]["registered_formula_MDE_points"], 0)
        self.assertFalse(out["repeatability"]["inferential_MDE_identified"])
        self.assertEqual(out["strategy_adoption"], "NO_AUTOMATIC_ADOPTION")

    def test_first_note_token_semantics_and_null_note(self):
        first = a.raw_game(fake_row("invented"), ["gave_up"])
        self.assertEqual(first["tokens_solver_note"], 5)
        row = fake_row("invented"); row["solver_note"] = None
        absent = a.raw_game(row, ["gave_up"])
        self.assertIsNone(absent["tokens_solver_note"])
        a.aggregate_check({"aggregate": aggregate([first, absent])}, [first, absent])

    def test_request_diagnostics_are_observations(self):
        report = {"warnings": [], "fallbacks": [], "timing": {
            "records": 7, "completed": 7, "logging_errors": 0,
            "per_thread": {"invented-thread": {"requests": 7, "errors": 2}}}}
        counts = a.runtime_report_observations(report)["logged_request_diagnostics"]
        self.assertEqual(counts["request_errors"], 2)
        self.assertTrue(counts["complete_logged_records"])
        self.assertTrue(counts["per_thread_labels_are_not_game_ids"])
        report["timing"]["completed"] = 6
        self.assertFalse(a.runtime_report_observations(report)["logged_request_diagnostics"]["complete_logged_records"])
        for mutate in (lambda r: r["timing"].update(records=True),
                       lambda r: r["timing"].update(records=8),
                       lambda r: r["timing"]["per_thread"]["invented-thread"].update(errors=8)):
            invalid = copy.deepcopy(report); mutate(invalid)
            with self.assertRaises(a.ContractError): a.runtime_report_observations(invalid)

    def test_malformed_session_and_huge_aggregate_numbers_fail_closed(self):
        panel = ["invented-a", "invented-b"]
        rows = [a.raw_game(fake_row(k), ["gave_up"]) for k in panel]
        for malformed in (None, [None, None]):
            sessions = {arm: {"games": copy.deepcopy(rows)} for arm in a.ARMS}
            sessions["T1"] = malformed if malformed is None else {"games": malformed}
            with self.assertRaises(a.ContractError): a.summarize(panel, sessions)
        self.assertFalse(a.same_number(10 ** 1000, 1.0))
        self.assertFalse(a.same_number(True, 1.0))

    def test_exact_capture_authority_branch_and_inventory_drift(self):
        with retained_directory() as temp:
            contract = fixture(Path(temp)); spec = contract["runs"]["T1"]
            source_raw = Path(spec["files"]["source"]["path"]).read_bytes()
            accepted = {"result": "PUSHED", "ref": spec["identity"]["id"], "version_number": 2,
                        "cells_identical": True, "expected": {k: v for k, v in spec["identity"].items() if k != "id"},
                        "postpush": {"source_sha256": spec["source_sha256"], "source_bytes": len(source_raw), "meta": spec["identity"]}}
            path = Path(temp) / "invented_accepted.json"; raw = json.dumps(accepted).encode(); path.write_bytes(raw)
            spec["files"]["accepted_receipt"] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
            capture = {"qualification": "PASS_EXACT_NATIVE_OUTPUT_CAPTURE_ONLY", "status": "COMPLETE",
                       "ref": spec["identity"]["id"], "version": 2, "native_session_id": "123",
                       "index_complete": True, "missing_required": [], "source_sha256": spec["source_sha256"],
                       "accepted_receipt_sha256": hashlib.sha256(raw).hexdigest(), "inventory": {}}
            for key, name in (("root", "BENCH_ROOT_B.json"), ("receipt", "ARM_B_receipt.json"), ("benchmark", "benchmark.json")):
                capture["inventory"][name] = {k: spec["files"][key][k] for k in ("bytes", "sha256")}
            a.run_identity(capture, spec, source_raw)
            for bad in (None, "", "0", "abc", True):
                invalid = copy.deepcopy(capture); invalid_spec = copy.deepcopy(spec)
                invalid["native_session_id"] = invalid_spec["native_session_id"] = bad
                with self.assertRaises(a.ContractError): a.run_identity(invalid, invalid_spec, source_raw)
            for bad in (0, True, -1):
                invalid = copy.deepcopy(capture); invalid_spec = copy.deepcopy(spec)
                invalid["version"] = invalid_spec["version"] = bad
                with self.assertRaises(a.ContractError): a.run_identity(invalid, invalid_spec, source_raw)
            capture["inventory"]["benchmark.json"]["bytes"] += 1
            with self.assertRaises(a.ContractError): a.run_identity(capture, spec, source_raw)


if __name__ == "__main__": unittest.main()
