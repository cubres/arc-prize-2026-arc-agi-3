# ARC-AGI-3 V23 output check — 2026-10-25

## What ran

Notebook: [ARC-AGI-3 Stock TAAF Action7 Shadow](https://www.kaggle.com/code/prvsiyan/arc-agi-3-stock-taaf-action7-shadow?scriptVersionId=360210266), V23, native version 360210266.

The exact V23 outputs were recovered once, with the same 17 metadata fields, source digest, and COMPLETE status checked before and after the read. Six expected files were acquired in 5.126 seconds. No notebook was edited and no new submission was sent.

## What the check establishes

The unchanged full-output verifier passed for ten public demo games. All ten have terminal records, non-reset actions, matching model-to-tool traces, and valid sampled resource receipts.

| Measure | V23 public demo run |
|---|---:|
| Games won | 1 / 10 |
| Games ended by give-up | 9 / 10 |
| Mean local game score | 35.7061 |
| Engine actions | 1,099 |
| Qualified clean model actions | 995 |
| Model calls returned / failed | 521 / 7 |
| Sampled GPU peak | 97.95% |

These ten-game local scores do not measure the hidden competition score. The notebook page currently displays 30.65 for V17. It is not a V23 leaderboard result.

## Limits and next experiment

The ten-game trace is too small to publish as a general-purpose dataset. GPU use peaked near the device limit, and the 15-second samples do not prove the longer hidden competition run fits. The input receipt also does not verify the model-weight content hashes or reproduce the original V1 runtime image.

The next useful experiment is to inspect the seven failed model calls and the two games with the largest gaps between engine actions and qualified model actions. The traces provide leads, not causes. Any change should first be compared on the same games and scored with the official public-run method.

The exact acquired-output and validation receipts are retained in the local ARC3 run audit. No public-score improvement is claimed.
