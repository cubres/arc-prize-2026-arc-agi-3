# ARC3 cold-start diagnostic V13: first complete native run of the temporal-feedback canary

Version 13 ran the whole chain on an RTX PRO 6000 and passed. The run went through:
- native Linux lifecycle fixtures;
- the helper import check;
- model-server readiness after **1215 seconds**, inside the 2400-second limit;
- one public game at a six-action cap;
- confirmed cleanup of the owned server and a GPU release check;
- a final receipt at **1483.5 seconds**.

The canary's status is `NATIVE_HOOK_CONSUMPTION_PASS`, the owned command returned 0, and the notebook is COMPLETE.

| | V12 | V13 |
|---|---|---|
| Readiness (s) | 1070.1 | 1215.2 |
| Game | crashed at its first analysis step, 0 actions | `gave_up` at the 6-action cap after 96.25 s |
| Model requests carrying the feedback opener, answered 2xx | 0 | **15 of 15** |
| Distinct rendered feedback revisions completed by the model | 0 | **5** (at least 2 required) |
| Tokens generated | 0 | 10,831 (about 112 per second) |

**What the receipts show.**
- **Delivery.** Each model request was matched against the hash of the feedback text rendered for the current action, so the counts above show the feedback was actually inside the requests the server completed. Only hashes and counters are kept, never prompts, frames or model outputs.
- **Terminal evidence.** The game's terminal record binds the six-action history by its sha256.
- **Two changes made this run possible.** The transport check now refuses only a proxy that would really be used for the local model server, and the game had a bounded wider window with a 120-second limit per model call.

**What it does not show.** It says nothing about quality: one game, six actions, score 0. Whether the temporal-feedback opener helps is the next experiment, run on the full 25-game public panel against an unchanged control.

Files: `receipts/` contains `timeline.json`, `startup-phase.json`, `helper-import-gate.json`, `delivery-summary.json`, `game-summary.json`, `terminal-evidence.json`, `payload-exit.json`, `caller-summary.json`, `server-release-summary.json` and `linux-lifecycle.json`. They hold typed fields, counters and hashes only, with no prompts, transcripts, frames, environment values or URLs. `MANIFEST.json` binds the version, the candidate (`522bccdc37c2e87c59d97319cd191ef3a06cede422a5da03c5e17ed3a3d54875`, 898,803-byte request) and every file hash.

Native run: `prvsiyan/zz-gpuchk-899422`, Version 13, notebook status COMPLETE. Measured on 8 October 2026. This is a private diagnostic, not a leaderboard result.
