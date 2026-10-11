"""Visible-evidence repeat advice; never an action veto.

This original, standard-library module has no game, model, filesystem or network
access. Callers supply observations available to the live agent. Complete
animation capture is an adapter responsibility, not something this module can
attest. Advice is a hypothesis about visible observations, never hidden state.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import re


MAX_GRID_SIDE = 64
MAX_ANIMATION_FRAMES = 128
_SIMPLE = frozenset(("UP", "DOWN", "LEFT", "RIGHT", "SPACE"))
_MOUSE = re.compile(r"MOUSE\(\s*(?:ROW\s*=\s*)?(\d{1,2})\s*,\s*(?:COL\s*=\s*)?(\d{1,2})\s*\)\Z")
VISIBLE_LETTERS = "WwgGcBMPRbSYOrNp"


def grid_from_ascii(text):
    """Convert the public letter-coded frame view to equality-only colour ids.

    These ids are our own ordering of the public legend, not engine colour ids.
    No runtime internals or raw engine array is required by a live adapter.
    """
    if type(text) is not str or not 1 <= len(text) <= MAX_GRID_SIDE * (MAX_GRID_SIDE + 2):
        raise ValueError("invalid ASCII frame size")
    rows = text.splitlines()
    try:
        board = [[VISIBLE_LETTERS.index(char) for char in row] for row in rows]
    except ValueError as exc:
        raise ValueError("unknown public colour letter") from exc
    _grid(board)
    return board


def _grid(value):
    if type(value) not in (list, tuple) or not 1 <= len(value) <= MAX_GRID_SIDE:
        raise ValueError("grid must have 1..64 rows")
    width = len(value[0]) if type(value[0]) in (list, tuple) else 0
    if not 1 <= width <= MAX_GRID_SIDE:
        raise ValueError("grid must have 1..64 columns")
    result = []
    for row in value:
        if type(row) not in (list, tuple) or len(row) != width:
            raise ValueError("grid must be rectangular")
        if any(type(v) is not int or not 0 <= v <= 15 for v in row):
            raise ValueError("grid cells must be integer colour ids 0..15")
        result.append(tuple(row))
    return tuple(result)


def visible_digest(board):
    """Whole-frame digest, including dimensions and every border/HUD cell."""
    b = _grid(board)
    encoded = bytes((len(b), len(b[0]))) + bytes(v for row in b for v in row)
    return hashlib.sha256(encoded).hexdigest()


def _level(value):
    if type(value) is not int or not 1 <= value <= 1000:
        raise ValueError("level must be an integer in 1..1000")
    return value


def _action(value):
    if type(value) is not str or len(value) > 32:
        raise ValueError("action must be a short model-facing string")
    name = value.strip().upper()
    if name in _SIMPLE or name in ("RESET", "UNDO"):
        return name
    m = _MOUSE.fullmatch(name)
    if m and all(int(c) < MAX_GRID_SIDE for c in m.groups()):
        return "MOUSE(%d,%d)" % tuple(int(c) for c in m.groups())
    raise ValueError("unsupported action or coordinates")


@dataclass(frozen=True)
class Advice:
    warn: bool
    message: str
    visible_repeat_count: int
    reason: str
    # Advice cannot express a veto. The host remains responsible for executing
    # or choosing an action, and must not reinterpret `warn` as a blocking flag.
    permits_execution: bool = True


@dataclass
class _Entry:
    count: int = 0
    contradicted: bool = False
    last_observed_step: int = 0
    announced: bool = False


class RepeatAdviser:
    """Bounded, per-attempt evidence memory with a one-time optional advisory.

    Two fully captured, unchanged visible transitions qualify by default. Missing
    animation never qualifies. A visible contradictory outcome retires that key
    until reset/level change/eviction. Hidden delayed effects remain possible
    even when all supplied frames are identical; execution is always permitted.
    """

    def __init__(self, *, observations_required=2, ttl_actions=32, max_entries=512):
        for name, value, lower, upper in (
            ("observations_required", observations_required, 2, 32),
            ("ttl_actions", ttl_actions, 1, 4096),
            ("max_entries", max_entries, 1, 4096),
        ):
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f"invalid {name}")
        self.required = observations_required
        self.ttl = ttl_actions
        self.capacity = max_entries
        self._entries = OrderedDict()
        self._level = None
        self._step = 0

    def reset_attempt(self):
        """Call on every observed RESET, including resets on the same level."""
        self._entries.clear()
        self._step = 0
        self._level = None

    def _scope(self, level):
        if self._level != level:
            self.reset_attempt()
            self._level = level

    def advise(self, *, level, board, action):
        level = _level(level)
        signature = _action(action)
        digest = visible_digest(board)
        self._scope(level)
        if signature in ("RESET", "UNDO"):
            return Advice(False, "", 0, "recovery_action")
        entry = self._entries.get((digest, signature))
        if entry is None:
            return Advice(False, "", 0, "no_qualified_evidence")
        if entry.contradicted:
            return Advice(False, "", entry.count, "contradictory_visible_outcome")
        if self._step - entry.last_observed_step > self.ttl:
            return Advice(False, "", entry.count, "expired_evidence")
        if entry.count < self.required:
            return Advice(False, "", entry.count, "insufficient_observations")
        if entry.announced:
            return Advice(False, "", entry.count, "already_announced")
        entry.announced = True
        return Advice(
            True,
            "Repeated actions from this exact visible frame produced no visible "
            "change in captured frames. Delayed or hidden effects remain possible; "
            "repeating is allowed. Consider a different probe if the repetition "
            "was not intentional.",
            entry.count,
            "repeated_visible_unchanged",
        )

    def observe(self, *, level_before, before, action, level_after, after,
                animation_frames=None, terminal=False):
        """Observe one executed action, after execution. Never execute/veto it.

        `animation_frames=None` means missing/incomplete capture. Otherwise the
        bounded sequence must include the final frame as its last element. It
        must be the COMPLETE per-action chain from the live adapter; this module
        validates structure and endpoint, not the adapter's completeness claim.
        """
        level_before = _level(level_before)
        level_after = _level(level_after)
        signature = _action(action)
        b, a = _grid(before), _grid(after)
        if len(b) != len(a) or len(b[0]) != len(a[0]):
            raise ValueError("grid dimensions changed")
        if type(terminal) is not bool:
            raise ValueError("terminal must be a bool")
        chain = None
        if animation_frames is not None:
            if type(animation_frames) not in (list, tuple) or not 1 <= len(animation_frames) <= MAX_ANIMATION_FRAMES:
                raise ValueError("animation must contain 1..128 frames or be None")
            chain = tuple(_grid(f) for f in animation_frames)
            if any(len(f) != len(a) or len(f[0]) != len(a[0]) for f in chain):
                raise ValueError("animation dimensions changed")
            if chain[-1] != a:
                raise ValueError("animation endpoint must equal final frame")
        self._scope(level_before)
        self._step += 1
        if signature == "RESET" or terminal or level_after != level_before:
            self.reset_attempt()
            self._level = level_after
            return "scope_reset"
        if signature == "UNDO":
            # An observed recovery may restore a board while altering history.
            self._entries.clear()
            return "recovery_evidence_cleared"
        key = (visible_digest(b), signature)
        final_changed = a != b
        animation_changed = chain is not None and any(f != b for f in chain)
        entry = self._entries.get(key)
        if final_changed or animation_changed:
            if entry is None:
                entry = _Entry()
                self._entries[key] = entry
            entry.contradicted = True
            entry.last_observed_step = self._step
            self._trim()
            return "visible_outcome_varies"
        if chain is None:
            # Unknown observations do not refresh the TTL or count as repeats.
            return "animation_capture_unknown"
        if entry is None:
            entry = _Entry()
            self._entries[key] = entry
        elif self._step - entry.last_observed_step > self.ttl and not entry.contradicted:
            entry.count = 0
            entry.announced = False
        if not entry.contradicted:
            entry.count += 1
        entry.last_observed_step = self._step
        self._entries.move_to_end(key)
        self._trim()
        return "qualified_visible_unchanged" if not entry.contradicted else "retired_key"

    def _trim(self):
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)

