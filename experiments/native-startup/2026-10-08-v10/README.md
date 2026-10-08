# ARC3 cold-start diagnostic V10: serving became ready, the canary helper did not load

The larger startup envelope worked. vLLM became ready after **1185.1 seconds**, inside the 1500-second readiness limit, and setup returned **1355.8 seconds** after the bootstrap started, inside the 1800-second limit. The run then stopped about 4 seconds later, before any game action: the canary helper could not import the pinned `vllm_server_watchdog` module. Teardown and GPU release were clean. This produced no competition submission and no score.

The typed exit receipt keeps the initiating failure: `ModuleNotFoundError`, with no cleanup error and the release marked `NATIVE_RELEASE_PASS`. The cause is one missing line pair. The original notebook cell adds the serving bundle directory to `sys.path` immediately before this import. The extracted helper kept the import but not those two lines. The module was mounted and its pin was verified; only the import path was missing. The same helper shipped in V9, which stopped earlier, at its 574-second readiness limit. That means the post-setup canary path has not yet run natively.

| Phase | Seconds from the first bootstrap statement | Duration (s) |
|---|---|---|
| Staging, Linux lifecycle fixtures (19 tests in each of 2 modes, PASS), hardware gate | 0 – 42.1 | 42.1 |
| Setup before readiness | 42.1 – 170.6 | 128.5 |
| Readiness (limit 1500) | 170.6 – 1355.8 | **1185.1** |
| Helper load → `ModuleNotFoundError` | 1355.8 – ≈1359.6 | ≈4 |
| Gameplay | — | 0 |
| Owned teardown and GPU settle (limit 10) | ≈1359.7 – 1360.3 | 0.59 |

Weight loading dominated readiness. The main loader took 593.6 seconds over 206 shards, and the parallel PLE-offload load ran for about 949 seconds. Compilation, warmup and CUDA-graph capture took about two more minutes. The earlier successful setup, Version 8, became ready in 1105.1 seconds. The two measured cold starts therefore span 1105–1185 seconds. Two runs do not establish a distribution.

After the failure, the owned server anchor confirmed cleanup of all 148 observed descendants, including one detached process that it stopped through its process file descriptor. No owned process remained. Two empty GPU samples taken 0.51 seconds apart passed the settle check, and the caller saw no GPU process after the command. The caller's final status is HOLD only because the payload exited with code 1. No earlier HOLD receipt was promoted.

The proposed correction restores the two original lines; see [minimal-fix.diff](./minimal-fix.diff). It leaves the model, runtime, inputs, clocks and the six-action, one-game canary unchanged.

## Files

- `receipts/startup-phase.json`: typed startup clock receipt (phase names, monotonic times, no messages).
- `receipts/payload-exit.json`: initiating and cleanup exception classes and release status.
- `receipts/caller-summary.json`: owned-command result, process-group signals and the final deadline gate.
- `receipts/server-release-summary.json`: anchor cleanup counts and GPU settle samples (no process identifiers or command lines).
- `receipts/linux-lifecycle.json`: native Linux fixture gates, normal and optimized.
- `receipts/readiness-timeline.json`: numeric startup timings taken from the server log.
- `MANIFEST.json`: notebook version, candidate and request hashes, hashes of the source outputs and of each file here.

The receipts keep exception classes and numeric fields only. They contain no exception messages, prompts, frames, environment values or URLs.

Native run: `prvsiyan/zz-gpuchk-899422`, Version 10, notebook status ERROR. Candidate SHA-256 `fb072e061e7120210851dfd3c38e9cd477970ec5254b7ae13626602d531c2204`; the submitted request was 896,332 bytes, below the 900,000-byte limit. RTX PRO 6000 Blackwell, 2400-second server limit, 2350-second bootstrap clock.

Measured on 8 October 2026. This is a private diagnostic, not a leaderboard result.
