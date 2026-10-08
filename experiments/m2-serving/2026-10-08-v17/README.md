# Public V17: robustness pack, MIT bundle and the tool-gap measurement (2026-10-08)

Public V17 is Version 16 (Franzen's M2 Version 1 recipe, settings unchanged) plus four additions:
- input checks with fallbacks, run before any GPU work;
- the MIT copy of the source bundle, which is byte-identical to the previous copy;
- startup and teardown checks;
- a logging-only timing log, active in interactive runs.

Its interactive commit run completed in 2,175 s.
- All 12 input checks passed, with no fallback and no warning.
- The model server was stopped through its ownership check.

## The robustness pack changed no behaviour

Sources: `V15/V16/V17_SERVING_ANALYSIS.json` and `L8_AND_BEHAVIOUR_ANALYSIS.json`.

| Run (10 demo games, about 25 min) | V15 | V16 | V17 |
|---|---|---|---|
| mean demo score | 42.78 | 37.58 | 53.88 |
| actions per game | 150.5 | 127.9 | 139.1 |
| generated tokens per game | 83,146 | 87,389 | 87,978 |
| job generated tok/s | 547 | 576 | 585 |
| server accept length (max 4) | 2.68 | 2.69 | 2.71 |
| server gen tok/s (decode samples) | 665 | 653 | 661 |
| server boot to first answer | 767 s | 480 s | 529 s |

- **Serving is the same in all three runs.** Accept length and decode throughput agree within ±2%. The recipe's speculative decoding with the FR-Spec map was on in all three runs, since no fallback triggered.
- **The demo score swings are run-to-run noise.** The same game's score varies by up to 26 points (SD) between runs, and the paired per-game difference is V17 − V16 = +16.3 ± 11.3 (SE, n = 10). Demo-game scores are not leaderboard scores.

## Tool-gap idle time (L8), measured

The timing log covers 629 chat requests over 10 game threads in a 1,504 s window.

- **Request timings.**
  - Request latency: median 14.6 s, p90 49 s.
  - Gaps between a stream's requests (tool execution and game steps): median 0.34 s, p90 2.0 s.
  - Six requests ended in ReadTimeout, all within 4.3 s of the window's end, when the run's soft end cancels in-flight work.
- **Slot occupancy.** The client side averages 9.375 of 10 requests in flight, so 6.25% of slot time has no request in flight:
  - 3.5% is tool gaps;
  - 2.7% comes from a game that finished early. In the scored rerun, a queued game fills that slot.
- **Server view.** It averages 8.56 requests in the running batch (14.4% of slots idle; V15 12.8%, V16 17.0%). The remaining 0.81 slots are requests that are in flight but queued or prefilling. That share is the larger one, and admitting more streams does not reduce it.
- **What closing the tool gaps would buy.** Admitting more streams than slots would fill the gaps, but the server is already near saturation: pooled decode throughput is 662, 673 and 685 tok/s at 8, 9 and 10 running requests.
  - Filling the gaps adds about 0.6% throughput, and at most 4.1% if throughput scaled linearly.
  - Using a score elasticity to tokens of 0.25 on a 26–28 base, that is **about +0.04 points, and at most +0.3**.
  - That is an order of magnitude below the run-to-run spread of a leaderboard row (SD about 3.9), and KV use already peaks at 0.96 of the pool with 10 streams.
  - **We drop L8 as a lever.** The timing log stays on for monitoring.
