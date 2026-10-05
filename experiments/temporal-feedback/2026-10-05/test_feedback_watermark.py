"""CPU source/control-flow contracts. No model/engine/network/notebook actions."""
from __future__ import annotations

import ast
import copy
import hashlib
import os
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from feedback_watermark import (
    ActionEvent, FeedbackContractError, FeedbackWatermark, TOOL_AGENT_SHA256,
    SOLVER_SHA256, event_from_result,
)

LOCAL_SOURCE_RELATIVE = Path("research/codex_arc3_frontier_20261004T212308Z/current_animation_source_readonly")
# Bounded ancestor lookup preserves the existing local default. Public forks can
# provide their own exact, approved asset source pair; SHA checks stay mandatory.
DEFAULT_ROOT = next((p for p in Path(__file__).resolve().parents
                     if (p / LOCAL_SOURCE_RELATIVE).is_dir()), Path.cwd())
SOURCE = Path(os.environ["ARC3_PINNED_SOURCE_DIR"]) if "ARC3_PINNED_SOURCE_DIR" in os.environ else DEFAULT_ROOT / LOCAL_SOURCE_RELATIVE


def pinned_tree(filename, expected):
    source = (SOURCE / filename).read_bytes()
    if hashlib.sha256(source).hexdigest() != expected:
        raise AssertionError("pinned actual native-consumed source changed")
    return ast.parse(source)


def function(tree, name, class_name=None):
    container = tree
    if class_name:
        container = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == class_name)
    return copy.deepcopy(next(x for x in container.body if isinstance(x, ast.FunctionDef) and x.name == name))


def compile_functions(nodes, namespace):
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), *nodes], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "<pinned-readonly-methods>", "exec"), namespace)
    return namespace


TREE = pinned_tree("tool_agent.py", TOOL_AGENT_SHA256)
SOLVER_TREE = pinned_tree("solver.py", SOLVER_SHA256)
PROMPT_NS = compile_functions([
    function(TREE, "_normalize_valid_actions"), function(TREE, "_format_valid_action_line"),
    function(TREE, "_build_user_prompt", "ToolAgent"),
    function(TREE, "_summarize_step_sequence", "ToolAgent"),
], {"to_engine_action": lambda x: x, "to_model_action": lambda x: x,
    "pick_animation": lambda values: next((v for v in values if v is not None), None),
    "describe_animation": lambda x: "Preserved animation evidence." if x else "",
    "TOOL_CALL_FORMAT_GUIDANCE": "Preserved tool format guidance."})
PROMPT_SELF = NS(_animation_hint_line=lambda *args: "Preserved animation hint.",
                 _summarized_knowledge_lines=lambda: ["Preserved world model and knowledge."])


def baseline(history, summary, frame_step=None, frame_level=None):
    level = frame_level if frame_level is not None else (history[-1].level if history else 1)
    step = len(history) if frame_step is None else frame_step
    return PROMPT_NS["_build_user_prompt"](PROMPT_SELF, len(history), valid_actions=["UP", "RESET"],
        current_frame=NS(step=step, level=level),
        history_entries=[NS(frame=NS(step=e.revision, level=e.level)) for e in history],
        previous_step_summary=summary)


def summary_for(history, *, count=1):
    e = history[-1]
    return {"start_action_num": e.revision-count+1, "end_action_num": e.revision,
            "executed_count": count, "executed_actions": ["UP"] * count,
            "level": e.level, "run_complete": e.run_complete,
            "level_transition": e.level_completed, "game_over": e.game_over,
            "animation": {"retained": True}, "board_changed": False}


class FeedbackTests(unittest.TestCase):
    def render(self, ledger, history, summary, *, scope=("session-a", "pass-0"), frame_step=None, frame_level=None):
        step = len(history) if frame_step is None else frame_step
        level = frame_level if frame_level is not None else (history[-1].level if history else 1)
        prompt = baseline(history, summary, frame_step=step, frame_level=level)
        before = copy.deepcopy((history, summary))
        out = ledger.render(prompt, scope=scope, history=history, frame_step=step, frame_level=level, summary=summary)
        self.assertEqual(before, (history, summary))
        old, new = prompt.split("\n"), out.prompt.split("\n")
        changed = {i for i, _, _ in out.changed_lines}
        self.assertEqual(len(old), len(new))
        allowed = ("The code executed ", "You have completed the run!", "You have progressed to a new level!",
                   "You are still on the same level.", "The game is over.", "Current state: ")
        for i, (a, b) in enumerate(zip(old, new)):
            if i in changed:
                self.assertTrue(any(a.startswith(x) for x in allowed), a)
            else:
                self.assertEqual(a, b)
        for text in ("Preserved animation evidence.", "Preserved animation hint.", "Preserved world model and knowledge.",
                     "Preserved tool format guidance.", "Executed actions:"):
            self.assertEqual(prompt.count(text), out.prompt.count(text))
        return out

    def test_exact_prompt_repeated_progression_is_annotated_not_new(self):
        h = [ActionEvent(1, "UP", 2, level_completed=True)]
        s = summary_for(h)
        p = baseline(h, s)
        self.assertIn("You have progressed to a new level!", p)
        self.assertEqual(p, baseline(h, s))
        ledger = FeedbackWatermark()
        a, b = self.render(ledger, h, s), self.render(ledger, h, s)
        self.assertEqual(a.summary_status, "newly observed")
        self.assertEqual(b.summary_status, "historical, already shown")
        self.assertIn("a level completion was reported during that sequence", b.prompt)
        self.assertNotIn("You have progressed to a new level!", b.prompt)

    def test_exact_prompt_after_actual_reset_preserves_failure_and_current_nonterminal_state(self):
        h = [ActionEvent(1, "UP", 2, game_over=True)]
        s = summary_for(h)
        h += [ActionEvent(2, "RESET", 2)]
        self.assertIn("The game is over.", baseline(h, s))
        out = self.render(FeedbackWatermark(), h, s)
        self.assertEqual(out.summary_status, "historical, first report")
        self.assertIn("that attempt failed", out.prompt)
        self.assertIn("nonterminal RESET was observed at action 2", out.prompt)
        self.assertIn("current visible phase: nonterminal", out.prompt)
        self.assertNotIn("The game is over.", out.prompt)

    def test_reset_name_alone_does_not_assert_success(self):
        h = [ActionEvent(1, "UP", 1, game_over=True)]
        s = summary_for(h)
        h += [ActionEvent(2, "RESET", 1, game_over=True)]
        out = self.render(FeedbackWatermark(), h, s)
        self.assertEqual(out.current_phase, "failed attempt")
        self.assertNotIn("nonterminal RESET", out.prompt)

    def test_actual_summarizer_aggregates_transition_before_ordinary_action(self):
        history = [ActionEvent(1, "UP", 2, level_completed=True), ActionEvent(2, "UP", 2)]
        results = [{"executed": True, "action_num": e.revision, "level": e.level,
                    "level_completed": e.level_completed, "run_complete": e.run_complete,
                    "game_over": e.game_over, "board_changed": False,
                    "executed_actions": [e.action], "animation": {"retained": True}}
                   for e in history]
        summary = PROMPT_NS["_summarize_step_sequence"](PROMPT_SELF, results)
        self.assertTrue(summary["level_transition"])
        self.assertFalse(history[-1].level_completed)
        self.assertEqual(summary["executed_count"], 2)
        out = self.render(FeedbackWatermark(), history, summary)
        self.assertIn("Outcome for actions 1-2", out.prompt)
        self.assertIn("a level completion was reported during that sequence", out.prompt)

    def test_actual_summarizer_retains_transition_and_failure_in_one_span(self):
        # This validates the actual summarizer's accepted metadata contract,
        # not a claim that the guarded native callback allows these later actions.
        history = [ActionEvent(1, "UP", 2, level_completed=True),
                   ActionEvent(2, "UP", 2, game_over=True)]
        results = [{"executed": True, "action_num": e.revision, "level": e.level,
                    "level_completed": e.level_completed, "run_complete": e.run_complete,
                    "game_over": e.game_over, "board_changed": False,
                    "executed_actions": [e.action], "animation": {"retained": True}}
                   for e in history]
        summary = PROMPT_NS["_summarize_step_sequence"](PROMPT_SELF, results)
        self.assertTrue(summary["level_transition"])
        self.assertTrue(summary["game_over"])
        out = self.render(FeedbackWatermark(), history, summary)
        self.assertIn("a level completion was reported during that sequence", out.prompt)
        self.assertIn("that attempt failed", out.prompt)
        self.assertEqual(out.current_phase, "failed attempt")
        contradictory = {**summary, "level_transition": False}
        with self.assertRaises(FeedbackContractError):
            self.render(FeedbackWatermark(), history, contradictory)

    def test_actual_summarizer_reset_inside_span_does_not_imply_unchanged_level(self):
        history = [ActionEvent(1, "UP", 3), ActionEvent(2, "RESET", 1)]
        results = [{"executed": True, "action_num": e.revision, "level": e.level,
                    "level_completed": e.level_completed, "run_complete": e.run_complete,
                    "game_over": e.game_over, "board_changed": False,
                    "executed_actions": [e.action], "animation": {"retained": True}}
                   for e in history]
        summary = PROMPT_NS["_summarize_step_sequence"](PROMPT_SELF, results)
        self.assertFalse(summary["level_transition"])
        self.assertEqual(summary["level"], 1)
        out = self.render(FeedbackWatermark(), history, summary)
        self.assertIn("no level completion was reported for that sequence", out.prompt)
        self.assertNotIn("stayed on its level", out.prompt)
        self.assertIn("Current state: step 3, level 1 out of observed max level 3 so far", out.prompt)

    def test_actual_summarizer_progress_then_reset_does_not_invent_destination_level(self):
        history = [ActionEvent(1, "UP", 3, level_completed=True), ActionEvent(2, "RESET", 1)]
        results = [{"executed": True, "action_num": e.revision, "level": e.level,
                    "level_completed": e.level_completed, "run_complete": e.run_complete,
                    "game_over": e.game_over, "board_changed": False,
                    "executed_actions": [e.action], "animation": {"retained": True}}
                   for e in history]
        summary = PROMPT_NS["_summarize_step_sequence"](PROMPT_SELF, results)
        self.assertTrue(summary["level_transition"])
        self.assertEqual(summary["level"], 1)
        out = self.render(FeedbackWatermark(), history, summary)
        self.assertIn("a level completion was reported during that sequence", out.prompt)
        self.assertNotIn("advanced to level 1", out.prompt)
        self.assertIn("Current state: step 3, level 1", out.prompt)

    def test_reset_origin_is_not_inferred_from_an_action_name(self):
        history = [ActionEvent(1, "UP", 1, game_over=True)]
        summary = summary_for(history)
        history.append(ActionEvent(2, "RESET", 1))
        out = self.render(FeedbackWatermark(), history, summary)
        self.assertIn("A nonterminal RESET was observed at action 2", out.prompt)
        self.assertNotIn("runner RESET", out.prompt)
        self.assertNotIn("successful", out.prompt)
        self.assertEqual(out.current_phase, "nonterminal")

    def test_win_remains_completion_not_death(self):
        h = [ActionEvent(1, "UP", 3, run_complete=True)]
        ledger = FeedbackWatermark()
        out = self.render(ledger, h, summary_for(h))
        again = self.render(ledger, h, summary_for(h))
        self.assertEqual(out.current_phase, "run complete")
        self.assertIn("run completed (WIN)", again.prompt)
        self.assertNotIn("attempt failed", again.prompt)

    def test_executed_static_board_action_is_new_despite_reused_frame_step(self):
        h = [ActionEvent(1, "UP", 1)]
        ledger = FeedbackWatermark()
        self.render(ledger, h, summary_for(h), frame_step=0)
        h += [ActionEvent(2, "UP", 1)]
        out = self.render(ledger, h, summary_for(h), frame_step=0)
        self.assertEqual(out.summary_status, "newly observed")
        self.assertIn("Current state: step 3, level 1", out.prompt)

    def test_rejected_action_is_not_a_new_event(self):
        h = [ActionEvent(1, "UP", 1)]
        ledger = FeedbackWatermark()
        self.render(ledger, h, summary_for(h))
        self.assertIsNone(event_from_result({"executed": False, "game_over": True}))
        out = self.render(ledger, h, summary_for(h))
        self.assertEqual(out.history_revision, 1)
        self.assertEqual(out.summary_status, "historical, already shown")

    def test_same_action_retry_keeps_historical_outcome(self):
        h = [ActionEvent(1, "UP", 1, game_over=True)]
        ledger = FeedbackWatermark()
        self.render(ledger, h, summary_for(h))
        out = self.render(ledger, h, summary_for(h))
        self.assertIn("that attempt failed", out.prompt)
        self.assertEqual(out.current_phase, "failed attempt")

    def test_current_frame_level_authority_after_lower_level_reset(self):
        h = [ActionEvent(1, "UP", 3, game_over=True)]
        s = summary_for(h)
        h += [ActionEvent(2, "RESET", 1)]
        self.assertIn("Current state: step 3, level 3", baseline(h, s))
        out = self.render(FeedbackWatermark(), h, s)
        self.assertIn("Current state: step 3, level 1 out of observed max level 3 so far", out.prompt)

    def test_scopes_isolate_interleaved_game_passes(self):
        h = [ActionEvent(1, "UP", 2, level_completed=True)]
        ledger = FeedbackWatermark()
        for scope in (("a", "p0"), ("b", "p0"), ("a", "p1")):
            self.assertEqual(self.render(ledger, h, summary_for(h), scope=scope).summary_status, "newly observed")
        self.assertEqual(self.render(ledger, h, summary_for(h), scope=("a", "p0")).summary_status, "historical, already shown")

    def test_regression_conflict_and_invalid_metadata_fail_before_consumption(self):
        h = [ActionEvent(1, "UP", 1)]
        ledger = FeedbackWatermark()
        self.render(ledger, h, summary_for(h))
        cases = [([], None), ([ActionEvent(1, "DOWN", 1)], summary_for(h)),
                 ([ActionEvent(2, "UP", 1)], summary_for(h)),
                 ([ActionEvent(True, "UP", 1)], summary_for(h)),
                 ([ActionEvent(1, "UP", 1, game_over=True, run_complete=True)], summary_for(h))]
        for history, summary in cases:
            with self.subTest(history=history), self.assertRaises(FeedbackContractError):
                self.render(ledger, history, summary)
        again = self.render(ledger, h, summary_for(h))
        self.assertEqual(again.summary_status, "historical, already shown")

    def test_missing_or_ambiguous_canonical_line_does_not_consume_event(self):
        h = [ActionEvent(1, "UP", 2, level_completed=True)]
        s = summary_for(h)
        ledger = FeedbackWatermark()
        p = baseline(h, s)
        for bad in (p.replace("You have progressed to a new level!", "Changed source text."),
                    p + "\nYou have progressed to a new level!"):
            with self.assertRaises(FeedbackContractError):
                ledger.render(bad, scope=("session-a", "pass-0"), history=h, frame_step=1, frame_level=2, summary=s)
        self.assertEqual(self.render(ledger, h, s).summary_status, "newly observed")

    def test_no_summary_initial_prompt_preserves_all_non_header_text(self):
        out = self.render(FeedbackWatermark(), [], None)
        self.assertEqual(out.summary_status, "none")
        self.assertEqual(len(out.changed_lines), 1)
        self.assertIn("No previous sequence has been executed yet.", out.prompt)

    def test_action_result_adapter_reads_real_flags_and_refuses_bad_types(self):
        p = {"executed": True, "action_num": 1, "action_name": "RESET", "level": 1,
             "game_over": False, "run_complete": False, "level_completed": False}
        self.assertEqual(event_from_result(p), ActionEvent(1, "RESET", 1))
        self.assertEqual(p["action_num"], 1)
        for name, value in (("executed", 1), ("action_num", float("nan")), ("level", True), ("game_over", 0)):
            with self.subTest(name=name), self.assertRaises(FeedbackContractError):
                event_from_result({**p, name: value})

    def test_pinned_actual_play_loop_reset_yield_no_action_and_retry(self):
        # Execute the exact source while-loop AST only. Setup/teardown, filesystem,
        # model/engine calls and finalization are outside this CPU branch fixture.
        play = function(SOLVER_TREE, "play", "_HarnessGameSession")
        outer_try = next(node for node in play.body if isinstance(node, ast.Try))
        retry_init = outer_try.body[0]
        actual_loop = next(node for node in outer_try.body if isinstance(node, ast.While))
        fn = ast.FunctionDef(name="pinned_loop", args=ast.arguments(posonlyargs=[], args=[ast.arg(arg="self")],
            kwonlyargs=[], kw_defaults=[], defaults=[]), body=[retry_init, actual_loop], decorator_list=[])
        calls = []
        h = [ActionEvent(1, "UP", 2, game_over=True)]
        s = summary_for(h)
        ledger = FeedbackWatermark()
        self_test = self

        class Harness:
            analysis_step = 0
            last_engine_action = "UP"
            state_path = "mock-state"
            transcript_path = "mock-transcript"
            game = NS(over=True)
            stopped = False
            attempts = 0

            @property
            def action_count(self):
                return len(h)

            def should_stop(self):
                return self.stopped

            def _execute_auto_reset(self):
                h.append(ActionEvent(len(h)+1, "RESET", 2))
                self.game.over = False
                self.last_engine_action = "RESET"

            def write_runtime_state(self):
                pass

            def _read_transcript_bytes(self):
                return b""

            def _transcript_delta_since(self, _):
                return ""

            def request_timeout_seconds(self):
                return 1

            def step_env(self, _):
                raise AssertionError("no actual engine action permitted")

            def analyze(self, _, action_num, **kwargs):
                self.attempts += 1
                calls.append((kwargs["analysis_step"], action_num,
                              self_test.render(ledger, h, s).summary_status))
                if self.attempts == 1:
                    return NS(retryable_failure=False, yielded_control=True, step_executed=False)
                if self.attempts == 2:
                    return NS(retryable_failure=False, yielded_control=False, step_executed=False)
                if self.attempts == 3:
                    return NS(retryable_failure=True, yielded_control=False, step_executed=False)
                self.stopped = True
                return NS(retryable_failure=False, yielded_control=False, step_executed=False)

        harness = Harness()
        harness.analyzer = harness
        ns = compile_functions([fn], {"_is_engine_game_over": lambda game: game.over,
            "_engine_action_names": lambda game: ["UP", "RESET"],
            "time": NS(sleep=lambda _: None), "ANALYZER_RETRY_BACKOFF_SECONDS": 0})
        ns["pinned_loop"](harness)
        self.assertEqual([(a, r) for a, r, _ in calls], [(1, 2), (1, 2), (2, 2), (2, 2)])
        self.assertEqual([x[2] for x in calls], ["historical, first report"] + ["historical, already shown"] * 3)
        self.assertEqual(h, [ActionEvent(1, "UP", 2, game_over=True), ActionEvent(2, "RESET", 2)])
        self.assertTrue(s["game_over"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
