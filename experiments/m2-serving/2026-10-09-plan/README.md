# Next steps on the M2 stack: steps bench, instrumentation candidate, licence (2026-10-09)

This note records the plan and its pre-registered decision rules. None of it has run yet.

## Submissions

- **Version 17** is the 2026-10-09 submission. It is the second draw of Franzen's M2 recipe, with our robustness pack.
- **Version 16's** leaderboard row is still pending.
- No score is claimed for either version until its row resolves.

## Speculative-steps bench (private, serving only)

**Question.** Does running 4 speculative steps beat the 3 steps used in Versions 16 and 17?

**Arms.**
- `steps4`: 4 speculative steps, 5 draft tokens.
- Control: the exact V16/V17 server arguments, 3 steps.
- The FR-Spec hot-token map is on in both arms, and the two argument lists differ in exactly two values.
- Each arm replays the same ten per-game model-call snapshots from a public commit run, at 10 concurrent streams with the public sampling settings.

**Timing.** The session is capped at 2,700 s, which fits one server boot per arm; a replicate boot does not fit.
- Both arms get equal replay windows of at most 600 s, fixed after the first boot.
- A full 600 s window needs a first boot of about 515 s or less. Observed boots were 478 s, 529 s and 767 s; at 529 s the window is 586 s, and at 767 s it is 348 s.
- Below 300 s, only one arm runs and the result is reported as incomplete.

**Gate, registered before any run.** Adopt 4 steps only if all four hold:
- accept length (decode samples at 10 running requests, steady state) gains at least 8%;
- steady decode tok/s gains at least 8%;
- zero errors in both arms;
- peak KV usage is at most the control's plus 0.03.

The two gains are reported separately.

**Expected value.** A geometric model fitted to the measured accept length gives steps 4 a ceiling of about +11% accepted tokens per step, before the cost of verifying wider batches. A decode gain in the +3–5% range would be worth roughly +0.2–0.3 points.

**Schedule.** After the weekly GPU quota resets on Saturday 2026-10-10.

## Public instrumentation candidate (Version 19)

The candidate keeps every Version 17 code cell unchanged and adds three switches, all **off by default**. With the defaults the run is exactly Version 17's, and serving is unchanged.
- **Death-repeat guard.** Uses the harness's own guard, which refuses an action that ended an earlier attempt on this level from the same board state. The model can override a refusal by repeating the action.
- **Death ledger.** The ledger's advisory prompt lines stay off unless separately switched on. Added prompt text has measured negative elsewhere.
- **No-op and death counter.** Logging only, interactive runs only. Per game, it counts:
  - no-ops (executed actions that changed nothing inside the board);
  - the no-op streak, which resets on the harness's `made_progress` rule;
  - deaths, cleared levels and guard refusals.

  The wrapped harness methods return exactly what they did before.

The reasoning-effort ladder already restores the default only when an action makes progress (`made_progress`) in the shipped harness. No change was needed.

A switch is turned on only after a bench shows a gain. The candidate request is 999,977 B, close to the 1 MiB limit.

## Licence

- The Pennyroyal wheelhouse dataset (Franzen's copy, v2.5.3) shows its licence as **"Unknown"** on Kaggle. Its description says bundled packages keep their upstream licences.
- The public recipe has mounted it since Version 15, so neither the bench nor the candidate adds exposure.
- If the author never licenses it, the pre-declared fallback (M-C) stays the plan: an Apache-2.0 runtime (lordhansolo's patched vLLM) with the mixed NVFP4-FP8 checkpoint of the same model, built and checked as a new version.
- The model weights stay under the Qwen Community License 1.0.
- Since Version 17, the source bundle is Jeroen Cottaar's MIT share, which is byte-identical to the earlier copy (73 files).
