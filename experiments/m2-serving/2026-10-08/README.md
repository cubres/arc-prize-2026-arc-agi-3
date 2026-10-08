# M2 serving stack: what the V15 commit run measured, and the FR-Spec check (2026-10-08)

Our public notebook now runs Daniel Franzen's Milestone 2 recipe. The code is Apache-2.0 (da-fr/arc-agi-3-solution) and the weights are under the Qwen Community License 1.0. Public V15 ran it once in a commit run. This folder holds what that run's server log shows, and the private benchmark that follows from it.

## V15 commit run (10 demo games, 25 min, RTX PRO 6000)

Source files: `V15_SERVING_ANALYSIS.json` from `analyze_m2_serving_log.py`, and `V15_OUTPUT_CHECK.json` from `check_commit_output_arc3.py`.

- **Games.** 10 demo games, 1 won. Mean score 42.78, median 41.67; 1,505 actions; 831k generated tokens. These are commit-run demo games, not a leaderboard row.
- **Boot.** 767 s from the first server log line to the first answered request: weights 555 s, CUDA graphs about 170 s.
- **Speculative decoding.** NEXTN with 3 steps and the FR-Spec 64k map.
  - Accept length averages 2.68 out of a maximum of 4 (accept rate 0.56). At 10 running requests it is 2.64.
  - Decode runs at 694 tok/s with 10 running requests.
- **Slot occupancy.** 8.72 of 10 slots busy, time-weighted, so 12.8% of slot time is idle in tool gaps. No gap with zero running requests lasted more than 15 s.
- **KV pool.** Mean 0.56, p90 0.85, max 0.96.
- **Placeholder submission.** submission.parquet has the official one-row schema. The gateway scores the games in the hidden rerun.

## Next private benchmark: FR-Spec off against the exact V16 stack

Source files: `m2_bench_cell_template.py`, `build_m2_bench.py` and `tests/`.

- **The two runs.** The notebook boots the V16 server twice:
  - first without `--speculative-token-map`;
  - then exactly as V16 builds it.

  The recipe code is reused verbatim and pinned by sha256.
- **Workload.** Each boot replays the ten per-game model-call snapshots from the commit run.
  - 10 streams, temperature 0.7, top_p 0.95, top_k 20, 2,048 tokens per request.
  - Both runs get equal windows of at most 300 s.
- **Decision rule.** Adopt "FR-Spec off" only if all three hold; otherwise keep V16 unchanged:
  - steady decode tok/s is at least 10% higher;
  - there are zero errors;
  - the KV pool is the same size.
- **Lifecycle.** Owned clock (2,580 s inside a 2,700 s session), owned server process group, and a deadline watchdog.
- **Known limits.** No images are replayed, tool results are elided, and a replay is not a live game.
- **Tests.** 46 CPU tests pass, using a stand-in server. The candidate request is 959,612 B.

## Lever status after the frontier sweep

- **Kept:**
  - rebase on M2 (done as V15/V16);
  - robustness pack (V17);
  - variance-aware submission protocol;
  - an M2-based private bench;
  - tool-gap idle time (benchmark-gated).
- **Refuted:**
  - our own priority-scheduler calibration;
  - a solved-level digest;
  - an NVFP4/FP8 checkpoint;
  - an extra indicator layer.
- **Added:**
  - a deadline-aware final schedule;
  - this FR-Spec check;
  - a pre-declared licence fallback (V17 text).

Public V16 corrects the expectation text in the prose (Franzen's own leaderboard row is 27.89; reruns score about 26–28) and keeps every V15 recipe cell. Its dry run passed and its push is pending.
