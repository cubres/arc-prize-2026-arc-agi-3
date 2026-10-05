"""Original CPU-only temporal annotation for the pinned ARC3 prompt.

Caller supplies complete PUBLIC executed-action metadata, never game answers.
This does not run an engine, model, tool or notebook, or alter their state.
The only edited prompt lines are canonical sequence/outcome/current-state lines.
Full last summary, action results, knowledge and animation text remain external.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re

TOOL_AGENT_SHA256 = "856bf9b895d0ad8b959c8f828c7132b0e09eaa47f4c5cc6173785354090f8be7"
SOLVER_SHA256 = "2bef5d6bc23c0312675f0c7203194c94e93d056ac06bf6419acd5142a4ea7c8e"
MAX_HISTORY = 100_000


class FeedbackContractError(ValueError):
    pass


def _integer(value: object, name: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise FeedbackContractError(f"{name} must be an integer >= {minimum}")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise FeedbackContractError(f"{name} must be a boolean")
    return value


@dataclass(frozen=True)
class ActionEvent:
    """One actual executed action, including runner RESET if observed.

    revision is the public history index, independent of frame contents/step.
    Outcome flags are the actual returned engine flags, not inferred from RESET.
    """
    revision: int
    action: str
    level: int
    game_over: bool = False
    run_complete: bool = False
    level_completed: bool = False


def event_from_result(result: Mapping[str, object]) -> ActionEvent | None:
    """Rejected/inspection-only results are not new executed history events."""
    if not _boolean(result.get("executed"), "executed"):
        return None
    event = ActionEvent(
        _integer(result.get("action_num"), "action_num", 1),
        result.get("action_name"),
        _integer(result.get("level"), "level", 1),
        _boolean(result.get("game_over"), "game_over"),
        _boolean(result.get("run_complete"), "run_complete"),
        _boolean(result.get("level_completed"), "level_completed"),
    )
    _validate_event(event)
    return event


def _validate_event(event: ActionEvent) -> None:
    if not isinstance(event, ActionEvent):
        raise FeedbackContractError("history requires ActionEvent observations")
    _integer(event.revision, "revision", 1)
    _integer(event.level, "level", 1)
    if not isinstance(event.action, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,31}", event.action):
        raise FeedbackContractError("invalid observed action name")
    for name in ("game_over", "run_complete", "level_completed"):
        _boolean(getattr(event, name), name)
    if sum((event.game_over, event.run_complete, event.level_completed)) > 1:
        raise FeedbackContractError("mutually inconsistent terminal outcome flags")


@dataclass(frozen=True)
class RenderedFeedback:
    prompt: str
    # Exactly the modified line index, original text and replacement text.
    changed_lines: tuple[tuple[int, str, str], ...]
    summary_status: str
    history_revision: int
    current_phase: str


class FeedbackWatermark:
    """Per-session/pass first-report watermark; no game-ID-dependent policy."""

    def __init__(self) -> None:
        self._seen: dict[tuple[str, str], tuple[tuple[ActionEvent, ...], tuple | None]] = {}

    def render(
        self, prompt: str, *, scope: tuple[str, str], history: Sequence[ActionEvent],
        frame_step: int, frame_level: int, summary: Mapping[str, object] | None,
    ) -> RenderedFeedback:
        if not isinstance(scope, tuple) or len(scope) != 2 or any(
            not isinstance(x, str) or not x or len(x) > 256 for x in scope
        ):
            raise FeedbackContractError("scope must identify one session and game pass")
        if not isinstance(prompt, str) or len(prompt) > 1_000_000:
            raise FeedbackContractError("invalid or unbounded prompt")
        _integer(frame_step, "frame_step")
        _integer(frame_level, "frame_level", 1)
        if len(history) > MAX_HISTORY:
            raise FeedbackContractError("history exceeds diagnostic bound")
        events = tuple(history)
        for index, event in enumerate(events, 1):
            _validate_event(event)
            if event.revision != index:
                raise FeedbackContractError("history must be complete and consecutively indexed")
        revision = len(events)
        if frame_step > revision or (events and events[-1].level != frame_level):
            raise FeedbackContractError("current frame disagrees with public history")
        old_history, old_key = self._seen.get(scope, ((), None))
        if revision < len(old_history) or events[:len(old_history)] != old_history:
            raise FeedbackContractError("history regressed or changed a previous observation")
        phase = ("run complete" if events[-1].run_complete else
                 "failed attempt" if events[-1].game_over else "nonterminal") if events else "unobserved"
        key = None
        start = end = count = 0
        flags = (False, False, False)
        if summary is not None:
            start = _integer(summary.get("start_action_num"), "summary start", 1)
            end = _integer(summary.get("end_action_num"), "summary end", 1)
            count = _integer(summary.get("executed_count"), "summary count", 1)
            summary_level = _integer(summary.get("level"), "summary level", 1)
            flags = tuple(_boolean(summary.get(name), name) for name in (
                "run_complete", "level_transition", "game_over"))
            if end > revision or end - start + 1 != count:
                raise FeedbackContractError("summary span is outside executed history")
            last = events[end - 1]
            span = events[start - 1:end]
            observed_flags = (any(e.run_complete for e in span),
                              any(e.level_completed for e in span),
                              any(e.game_over for e in span))
            if (summary_level, flags) != (last.level, observed_flags):
                raise FeedbackContractError("summary outcome disagrees with its actual executed span")
            key = (start, end, count, summary_level, flags)
            if old_key is not None and (end < old_key[1] or (end == old_key[1] and key != old_key)):
                raise FeedbackContractError("summary regressed or changed an existing outcome")
        elif old_key is not None:
            raise FeedbackContractError("last executed summary disappeared")
        status = ("none" if key is None else "historical, already shown" if key == old_key else
                  "newly observed" if end == revision else "historical, first report")
        reset = next((e for e in reversed(events) if e.action == "RESET" and
                      e.revision > end and not e.game_over and not e.run_complete), None)
        label = f"Outcome for actions {start}-{end} ({status})"
        replacements: dict[str, str] = {}
        if key is not None:
            noun = "action" if count == 1 else "actions"
            replacements[f"The code executed {count} {noun} in the previous sequence."] = (
                f"Agent sequence at actions {start}-{end} ({status}): {count} {noun}.")
            if flags[0]:
                replacements["You have completed the run!"] = f"{label}: the run completed (WIN)."
            elif flags[1]:
                replacements["You have progressed to a new level!"] = f"{label}: a level completion was reported during that sequence."
            else:
                replacements["You are still on the same level."] = f"{label}: no level completion was reported for that sequence."
            if flags[2]:
                replacement = f"{label}: that attempt failed."
                if reset is not None:
                    replacement += (f" A nonterminal RESET was observed at action {reset.revision} "
                                    f"after that failure; current visible phase: {phase}.")
                replacements["The game is over."] = replacement
        original_lines = prompt.split("\n")
        for line in replacements:
            if original_lines.count(line) != 1:
                raise FeedbackContractError("canonical feedback line is absent or ambiguous")
        state_indices = [i for i, line in enumerate(original_lines) if re.fullmatch(
            r"Current state: step \d+, level \d+(?: out of observed max level \d+ so far)?\.", line)]
        if len(state_indices) != 1:
            raise FeedbackContractError("canonical current-state header is absent or ambiguous")
        maximum_level = max([frame_level, *[e.level for e in events]])
        state = f"Current state: step {revision + 1}, level {frame_level}"
        if maximum_level > frame_level:
            state += f" out of observed max level {maximum_level} so far"
        state += f"; current visible phase: {phase}."
        result = list(original_lines)
        changes = []
        for index, line in enumerate(original_lines):
            replacement = state if index == state_indices[0] else replacements.get(line, line)
            if replacement != line:
                result[index] = replacement
                changes.append((index, line, replacement))
        # Commit only after complete validation/rendering, including canonical gates.
        self._seen[scope] = (events, key)
        return RenderedFeedback("\n".join(result), tuple(changes), status, revision, phase)
