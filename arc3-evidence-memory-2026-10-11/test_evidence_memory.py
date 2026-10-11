"""Invented primitive/fake-harness controls; no games or foreign source run."""
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from evidence_memory import EvidenceMemory, install, tool_key


def frame(step=0, level=1, grid=((0, 0), (0, 0))):
    return {"step": step, "level": level, "grid": grid}


def entry(step=1, action="UP", grid=((1, 0), (0, 0)), **result):
    return {"action": action, "frame": frame(step, grid=grid),
            "result": {"executed": True, **result}}


def message(text="executed", call="call1"):
    return {"role": "tool", "tool_call_id": call, "content": text}


def populated():
    mem = EvidenceMemory()
    mem.sync(object(), 1)
    mem.observe(frame(), [entry()], confirmed=True, content="executed")
    mem.bind(message())
    return mem


class FakeAgent:
    """Original tiny lifecycle with no action execution or file reads."""
    def __init__(self, loader):
        self.loader = loader
        self._context_budget_tokens = 2000
        self._session_runtime_dir = None
        self._history_messages = []
        self.sent = []
        self.calls = 0

    def _ensure_session(self, state_path):
        if self._session_runtime_dir != state_path.parent:
            self._session_runtime_dir = state_path.parent
            self._history_messages = []

    def _run_python_tool(self, state_path, arguments):
        self._ensure_session(state_path)
        self.calls += 1
        if arguments.get("throw"):
            raise RuntimeError("invented tool failure")
        self.loader.current = arguments.get("after", self.loader.current)
        self.loader.history = arguments.get("history", self.loader.history)
        return NS(step_executed=arguments.get("confirmed", True), content="executed")

    def _append_context_message(self, messages, message):
        messages.append(message)

    def _persistent_history_messages(self, messages, **kwargs):
        return self._trim_messages_for_context(messages, **kwargs)[1:]

    def _estimate_request_input_tokens(self, messages, **kwargs):
        return sum(len(m.get("content", "")) for m in messages)

    def _trim_messages_for_context(self, messages, **kwargs):
        # Fake baseline algorithm: removal is independent of adapter memory.
        result = list(messages)
        budget = self._context_budget_tokens - kwargs.get("extra_safety_tokens", 0)
        while len(result) > 2 and self._estimate_request_input_tokens(result) > budget:
            result.pop(1)
        return result

    def _force_reduce_messages(self, messages, **kwargs):
        return messages[:1] + messages[2:]

    def _chat_completion(self, messages, **kwargs):
        self.sent.append(messages)
        return {"messages": messages}


class Loader:
    def __init__(self):
        self.current = NS(**frame())
        self.history = []

    def __call__(self, state_path):
        return self.current, self.history


def adapted(enabled=True):
    class IsolatedFake(FakeAgent):
        pass
    loader = Loader()
    pin = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = install(IsolatedFake, loader, enabled=enabled, expected_module_sha256=pin)
    return IsolatedFake(loader), loader, report


class MemoryControls(unittest.TestCase):
    def test_no_commit_no_block(self):
        self.assertEqual(populated().block, "")

    def test_confirmed_evicted_produces_endpoint_facts(self):
        m = populated(); m.commit([message()], [])
        self.assertIn("changed_cells=1 bbox=0,0,0,0", m.block)
        self.assertIn("animations and hidden state are unknown", m.block)
        self.assertNotIn("no-op", m.block)

    def test_retained_message_does_not_activate(self):
        m = populated(); m.commit([message()], [message()])
        self.assertEqual(m.block, "")

    def test_committing_twice_is_idempotent(self):
        m = populated(); m.commit([message()], []); before = m.report()
        m.commit([message()], [])
        self.assertEqual(before, m.report())

    def test_clicked_coordinates_distinct(self):
        m = EvidenceMemory(); m.sync(object(), 1)
        for i in range(2):
            m.observe(frame(i), [entry(i + 1, f"MOUSE(row={i}, col=9)")], confirmed=True, content="executed")
            m.bind(message(call=f"call{i}"))
        m.commit([message(call="call0"), message(call="call1")], [])
        self.assertIn("MOUSE(row=0, col=9)", m.block)
        self.assertIn("MOUSE(row=1, col=9)", m.block)

    def test_endpoint_equality_never_claims_no_effect(self):
        m = EvidenceMemory(); m.sync(object(), 1)
        m.observe(frame(), [entry(grid=((0, 0), (0, 0)))], confirmed=True, content="executed")
        m.bind(message()); m.commit([message()], [])
        self.assertIn("changed_cells=0", m.block)
        self.assertNotIn("no effect", m.block)

    def test_edge_pixel_counted(self):
        m = EvidenceMemory(); m.sync(object(), 1)
        m.observe(frame(), [entry(grid=((0, 0), (0, 1)))], confirmed=True, content="executed")
        self.assertEqual(m.records[0]["bbox"], (1, 1, 1, 1))

    def test_contradictory_observations_both_carried(self):
        m = EvidenceMemory(); m.sync(object(), 1)
        for i, grid in enumerate([((1, 0), (0, 0)), ((2, 0), (0, 0))]):
            m.observe(frame(i), [entry(i + 1, grid=grid)], confirmed=True, content="executed")
            m.bind(message(call=f"call{i}"))
        m.commit([message(call="call0"), message(call="call1")], [])
        self.assertIn("o1 ", m.block); self.assertIn("o2 ", m.block)
        self.assertNotEqual(m.records[0]["after"], m.records[1]["after"])

    def test_unconfirmed_ignored(self):
        m = EvidenceMemory(); m.sync(object(), 1)
        m.observe(frame(), [entry()], confirmed=False, content="executed")
        self.assertEqual(m.records, [])

    def test_noncontiguous_rejected_without_partial_records(self):
        m = EvidenceMemory(); m.sync(object(), 1)
        with self.assertRaises(ValueError):
            m.observe(frame(), [entry(), entry(3)], confirmed=True, content="executed")
        self.assertEqual(m.records, [])

    def test_reset_boundary_clears(self):
        m = populated(); m.commit([message()], [])
        m.observe(frame(1), [entry(2, "RESET")], confirmed=True, content="executed")
        self.assertEqual(m.records, []); self.assertEqual(m.block, "")

    def test_terminal_automatic_and_level_boundaries(self):
        for field in ["game_over", "done", "run_complete", "level_completed", "automatic"]:
            m = populated(); m.commit([message()], [])
            m.observe(frame(1), [entry(2, **{field: True})], confirmed=True, content="executed")
            self.assertEqual(m.block, "")
        m = populated(); m.sync(m.scope, 2)
        self.assertEqual(m.records, [])

    def test_scope_never_exposed(self):
        m = populated(); old = m.scope; m.commit([message()], [])
        self.assertNotIn(repr(old), str(m.report()) + m.block)
        m.sync(object(), 1)
        self.assertEqual(m.block, "")

    def test_missing_level_boolean_step_ragged_oversize_rejected(self):
        for bad in [frame(level=None), frame(step=True), frame(grid=((0,), (1, 2))),
                    frame(grid=tuple((0,) for _ in range(129))), frame(grid=((False,),))]:
            m = EvidenceMemory()
            with self.assertRaises(ValueError):
                m.observe(bad, [entry()], confirmed=True, content="executed")

    def test_boundary_flag_type_drift_rejected(self):
        for field in ["executed", "automatic", "game_over", "done", "run_complete", "level_completed"]:
            m = EvidenceMemory()
            with self.assertRaises(ValueError):
                m.observe(frame(), [entry(**{field: 1})], confirmed=True, content="executed")

    def test_secret_like_action_rejected(self):
        m = EvidenceMemory()
        with self.assertRaises(ValueError):
            m.observe(frame(), [entry(action="/Users/example/key")], confirmed=True, content="executed")

    def test_duplicate_binding_does_not_learn_ambiguous_association(self):
        m = populated()
        m.observe(frame(1), [entry(2)], confirmed=True, content="executed")
        m.bind(message())
        self.assertEqual(m.counters["ambiguous_bindings"], 1)
        self.assertIsNone(m.records[-1]["key"])

    def test_record_and_complete_line_utf8_bounds(self):
        m = EvidenceMemory(); m.sync(object(), 1); messages = []
        for i in range(80):
            m.observe(frame(i), [entry(i + 1)], confirmed=True, content="executed")
            msg = message(call=f"call{i}"); messages.append(msg); m.bind(msg)
        m.commit(messages, [])
        self.assertEqual(len(m.records), 32)
        self.assertEqual([r["n"] for r in m.records[:2]], [1, 2])
        self.assertLessEqual(len(m.block.encode()), 1200)
        self.assertLessEqual(len(m.block.splitlines()) - 2, 6)
        self.assertTrue(m.block.endswith("\n"))


class AdapterControls(unittest.TestCase):
    def test_disabled_changes_no_class_methods(self):
        agent, _, report = adapted(False)
        self.assertFalse(report()["enabled"])
        self.assertFalse(hasattr(agent, "_owned_evidence_memory"))
        self.assertIs(agent._trim_messages_for_context.__func__, FakeAgent._trim_messages_for_context)

    def test_source_mismatch_rejected_before_mutation(self):
        class Fresh(FakeAgent): pass
        with self.assertRaises(ValueError):
            install(Fresh, Loader(), enabled=True, expected_module_sha256="0" * 64)
        self.assertFalse(hasattr(Fresh, "_owned_evidence_memory_installed"))

    def test_without_activation_request_byte_equal(self):
        a, _, _ = adapted(); messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hello"}]
        result = a._trim_messages_for_context(messages, tools=[])
        self.assertEqual(messages, result)
        self.assertEqual(a._chat_completion(result, tools=[])["messages"], messages)

    def test_observer_bind_then_committed_drain_only(self):
        a, loader, report = adapted(); path = Path("/fictional/a/state.json")
        e = entry(); native_entry = NS(action=e["action"], frame=NS(**e["frame"]), result=e["result"])
        a._run_python_tool(path, {"after": native_entry.frame, "history": [native_entry]})
        history = [{"role": "system", "content": "sys"}, message(), {"role": "user", "content": "now"}]
        a._append_context_message([], message())
        mem = a._owned_evidence_memory
        self.assertEqual(mem.block, "")
        a._context_budget_tokens = 5
        a._trim_messages_for_context(history)
        self.assertEqual(mem.block, "")
        a._persistent_history_messages(history)
        self.assertTrue(mem.block)
        a._context_budget_tokens = 2000
        self.assertIn("Executed observations", a._chat_completion(history[:1] + history[-1:], tools=[])["messages"][0]["content"])
        self.assertEqual(a.calls, 1)
        self.assertEqual(report()["instances"][0]["counters"]["observations"], 1)

    def test_preview_idempotent_and_never_evicts_extra_history(self):
        a, _, _ = adapted(); a._owned_evidence_memory = populated()
        a._owned_evidence_memory.commit([message()], [])
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "old"}, {"role": "user", "content": "now"}]
        before = a._owned_evidence_memory.report()
        once = a._trim_messages_for_context(messages)
        twice = a._trim_messages_for_context(once)
        self.assertEqual(once, twice)
        self.assertEqual(once[1:], messages[1:])
        self.assertEqual(before, a._owned_evidence_memory.report())
        a._context_budget_tokens = 12
        trimmed = a._trim_messages_for_context(messages)
        self.assertEqual(trimmed, FakeAgent._trim_messages_for_context(a, messages))

    def test_budget_omits_evidence_and_never_requests_again(self):
        a, _, _ = adapted(); a._owned_evidence_memory = populated()
        a._owned_evidence_memory.commit([message()], [])
        a._context_budget_tokens = 5
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "hi"}]
        self.assertEqual(a._chat_completion(messages, tools=[])["messages"], messages)
        self.assertEqual(len(a.sent), 1)
        self.assertEqual(a._owned_evidence_memory.counters["request_budget_omissions"], 1)

    def test_overflow_reserve_not_spent_by_final_chat(self):
        a, _, _ = adapted(); a._owned_evidence_memory = populated()
        a._owned_evidence_memory.commit([message()], [])
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "now"}]
        a._context_budget_tokens = len("sysnow") + len(a._owned_evidence_memory.block) + 400
        trimmed = a._trim_messages_for_context(messages, extra_safety_tokens=512, force_drain=True)
        self.assertEqual(trimmed, messages)
        self.assertEqual(a._chat_completion(trimmed, tools=[])["messages"], messages)

    def test_scope_level_change_clears_before_next_request(self):
        a, loader, _ = adapted(); path = Path("/fictional/a/state.json")
        a._ensure_session(path)
        a._owned_evidence_memory = populated()
        a._owned_evidence_memory.scope = path.parent
        a._owned_evidence_memory.commit([message()], [])
        loader.current = NS(**frame(level=2))
        a._ensure_session(path)
        self.assertEqual(a._owned_evidence_memory.block, "")

    def test_tool_failure_propagates_without_fake_observation(self):
        a, _, _ = adapted()
        with self.assertRaises(RuntimeError):
            a._run_python_tool(Path("/fictional/a/state.json"), {"throw": True})
        self.assertEqual(a._owned_evidence_memory.records, [])

    def test_final_capture_failure_clears_old_facts(self):
        a, _, _ = adapted(); a._ensure_session(Path("/fictional/a/state.json"))
        mem = a._owned_evidence_memory
        mem.observe(frame(), [entry()], confirmed=True, content="executed")
        mem.bind(message()); mem.commit([message()], [])
        self.assertTrue(mem.block)
        a._run_python_tool(Path("/fictional/a/state.json"), {"after": NS(**frame(3))})
        self.assertEqual(mem.block, "")

    def test_partial_missing_history_does_not_become_execution(self):
        a, _, _ = adapted()
        a._run_python_tool(Path("/fictional/a/state.json"), {"after": NS(**frame(3))})
        self.assertEqual(a._owned_evidence_memory.records, [])
        self.assertGreater(a._owned_evidence_memory.counters["capture_errors"], 0)


if __name__ == "__main__":
    unittest.main()
