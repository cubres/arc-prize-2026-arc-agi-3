"""Original, bounded observations carried across committed conversation drains.

This module never chooses, blocks, replays or executes a game action. It retains
endpoint evidence from confirmed actions; endpoint equality says nothing about
an unseen animation or hidden state. The optional adapter wraps a caller-pinned
harness. No harness, model, network or game package is imported here.
"""
from __future__ import annotations

from collections import Counter
from functools import wraps
import hashlib
import inspect
import json
from pathlib import Path
import re
import time


MAX_RECORDS = 32
MAX_LINES = 6
MAX_BLOCK_BYTES = 1200
MAX_BATCH = 64
_ACTION = re.compile(r"(?:UP|DOWN|LEFT|RIGHT|SPACE|ACTION[1-7]|UNDO|MOUSE\(row=-?\d{1,4}, col=-?\d{1,4}\))\Z")
_HEADER = (
    "\n[Executed observations retained from dropped tool turns; bounded sample. "
    "Whole-grid endpoints only; animations and hidden state are unknown. "
    "Matching visible boards do not prove matching internal state.]\n"
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _frame(value):
    """Validate caller-decoded primitive observations without normalization."""
    if type(value) is not dict or type(value.get("step")) is not int or value["step"] < 0:
        raise ValueError("unknown step")
    if type(value.get("level")) is not int or value["level"] < 1:
        raise ValueError("unknown level")
    grid = value.get("grid")
    if type(grid) not in (list, tuple) or not 1 <= len(grid) <= 128:
        raise ValueError("unknown grid")
    if any(type(row) not in (list, tuple) for row in grid):
        raise ValueError("unknown row")
    cols = len(grid[0])
    if not 1 <= cols <= 128 or any(len(row) != cols for row in grid):
        raise ValueError("ragged or oversized grid")
    if any(type(cell) is not int or not 0 <= cell <= 15 for row in grid for cell in row):
        raise ValueError("unknown palette value")
    return {"step": value["step"], "level": value["level"],
            "grid": tuple(tuple(row) for row in grid)}


def tool_key(message):
    if type(message) is not dict or message.get("role") != "tool":
        return None
    content, call_id = message.get("content"), message.get("tool_call_id")
    if type(content) is not str or type(call_id) is not str or not call_id or len(call_id) > 256:
        return None
    return _digest([call_id, hashlib.sha256(content.encode()).hexdigest()])


class EvidenceMemory:
    """One opaque session/level epoch; counters span epochs, facts do not."""
    def __init__(self):
        self.scope = None
        self.level = None
        self.records = []
        self.pending = []
        self.pending_content = None
        self.block = ""
        self.serial = 0
        self.counters = Counter()
        self.observer_seconds = 0.0

    def clear(self):
        self.records = []
        self.pending = []
        self.pending_content = None
        self.block = ""
        self.counters["scope_clears"] += 1

    def sync(self, scope, level):
        if type(level) is not int or level < 1:
            self.clear()
            self.level = None
            return False
        if self.scope != scope or self.level != level:
            self.clear()
            self.scope, self.level = scope, level
        return True

    def observe(self, before, entries, *, confirmed, content):
        """Record only a contiguous confirmed, same-level, non-reset sequence.

        No per-action animation is reconstructed from the final frame. A source
        transition's executed flag must be exactly True. Automatic actions and
        terminal/level boundaries clear the epoch instead of becoming evidence.
        """
        self.pending, self.pending_content = [], None
        if confirmed is not True:
            self.counters["unconfirmed_tools"] += 1
            return
        before = _frame(before)
        if not self.sync(self.scope, before["level"]):
            return
        if type(entries) is not list or not 1 <= len(entries) <= MAX_BATCH or type(content) is not str:
            raise ValueError("unknown execution sequence")
        previous = before
        new = []
        for entry in entries:
            if type(entry) is not dict or type(entry.get("result")) is not dict:
                raise ValueError("unknown result")
            result = entry["result"]
            for field in ("executed", "automatic", "game_over", "done", "run_complete", "level_completed"):
                if field in result and type(result[field]) is not bool:
                    raise ValueError("unknown execution/boundary flag")
            after = _frame(entry.get("frame"))
            action = entry.get("action")
            boundary = (action == "RESET" or result.get("action_name") == "RESET"
                        or result.get("automatic") is True
                        or any(result.get(k) is True for k in ("game_over", "done", "run_complete", "level_completed"))
                        or after["level"] != before["level"])
            if boundary:
                self.clear()
                self.level = after["level"]
                self.counters["execution_boundaries"] += 1
                return
            if result.get("executed") is not True or after["step"] != previous["step"] + 1:
                raise ValueError("unconfirmed or non-contiguous action")
            if type(action) is not str or not _ACTION.fullmatch(action):
                raise ValueError("unknown action display")
            bg, ag = previous["grid"], after["grid"]
            bs, ass = (len(bg), len(bg[0])), (len(ag), len(ag[0]))
            changed = None
            bbox = None
            if bs == ass:
                coords = [(r, c) for r in range(bs[0]) for c in range(bs[1]) if bg[r][c] != ag[r][c]]
                changed = len(coords)
                if coords:
                    bbox = (min(r for r, _ in coords), min(c for _, c in coords),
                            max(r for r, _ in coords), max(c for _, c in coords))
            self.serial += 1
            new.append({"n": self.serial, "action": action, "before_step": previous["step"],
                        "step": after["step"], "level": after["level"], "before": _digest(bg),
                        "after": _digest(ag), "before_shape": bs, "after_shape": ass,
                        "changed": changed, "bbox": bbox, "key": None, "evicted": False})
            previous = after
        self.records.extend(new)
        # Two early anchors survive, then the most recent thirty observations.
        if len(self.records) > MAX_RECORDS:
            self.records = self.records[:2] + self.records[-(MAX_RECORDS - 2):]
        self.pending = new
        self.pending_content = hashlib.sha256(content.encode()).hexdigest()
        self.counters["observations"] += len(new)

    def bind(self, message):
        if not self.pending or type(message) is not dict or message.get("role") != "tool":
            return
        key = tool_key(message)
        content = message.get("content")
        if (not key or type(content) is not str
                or hashlib.sha256(content.encode()).hexdigest() != self.pending_content
                or any(r["key"] == key for r in self.records if r not in self.pending)):
            self.counters["ambiguous_bindings"] += 1
        else:
            for record in self.pending:
                record["key"] = key
            self.counters["bound_tools"] += 1
        self.pending, self.pending_content = [], None

    def commit(self, original, retained):
        """Called on the actual persistent-history commit, never a trim preview."""
        old = Counter(k for m in original for k in [tool_key(m)] if k)
        kept = Counter(k for m in retained for k in [tool_key(m)] if k)
        removed = {k for k, n in old.items() if n == 1 and kept[k] == 0}
        changed = False
        for record in self.records:
            if record["key"] in removed and not record["evicted"]:
                record["evicted"] = True
                changed = True
        if not changed:
            return
        self.counters["committed_drains_with_evidence"] += 1
        self.block = self._render()

    def _render(self):
        eligible = [r for r in self.records if r["evicted"]]
        if not eligible:
            return ""
        chosen = [eligible[-1]]
        # Contradictory endpoints from the same *visible* board/action remain
        # observations, never a deterministic world-model rule.
        for a in reversed(eligible):
            pair = next((b for b in reversed(eligible) if a["n"] != b["n"]
                         and (a["before"], a["action"]) == (b["before"], b["action"])
                         and a["after"] != b["after"]), None)
            if pair:
                chosen.extend([a, pair])
                break
        chosen.append(eligible[0])
        chosen.extend(reversed(eligible))
        unique = []
        for item in chosen:
            if item["n"] not in {r["n"] for r in unique}:
                unique.append(item)
            if len(unique) == MAX_LINES:
                break
        block = _HEADER
        for r in sorted(unique, key=lambda item: item["n"]):
            shape = f'{r["before_shape"][0]}x{r["before_shape"][1]}>{r["after_shape"][0]}x{r["after_shape"][1]}'
            delta = "unknown" if r["changed"] is None else str(r["changed"])
            box = "-" if r["bbox"] is None else ",".join(str(v) for v in r["bbox"])
            line = (f'o{r["n"]} L{r["level"]} s{r["before_step"]}>{r["step"]} {r["action"]} '
                    f'grid={r["before"][:12]}>{r["after"][:12]} shape={shape} changed_cells={delta} bbox={box}\n')
            if len((block + line).encode()) <= MAX_BLOCK_BYTES:
                block += line
        return block if block != _HEADER else ""

    def report(self):
        return {"counters": dict(self.counters), "observer_seconds": self.observer_seconds,
                "stored_observations": len(self.records), "block_bytes": len(self.block.encode()),
                "scope_identity_exposed": False, "animation_complete_claimed": False}


def _plain_frame(frame):
    if frame is None:
        raise ValueError("missing frame")
    return {"grid": frame.grid, "step": frame.step, "level": frame.level}


def install(agent_class, runtime_loader, *, enabled, expected_module_sha256):
    """Optional source-pinned lifecycle adapter; returns aggregate-only reporter.

    Installation is intended before any games. The source pin is a reviewed
    trust input, not an authenticity claim. Disabled installation touches no
    class methods. Each request keeps the baseline trimming algorithm. Evidence
    is inserted only if the existing estimator has sufficient unused budget;
    it cannot evict additional history or cause additional model requests.
    """
    if type(enabled) is not bool:
        raise ValueError("enabled must be exact boolean")
    if not enabled:
        return lambda: {"enabled": False, "instances": [], "native_qualification": False}
    path = inspect.getsourcefile(agent_class)
    if not path or hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected_module_sha256:
        raise ValueError("harness source pin mismatch")
    if getattr(agent_class, "_owned_evidence_memory_installed", False):
        raise ValueError("adapter already installed")
    names = ("_ensure_session", "_run_python_tool", "_append_context_message",
             "_persistent_history_messages", "_trim_messages_for_context", "_force_reduce_messages",
             "_chat_completion", "_estimate_request_input_tokens")
    original = {name: getattr(agent_class, name) for name in names}
    ledgers = []

    def memory(agent):
        value = getattr(agent, "_owned_evidence_memory", None)
        if value is None:
            value = EvidenceMemory()
            agent._owned_evidence_memory = value
            ledgers.append(value)
        return value

    def strip(agent, messages):
        """Remove exactly our prior suffix before baseline trimming."""
        suffix = getattr(agent, "_owned_evidence_suffix", "")
        if (suffix and messages and type(messages[0]) is dict
                and type(messages[0].get("content")) is str
                and messages[0]["content"].endswith(suffix)):
            return [dict(messages[0], content=messages[0]["content"][:-len(suffix)]), *messages[1:]]
        return messages

    def augment(agent, messages, tools=None, extra_safety_tokens=0):
        block = memory(agent).block
        if not block or not messages or type(messages[0].get("content")) is not str:
            return messages
        candidate = [dict(messages[0], content=messages[0]["content"] + block), *messages[1:]]
        # Preserve the pinned harness's 512-token overflow reduction even
        # when a subsequent chat call receives no explicit safety argument.
        budget = max(1, agent._context_budget_tokens - max(512, extra_safety_tokens))
        used = original["_estimate_request_input_tokens"](agent, candidate, tools=tools)
        if type(used) is not int or used > budget:
            return messages
        agent._owned_evidence_suffix = block
        return candidate

    @wraps(original["_ensure_session"])
    def ensure(agent, state_path):
        result = original["_ensure_session"](agent, state_path)
        mem = memory(agent)
        scope = getattr(agent, "_session_runtime_dir", None)
        if mem.scope != scope:
            mem.clear()
            mem.scope, mem.level = scope, None
        # analyze() calls this before constructing its first request, so a level
        # transition that happened outside this adapter cannot leak old facts.
        start = time.perf_counter()
        try:
            frame, _ = runtime_loader(state_path)
            observed = _frame(_plain_frame(frame))
            mem.sync(scope, observed["level"])
        except Exception:
            mem.clear()
            mem.level = None
            mem.counters["capture_errors"] += 1
        mem.observer_seconds += time.perf_counter() - start
        return result

    @wraps(original["_run_python_tool"])
    def run(agent, state_path, arguments):
        mem = memory(agent)
        mem.pending, mem.pending_content = [], None
        start = time.perf_counter()
        before = None
        try:
            frame, _ = runtime_loader(state_path)
            before = _frame(_plain_frame(frame))
            mem.sync(getattr(agent, "_session_runtime_dir", None), before["level"])
        except Exception:
            mem.clear()
            mem.level = None
            mem.counters["capture_errors"] += 1
        mem.observer_seconds += time.perf_counter() - start
        result = original["_run_python_tool"](agent, state_path, arguments)
        if before is None or getattr(result, "step_executed", False) is not True:
            return result
        start = time.perf_counter()
        try:
            frame, history = runtime_loader(state_path)
            final = _frame(_plain_frame(frame))
            if type(history) is not list or len(history) > 8192:
                raise ValueError("unknown or oversized history")
            if final["level"] != before["level"] or final["step"] <= before["step"]:
                mem.clear()
                mem.level = final["level"]
                mem.counters["execution_boundaries"] += 1
            else:
                entries = [{"action": e.action, "frame": _plain_frame(e.frame), "result": e.result}
                           for e in history if type(e.frame.step) is int and e.frame.step > before["step"]]
                if not entries or entries[-1]["frame"] != _plain_frame(frame):
                    raise ValueError("latest observation is not the returned frame")
                mem.observe(before, entries, confirmed=True, content=result.content)
        except Exception:
            mem.clear()
            mem.level = None
            mem.counters["capture_errors"] += 1
        mem.observer_seconds += time.perf_counter() - start
        return result

    @wraps(original["_append_context_message"])
    def append(agent, messages, message):
        result = original["_append_context_message"](agent, messages, message)
        memory(agent).bind(message)
        return result

    @wraps(original["_persistent_history_messages"])
    def persist(agent, messages, **kwargs):
        original_messages = strip(agent, messages)
        retained = original["_persistent_history_messages"](agent, original_messages, **kwargs)
        memory(agent).commit(original_messages[1:], retained)
        return retained

    @wraps(original["_trim_messages_for_context"])
    def trim(agent, messages, **kwargs):
        result = original["_trim_messages_for_context"](agent, strip(agent, messages), **kwargs)
        return augment(agent, result, kwargs.get("tools"), kwargs.get("extra_safety_tokens", 0))

    @wraps(original["_force_reduce_messages"])
    def reduce(agent, messages, **kwargs):
        result = original["_force_reduce_messages"](agent, strip(agent, messages), **kwargs)
        return augment(agent, result)

    @wraps(original["_chat_completion"])
    def chat(agent, messages, **kwargs):
        outgoing = augment(agent, strip(agent, messages), kwargs.get("tools"))
        mem = memory(agent)
        if outgoing is not messages and outgoing and mem.block and outgoing[0]["content"].endswith(mem.block):
            mem.counters["requests_with_evidence"] += 1
        elif mem.block:
            mem.counters["request_budget_omissions"] += 1
        return original["_chat_completion"](agent, outgoing, **kwargs)

    for name, function in (("_ensure_session", ensure), ("_run_python_tool", run),
                           ("_append_context_message", append), ("_persistent_history_messages", persist),
                           ("_trim_messages_for_context", trim), ("_force_reduce_messages", reduce),
                           ("_chat_completion", chat)):
        setattr(agent_class, name, function)
    agent_class._owned_evidence_memory_installed = True
    return lambda: {"enabled": True, "instances": [m.report() for m in ledgers],
                    "bounds": {"observations": MAX_RECORDS, "lines": MAX_LINES, "utf8_bytes": MAX_BLOCK_BYTES},
                    "native_qualification": False, "timing_scope": "extra observation reads and extraction only"}
