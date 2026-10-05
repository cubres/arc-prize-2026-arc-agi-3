"""Bounded read-only authentication of pinned ARC3 retained action sidecars.

Dependency: the unchanged original feedback_watermark.ActionEvent dataclass.
No board/transcript/prose-summary output, engine/model calls or live integration.
Session/version/arm are EXTERNAL caller-attested provenance, absent from these
files. Both expected file SHA256 values must come from a trusted fetch receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

from feedback_watermark import ActionEvent

PINNED_SOLVER_SHA256 = "2bef5d6bc23c0312675f0c7203194c94e93d056ac06bf6419acd5142a4ea7c8e"
PINNED_CONSUMED_ASSETS_SHA256 = "3f07a97439d4b958b12d01b36db6eafbf1d93659ec5e1d71da4b2956b2c8debf"


class SidecarContractError(ValueError):
    pass


def _integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise SidecarContractError(f"invalid {name} integer")
    return value


def _boolean(value, name):
    if type(value) is not bool:
        raise SidecarContractError(f"invalid {name} boolean")
    return value


@dataclass(frozen=True)
class Provenance:
    notebook_ref: str
    version: int
    session_id: int
    arm: str
    run_token: str
    game_id: str
    pass_index: int

    def validate(self):
        for name in ("notebook_ref", "arm", "run_token", "game_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]{1,128}", value):
                raise SidecarContractError(f"invalid external {name}")
        _integer(self.version, "external version", 1)
        _integer(self.session_id, "external session", 1)
        _integer(self.pass_index, "external pass")

    @property
    def watermark_scope(self):
        # All components distinguish sessions, arms, game passes and individual
        # runs. Digests are opaque scope identities, never game-dependent policy.
        self.validate()
        values = [self.notebook_ref, self.version, self.session_id, self.arm,
                  self.run_token, self.game_id, self.pass_index]
        digest = hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()
        return ("retained-session:" + digest, "game-pass:" + digest)


@dataclass(frozen=True)
class Limits:
    file_bytes: int = 8 * 1024 * 1024
    line_bytes: int = 1024 * 1024
    events: int = 10_000

    def validate(self):
        for name, ceiling in (("file_bytes", 8 * 1024 * 1024),
                              ("line_bytes", 1024 * 1024), ("events", 10_000)):
            value = _integer(getattr(self, name), name, 1)
            if value > ceiling:
                raise SidecarContractError("limits may lower, not raise, hard bounds")
        if self.line_bytes > self.file_bytes:
            raise SidecarContractError("line bound exceeds file bound")


@dataclass(frozen=True)
class ParsedActions:
    events: tuple[ActionEvent, ...]
    scope: tuple[str, str]
    external_provenance: Provenance
    sidecar_sha256: str
    viewer_sha256: str
    raw_event_count: int
    initial_anchor_count: int

    def scalar_receipt(self):
        return {"action_count": len(self.events), "raw_event_count": self.raw_event_count,
                "initial_anchor_count": self.initial_anchor_count,
                "sidecar_sha256": self.sidecar_sha256, "viewer_sha256": self.viewer_sha256,
                "scope": list(self.scope),
                "external_provenance": {"notebook_ref": self.external_provenance.notebook_ref,
                    "version": self.external_provenance.version, "session_id": self.external_provenance.session_id,
                    "arm": self.external_provenance.arm, "run_token": self.external_provenance.run_token,
                    "game_id": self.external_provenance.game_id, "pass_index": self.external_provenance.pass_index},
                "external_identity_binding": "caller-attested file hashes; session/version/arm are not internal fields",
                "internal_scope_checks": "viewer game_id, pass_index, pass_label, eventCount and lastEvent",
                "live_bridge": "unimplemented", "quality_claim": "none"}


def _bounded_bytes(path, maximum):
    """Bounded full-buffer read; fstat checks opened-FD stability, not path continuity."""
    try:
        descriptor = os.open(Path(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise SidecarContractError("source must be a readable regular non-symlink file") from None
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= maximum:
            raise SidecarContractError("file size/type exceeds reader contract")
        remaining = before.st_size
        chunks = []
        while remaining:
            block = os.read(descriptor, min(65_536, remaining))
            if not block:
                raise SidecarContractError("source changed or was truncated during read")
            if len(block) > remaining:
                raise SidecarContractError("actual read exceeded its byte budget")
            chunks.append(block)
            remaining -= len(block)
        after = os.fstat(descriptor)
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if identity(before) != identity(after):
            raise SidecarContractError("source changed during bounded read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise SidecarContractError("duplicate JSON key")
            result[key] = value
        return result

    def finite(number):
        value = float(number)
        if not math.isfinite(value):
            raise SidecarContractError("nonfinite JSON number")
        return value

    def constant(_):
        raise SidecarContractError("nonfinite JSON constant")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_float=finite, parse_constant=constant)
    except (ValueError, RecursionError, UnicodeError):
        raise SidecarContractError("invalid strict JSON document") from None
    if type(value) is not dict:
        raise SidecarContractError("JSON event must be an object")
    return value


_COMMON = {"board", "board_ascii", "score", "state", "level", "run_status"}
_SCHEMAS = {
    "initial": _COMMON | {"type", "title", "action_num", "analysis_step", "action_display", "reward"},
    "action": _COMMON | {"type", "title", "action_num", "analysis_step", "action_name", "action_display", "reward",
                          "board_changed", "done", "level_completed", "game_over", "run_complete", "batch_index", "batch_size"},
    "analysis": _COMMON | {"type", "title", "action_num", "analysis_step", "transcript"},
    "experiment": {"type", "experiment", "title", "action_num", "analysis_step", "animation_awareness", "counters"},
}
_VIEWER_KEYS = {"game_id", "agent_name", "status", "pass_index", "pass_label", "eventCount", "lastEvent", "viewer_steps", "replay_url",
                "levels_completed", "total_levels", "actions_per_level", "final_score"}


def _validate_row(row):
    kind = row.get("type")
    if type(kind) is not str or kind not in _SCHEMAS:
        raise SidecarContractError("unknown event type")
    required = _SCHEMAS[kind]
    allowed = required | ({"animation"} if kind == "action" else set())
    if not required <= row.keys() or not row.keys() <= allowed:
        raise SidecarContractError("event fields disagree with pinned schema")
    _integer(row["action_num"], "action_num")
    if kind != "initial":
        _integer(row["analysis_step"], "analysis_step")
    if kind != "experiment":
        _integer(row["level"], "level", 1)
        if row["state"] not in ("NOT_FINISHED", "NOT_PLAYED", "GAME_OVER", "WIN"):
            raise SidecarContractError("unknown raw engine state")
    if kind == "action":
        flags = {name: _boolean(row[name], name) for name in ("done", "run_complete", "game_over", "level_completed", "board_changed")}
        if (flags["done"] != flags["run_complete"] or flags["run_complete"] != (row["state"] == "WIN")
                or flags["game_over"] != (row["state"] == "GAME_OVER")
                or sum(flags[name] for name in ("run_complete", "game_over", "level_completed")) > 1
                or (flags["level_completed"] and row["state"] != "NOT_FINISHED")):
            raise SidecarContractError("raw state/done/outcome flags disagree")
        if not isinstance(row["action_name"], str) or not re.fullmatch(r"RESET|ACTION[1-7]", row["action_name"]):
            raise SidecarContractError("unknown engine action name")
        _integer(row["batch_index"], "batch_index", 1)
        _integer(row["batch_size"], "batch_size", 1)
        if row["batch_index"] > row["batch_size"]:
            raise SidecarContractError("invalid batch index")
    return kind


def parse_sidecar(sidecar_path, viewer_path, *, expected_sidecar_sha256,
                  expected_viewer_sha256, provenance: Provenance, limits=Limits()):
    """Authenticate retained files, then emit only scalar actual ActionEvents.

    No live execution authority is established by this utility. The hashes must
    be supplied from a trusted exact-version fetch; paths/filenames are not proof.
    """
    provenance.validate()
    limits.validate()
    for value in (expected_sidecar_sha256, expected_viewer_sha256):
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
            raise SidecarContractError("expected SHA256 must be a lowercase 64-hex digest")
    sidecar = _bounded_bytes(sidecar_path, limits.file_bytes)
    viewer_raw = _bounded_bytes(viewer_path, limits.file_bytes)
    if hashlib.sha256(sidecar).hexdigest() != expected_sidecar_sha256 or hashlib.sha256(viewer_raw).hexdigest() != expected_viewer_sha256:
        raise SidecarContractError("retained source SHA256 mismatch")
    viewer = _json(viewer_raw)
    if set(viewer) != _VIEWER_KEYS:
        raise SidecarContractError("viewer fields disagree with pinned schema")
    if (viewer["game_id"] != provenance.game_id or type(viewer["game_id"]) is not str
            or _integer(viewer["pass_index"], "viewer pass") != provenance.pass_index
            or type(viewer["pass_label"]) is not str or viewer["pass_label"] != str(provenance.pass_index)):
        raise SidecarContractError("viewer game/pass differs from caller scope")
    lines = sidecar.split(b"\n")
    if lines[-1] == b"":
        lines.pop()
    if not 1 <= len(lines) <= limits.events or any(not line.strip() or len(line) > limits.line_bytes for line in lines):
        raise SidecarContractError("JSONL line/event bound or empty-line contract failed")
    events = []
    anchor_count = 0
    last_action = last_row = None
    for index, line in enumerate(lines):
        row = _json(line)
        kind = _validate_row(row)
        if kind == "initial":
            anchor_count += 1
            if index != 0 or anchor_count != 1 or row["action_num"] != 0 or row["analysis_step"] is not None or row["action_display"] != "RESET" or row["state"] != "NOT_FINISHED" or row["level"] != 1:
                raise SidecarContractError("initial zero anchor disagrees with pinned schema")
        elif index == 0:
            raise SidecarContractError("initial zero anchor is missing")
        elif kind == "action":
            if row["action_num"] != len(events) + 1:
                raise SidecarContractError("actual action history is partial, duplicate or out of order")
            events.append(ActionEvent(row["action_num"], row["action_name"], row["level"],
                                      row["game_over"], row["run_complete"], row["level_completed"]))
            last_action = row
        elif row["action_num"] != len(events):
            raise SidecarContractError("non-action event counter disagrees with current history")
        last_row = row
    if anchor_count != 1 or _integer(viewer["eventCount"], "viewer eventCount", 1) != len(lines):
        raise SidecarContractError("viewer eventCount/initial anchor disagrees with sidecar")
    # Pinned writer chooses its last actual action, or last raw row when empty.
    metadata = {k: v for k, v in (last_action or last_row).items() if k not in ("board", "board_ascii", "transcript")}
    # Canonical JSON preserves strict boolean/int/float distinctions that plain
    # Python container equality loses (False == 0 and True == 1).
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if type(viewer["lastEvent"]) is not dict or canonical(viewer["lastEvent"]) != canonical(metadata):
        raise SidecarContractError("viewer lastEvent differs from actual retained metadata")
    return ParsedActions(tuple(events), provenance.watermark_scope, provenance,
                         expected_sidecar_sha256, expected_viewer_sha256, len(lines), anchor_count)
