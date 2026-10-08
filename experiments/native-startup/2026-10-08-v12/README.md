# ARC3 cold-start diagnostic V12: the server was ready, but the canary's transport check stopped the first model call

The wider startup envelope worked. The vLLM server became ready after **1070.1 seconds**, well inside the new 2400-second limit, and setup returned **1237.2 seconds** after the bootstrap started. For the first time the one-game canary began: game `tn36-ef4dde99`, six-action budget. It stopped at its first analysis step, before any model request, after **0.073 seconds**.

The canary's transport observer rejected the call. It rejects any model call whose `proxies` mapping contains a non-empty value. That mapping is filled from environment variables, and the check was stricter than the routing that `requests` actually performs: it can be non-empty even when `requests` would connect to the local server directly. With zero actions and a crashed game, the evidence gate correctly refused to record a result. No model tokens were generated and nothing was submitted.

| | V8 | V10 | V11 | V12 |
|---|---|---|---|---|
| Readiness (s) | 1105.1 | 1185.1 | >1500 (timed out) | **1070.1** |
| Setup returned (s from start) | — | 1355.8 | not reached | **1237.2** |
| Game | 25-game pair | not reached | not reached | started; crashed at step 1, 0 actions |

Cleanup was clean. The owned server anchor confirmed its cleanup, GPU samples went from one process to empty to empty, and no process or GPU memory remained.

The next version changes one line. The observer will refuse a call only when a proxy would actually be used for the local model endpoint, and it will name the proxy keys involved. Everything else stays the same.

Files: `receipts/` contains `startup-phase.json`, `timeline.json`, `game-summary.json`, `helper-import-gate.json`, `payload-exit.json`, `caller-summary.json`, `server-release-summary.json` and `linux-lifecycle.json`. They hold typed fields and numbers only, with no prompts, transcripts, frames, environment values or URLs. `MANIFEST.json` binds the version, the candidate (`1576147ff7606db161708b09610cd4de3b595e7ce6bb04757133d0b79bf0146a`, 762,159-byte request) and every file hash.

Native run: `prvsiyan/zz-gpuchk-899422`, Version 12, notebook status ERROR, on an RTX PRO 6000 Blackwell. Measured on 8 October 2026. This is a private diagnostic, not a leaderboard result.
