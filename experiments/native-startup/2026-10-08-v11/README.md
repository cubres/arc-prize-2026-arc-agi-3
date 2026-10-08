# ARC3 cold-start diagnostic V11: the import fix held, but model loading ran past the 1500-second readiness limit

Version 11 restored the missing import path from Version 10 and added an early check that the helper's modules resolve. The check passed **48.8 seconds** in: all seven modules resolved, none was executed and `sys.path` did not change. The run then stopped during serving startup. The vLLM server was not ready when the **1500-second** readiness limit expired, so the typed receipts record an initiating `TimeoutError`. No game action ran, and nothing was submitted.

The model files loaded much more slowly than before:

| | Version 8 | Version 10 | Version 11 |
|---|---|---|---|
| Main weight load (s) | — | 593.6 | **1109.9** |
| Total model loading (s) | 641.7 | 677.0 | **1201.1** |
| PLE-offload shard load (s) | 870 | 949 | >1404 (203/206 shards when stopped) |
| Readiness (s) | 1105.1 | 1185.1 | >1500 (timed out) |

In Versions 8 and 10, readiness was close to the PLE-offload load time plus about 235 seconds. Applying that to Version 11 suggests it would have needed roughly 1,800–1,900 seconds. That figure is an estimate, not a measurement. The receipts do not show why storage was slower.

Cleanup was clean. The owned server anchor confirmed cleanup of all 27 observed descendants and stopped one detached process. Four GPU samples went from two processes, to one, to empty, to empty within 1.55 seconds, inside the 10-second settle limit. No owned process or GPU process remained after the command.

The next version widens only the startup envelope: readiness up to 2400 s, setup 2700 s, whole run 3000 s, server limit 3100 s. The model, inputs, canary and checks stay as they are. The serving module's own readiness limit, which also sets the server's offload-loading timeout, is now set to the new value rather than capped at its built-in 1500 seconds; a CPU test confirms the server environment then carries 2400.

Files: `receipts/` contains `startup-phase.json`, `payload-exit.json`, `helper-import-gate.json`, `caller-summary.json`, `server-release-summary.json`, `linux-lifecycle.json` and `readiness-timeline.json`. They keep exception classes and numbers only, with no messages, prompts, frames, environment values or URLs. `MANIFEST.json` binds the version, the candidate (`1c38cc82bc07528891cacbeb6eaa21cc3d71d03d9fdc5edc9d6be8a6b6475d40`, 626,080-byte request) and every file hash.

Native run: `prvsiyan/zz-gpuchk-899422`, Version 11, notebook status ERROR, on an RTX PRO 6000 Blackwell. Measured on 8 October 2026. This is a private diagnostic, not a leaderboard result.
