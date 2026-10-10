# ARC-AGI-3 Milestone-2 serving logs and metrics (RTX PRO 6000)

Measured serving behaviour of the Milestone-2 (M2) stack that our public ARC-AGI-3 notebook runs. The measurements come from our notebook runs of versions V15, V16 and V17 on one NVIDIA RTX PRO 6000 inside a Kaggle GPU notebook, with 10 concurrent game streams. V15, V16 and V17 are our own labels for those notebook versions and runs; V16 and V17 also appear as the version names in the Kaggle submission descriptions quoted below. The three official rows are our own Kaggle submissions.

The stack is Daniel Franzen's M2 recipe: Qwen3.8-Flash-Next W4A16 (Intel AutoRound) served by an SGLang build (Pennyroyal v2.5.3, from the Kaggle wheelhouse `dfranzen/pennyroyal-v253`), EAGLE speculative decoding with an FR-Spec token map and a draft checkpoint by Albucino, and Tufa Labs' Duck harness. None of the recipe's code or model weights is redistributed here. Credits and the licence of each component are in the Credits section.

## What is in this dataset

- Official Kaggle rows for our project: **2.95 (row 56432721), 27.83 (row 56963315), 30.65 (row 57016786)**.
- Server time series parsed from the serve logs of three notebook runs (V15, V16, V17): every decode and prefill batch, with throughput, accept length, KV-pool use and running requests.
- V17 client-side timing of 629 model requests across 10 game threads.
- V17 token, cache and finish-reason aggregates for 10 public demo games (labelled `demo_01` to `demo_10`), and a 5% random sample of per-request usage records.
- A steps finding: 4 speculative steps do not run on this stack.

Not included: prompts, system messages, tool definitions, model outputs, game frames, observations, action identities, original game identifiers, game results (scores, levels cleared, benchmark states, action counters), model weights, local file paths or credentials. The per-stream logs are summarised, not republished. `NOTICE.md` lists the fields that were removed and why.

## Why it is useful

These files give tok/s, accept length, KV-pool use, slot idle and boot times per batch, the per-request client timing, and a measured limit: on this stack 4 speculative steps fail during CUDA-graph capture, and our reading of the SGLang source puts the cap at 3 steps.

## Files

| File | Rows | Contents |
|---|---|---|
| `rows.csv` | 5 | Official Kaggle rows and serving aggregates per version, with notes. |
| `server_metrics.csv` | 4,822 | One row per decode or prefill batch from the V15, V16 and V17 serve logs. |
| `client_request_timing.csv` | 629 | V17 client-side request start, duration and HTTP status. |
| `per_stream_summary.csv` | 10 | Per demo game, V17: token totals, cache hit ratio, request counts and finish reasons. |
| `requests_sample.jsonl` | 31 | 5% random sample of V17 response records. Usage metadata only. |
| `schema.json` | | Column names, types, units and descriptions for every data file, plus row counts. |
| `README.md` | | This document: method, column reference, credits, licence, caveats. |
| `NOTICE.md` | | Per-file licence terms and the fields removed for licence reasons. |
| `LICENSE` | | Apache License 2.0, full text. |
| `MANIFEST.json` | | SHA-256 and size in bytes of every other file. |

## Official rows and headline numbers

| Version | Kaggle row | Public score | Submitted (UTC) | Status |
|---|---|---|---|---|
| Pre-M2 submission | 56432721 | 2.95 | 2026-09-21 14:11:45 | COMPLETE |
| V16 | 56963315 | 27.83 | 2026-10-08 16:50:12 | COMPLETE |
| V17 | 57016786 | 30.65 | 2026-10-09 17:57:00 | COMPLETE |

The public scores and submission times are taken from the Kaggle submission records in our account's submissions snapshot, taken 2026-10-10 11:47 UTC. Each row id and score was checked against that snapshot.

The submission descriptions, quoted verbatim from the same snapshot, are:

- V16 (56963315): "ARC3 public V16: Franzen M2 recipe (Apache-2.0 code), corrected expectation text; placeholder parquet, games scored by the gateway"
- V17 (57016786): "ARC3 public V17: Franzen M2 recipe (Apache-2.0 code) + robustness pack (fail-fast input checks with fallbacks, py3.12 pin, startup/teardown reserves), MIT TAAF bundle (byte-identical), per-stream timing log in Save&Run only; second draw of the recipe for variance-aware final selection" (the rest of the description is a file hash and a notebook reference, not reproduced here)
- Pre-M2 (56432721): no description recorded in the submission record.

**Selection rule for 2.95.** It is the highest of the three pre-M2 ARC-AGI-3 rows in our account: 56432721 (2.95), 55060904 (0.67) and 55004602 (0.60), all COMPLETE. The two other rows are not part of this dataset. Choosing the highest of three biases the baseline upward, so the gain measured from it is, if anything, understated.

Public leaderboard scores are computed on the public part of the test data. Each row is one draw of that score. V16 (56963315) and V17 (57016786) are two versions of the same Franzen M2 recipe with different code, as their descriptions above show. The 2.82-point gap between them (27.83 to 30.65) compares one draw of each, so it is unresolved: the two versions differ in code, and the gap is not attributed to either change.

Serving aggregates, from the serve logs (decode batches only, unless stated):

| Measure | V15 | V16 | V17 |
|---|---|---|---|
| Decode batches parsed | 920 | 1,009 | 957 |
| Accept length, mean (median; p10 to p90) | 2.68 (2.675; 2.48 to 2.87) | 2.69 (2.69; 2.50 to 2.89) | 2.71 (2.70; 2.50 to 2.92) |
| Accept rate, mean | 0.560 | 0.564 | 0.568 |
| Generation tok/s, mean (median) | 664.8 (719.0) | 652.9 (703.0) | 660.6 (703.5) |
| KV-pool usage, max | 0.96 | 0.92 | 0.96 |
| Server-side slot idle (recorded) | 12.8% | 17.0% | 14.4% |
| Boot to first HTTP 200 (recorded) | 767 s | 480 s | 529 s |
| Engine load_weight (recorded) | 557.2 s | 278.9 s | 320.2 s |

Values marked "recorded" come from the serve-log startup lines and from our occupancy analysis. Neither the raw lines nor the analysis is published here, so these values cannot be recomputed from the shipped files; `rows.csv` is their source.

Accept length is the mean number of tokens SGLang accepts per speculative step. Generation tok/s is SGLang's aggregate throughput across the running batch in each decode batch. Across the three runs the accept length moves by less than 0.03, and the mean throughput by less than 2%. Between V15 and V16, load_weight accounts for 278 s of the 287 s boot-time gap.

V17 request-level facts, recomputed from `client_request_timing.csv`:

- 629 model requests across 10 game threads; the last request ends about 1,504 s after the first one starts. Client durations: mean 22.4 s, median 14.6 s, p90 49.0 s, max 186.3 s.
- Six requests have no HTTP status recorded, with durations from 5.5 to 43.5 s. Our logs do not show a cause, so we do not call these timeouts.
- Client-side slot idle is 6.25%. It is 1 minus the summed request durations divided by 10 threads times the 1,504 s window.
- Tokens, from `per_stream_summary.csv` (622 responses over the 10 demo games): prompt 39,956,627, of which 94.9% came from the prefix cache. Completion 898,976, of which 81.9% (736,670 tokens) were reasoning tokens. The benchmark counts 879,780 generated tokens; the two counts come from different logs and differ by about 2%.
- Finish reasons: 621 tool_calls, 1 length.
- There are 629 request records and 622 response records. Seven requests have no matching response record, and six requests have no HTTP status. We did not reconcile the difference.

## Steps finding: 4 speculative steps do not run here

We tried 4 speculative steps (5 draft tokens) against the V16 and V17 setting of 3 steps (4 draft tokens). The server failed during CUDA-graph capture with:

> NotImplementedError: Qwen QSA requires speculative_num_draft_tokens <= the QSA compress ratio (4): the pending index-key ring holds one group; got 5

Reading the SGLang source (Pennyroyal wheel, read-only), our reading is that with top-k 1 the draft-token count is forced to steps + 1, and that must not exceed the model's QSA compress ratio of 4. So steps must be at most 3. We did not take the 4-step setting further, and no 4-step measurement exists. The row `steps4_run` in `rows.csv` records the failed attempt.

## What you can do with this

- **Accept length against batch size.** Plot `accept_len` against `running_req` in `server_metrics.csv` (decode rows) to see how speculation holds up as more streams run together.
- **Throughput against KV pressure.** Plot `gen_tok_s` against `full_token_usage` to find where KV-pool use starts to cap tok/s.
- **Where boot time goes.** Compare `engine_load_weight_s` with `boot_first_200_s` in `rows.csv` to see how much of boot is weight loading. These are recorded values (see above).
- **Tail latency of model calls.** Look at the `duration_s` distribution in `client_request_timing.csv` by `thread`, and check how the slowest calls line up with the serve-log batches.
- **Prefix cache and reasoning.** Relate `cache_hit_ratio` and `reasoning_tokens_sum` to `completion_tokens_mean` per game in `per_stream_summary.csv`.

## How to load

```python
import pandas as pd

sm = pd.read_csv("server_metrics.csv")
dec = sm[sm.kind == "decode"]
print(dec.groupby("run_label")[["accept_len", "gen_tok_s"]].agg(["mean", "median"]).round(2))
```

```python
import pandas as pd

ct = pd.read_csv("client_request_timing.csv")
print(ct["duration_s"].describe(percentiles=[0.5, 0.9]).round(2))
```

```python
import json
import pandas as pd

with open("requests_sample.jsonl", encoding="utf-8") as f:
    sample = [json.loads(line) for line in f]
sample_share = sum(r["reasoning_tokens"] for r in sample) / sum(r["completion_tokens"] for r in sample)

ps = pd.read_csv("per_stream_summary.csv")
pop_share = ps["reasoning_tokens_sum"].sum() / ps["completion_tokens_sum"].sum()

print(f"sample n={len(sample)}, sample reasoning share={sample_share:.3f}")
print(f"population reasoning share={pop_share:.3f} (all 622 V17 responses)")
```

The sample ratio is a 31-record estimate and is not the population figure. Use `per_stream_summary.csv` for the full-data share (81.9%).

## Column reference

Every column of every data file. Units are in the Unit column; blank means dimensionless or not applicable. The same definitions are in `schema.json` and in the dataset metadata.

### requests_sample.jsonl

Random 5% sample of V17 per-stream response records. Usage metadata only; no message content, no game frames, no action identities and no original game identifiers.

31 rows. Format: jsonl.

| Column | Type | Unit | Description |
|---|---|---|---|
| `demo_game` | string |  | Demo game label (demo_01 to demo_10) assigned by us. The original public game identifier is not published here. |
| `event` | string |  | Always response in this file. |
| `tool_choice` | string |  | Tool-choice mode sent with the request, as logged. |
| `finish_reason` | string |  | Finish reason reported by the server: tool_calls, stop or length. |
| `prompt_tokens` | integer | tokens | Prompt tokens, including cached tokens. |
| `cached_prompt_tokens` | integer | tokens | Prompt tokens served from the prefix cache. |
| `image_tokens` | integer | tokens | Image tokens inside the prompt. |
| `reasoning_tokens` | integer | tokens | Reasoning tokens generated (part of completion_tokens). |
| `completion_tokens` | integer | tokens | Generated tokens for the response. |
| `total_tokens` | integer | tokens | prompt_tokens plus completion_tokens, as reported by the server. |

### per_stream_summary.csv

One row per public demo game for the V17 notebook run: token totals, cache hits, request counts and finish reasons. Game results are not included (see NOTICE.md).

10 rows. Format: csv.

| Column | Type | Unit | Description |
|---|---|---|---|
| `run_label` | string |  | Notebook run that produced the row. Always v17 in this file. |
| `demo_game` | string |  | Demo game label (demo_01 to demo_10) assigned by us. The original public game identifier is not published here. |
| `benchmark_tokens` | integer | tokens | Generated tokens counted by the benchmark for the game. |
| `request_records` | integer | count | Request records in the per-stream log (event == request). |
| `response_records` | integer | count | Response records in the per-stream log (event == response). |
| `usage_missing_responses` | integer | count | Response records without a usage block. |
| `prompt_tokens_sum` | integer | tokens | Sum of prompt tokens over the game's responses (usage.prompt_tokens). |
| `cached_prompt_tokens_sum` | integer | tokens | Sum of prompt tokens served from the prefix cache (prompt_tokens_details.cached_tokens). |
| `cache_hit_ratio` | number | fraction | cached_prompt_tokens_sum divided by prompt_tokens_sum. |
| `completion_tokens_sum` | integer | tokens | Sum of completion tokens (usage.completion_tokens). |
| `completion_tokens_mean` | number | tokens | Mean completion tokens per response. |
| `completion_tokens_median` | number | tokens | Median completion tokens per response. |
| `reasoning_tokens_sum` | integer | tokens | Sum of reasoning tokens (usage.reasoning_tokens); part of completion tokens. |
| `image_tokens_sum` | integer | tokens | Sum of image tokens inside prompts (prompt_tokens_details.image_tokens). |
| `finish_tool_calls` | integer | count | Responses with finish_reason tool_calls. |
| `finish_stop` | integer | count | Responses with finish_reason stop. |
| `finish_length` | integer | count | Responses with finish_reason length (generation hit its token cap). |

### server_metrics.csv

Time series parsed from the SGLang serve logs of the V15, V16 and V17 notebook runs: one row per decode or prefill batch.

4,822 rows. Format: csv.

| Column | Type | Unit | Description |
|---|---|---|---|
| `run_label` | string |  | Run: v15, v16 or v17 (notebook runs). |
| `kind` | string |  | decode (one decode batch) or prefill (one prefill batch). |
| `log_timestamp` | string |  | Timestamp as printed by the server container; time zone not recorded (UTC assumed). |
| `t_s` | number | seconds | Seconds since the first timestamped line of that run's serve log. |
| `running_req` | integer | requests | Requests running in the batch (#running-req). |
| `queue_req` | integer | requests | Requests queued (#queue-req). |
| `kv_tokens` | integer | tokens | Tokens currently held in the KV pool (#full token), decode lines only. |
| `full_token_usage` | number | fraction | Share of the full-token KV pool in use. |
| `mamba_usage` | number | fraction | Share of the mamba state pool in use. |
| `accept_len` | number | tokens per step | Mean accepted tokens per speculative step, decode lines only. |
| `accept_rate` | number | fraction | Accept rate, decode lines only. |
| `gen_tok_s` | number | tokens/s | Aggregate generation throughput across the batch, decode lines only. |
| `new_tokens` | integer | tokens | New prompt tokens in the prefill batch, prefill lines only. |
| `input_tok_s` | number | tokens/s | Input (prefill) throughput, prefill lines only. |
| `cuda_graph` | boolean |  | Whether the batch ran under a CUDA graph. |

### client_request_timing.csv

Client-side timing of every V17 model request: start, duration and HTTP status, across 10 game threads.

629 rows. Format: csv.

| Column | Type | Unit | Description |
|---|---|---|---|
| `seq` | integer |  | Request sequence number, ordered by start time. |
| `run_label` | string |  | Run label. Always v17. |
| `thread` | string |  | Harness game thread (one thread per game stream), for example harness-game_3. |
| `t0_epoch_s` | number | seconds | Request start, epoch seconds on the notebook clock. |
| `t0_rel_s` | number | seconds | Request start relative to the first request in the file. |
| `duration_s` | number | seconds | Client-side request duration (end minus start). |
| `http_status` | integer |  | HTTP status returned. Blank where no HTTP status was recorded (6 requests; the cause is not shown in our logs). |
| `stream` | boolean |  | Whether the request used streaming. False for every record in this run. |

### rows.csv

Official Kaggle rows of this project and serving aggregates per version, with notes. Per-game demo scores are not included.

5 rows. Format: csv.

| Column | Type | Unit | Description |
|---|---|---|---|
| `row_label` | string |  | Label of the measured version or official row. |
| `competition` | string |  | Kaggle competition slug the row belongs to. |
| `notebook_version` | string |  | Our notebook version and what it changed, or the run that produced the numbers. For official rows, the Kaggle submission description, quoted verbatim. |
| `official_row_id` | integer |  | Kaggle submission row id. Blank when the version was never submitted. |
| `submitted_utc` | string |  | Submission time in ISO 8601 UTC (YYYY-MM-DDTHH:MM:SSZ), from the Kaggle submission record (submissions snapshot of 2026-10-10). Blank where the version was never submitted. |
| `public_score` | number | score points | Public leaderboard score of the official row, from the Kaggle submission record. Unit: score points. |
| `raw_status` | string |  | Row or run status as recorded by us. |
| `is_official_row` | boolean |  | True when the row is a Kaggle submission row with a leaderboard score. |
| `stack` | string |  | Serving stack description. |
| `speculative_steps` | integer | steps | SGLang speculative steps from the server arguments in the serve log. |
| `speculative_draft_tokens` | integer | tokens | SGLang speculative draft tokens from the server arguments in the serve log. |
| `engine_load_weight_s` | number | seconds | Engine startup timing: load_weight from the 'Engine startup timings' line of the serve log. Recorded value; not recomputable from the shipped files. Unit: seconds. |
| `boot_first_200_s` | number | seconds | Seconds from the first serve-log line to the first HTTP 200 answer. Recorded value; not recomputable from the shipped files. Unit: seconds. |
| `decode_batches` | integer | count | Decode batch lines parsed from the serve log. |
| `accept_len_mean` | number | tokens per step | Mean accept length reported by SGLang across decode batches. |
| `accept_rate_mean` | number | fraction | Mean accept rate reported by SGLang across decode batches. |
| `gen_tok_s_mean` | number | tokens/s | Mean of SGLang's per-batch aggregate generation throughput. |
| `gen_tok_s_median` | number | tokens/s | Median of SGLang's per-batch aggregate generation throughput. |
| `kv_usage_max` | number | fraction | Maximum full-token (KV pool) usage across decode batches. |
| `server_slot_idle_fraction` | number | fraction | Server-side slot idle fraction from our serve-log occupancy analysis. Recorded value; the analysis is not published, so the value is not recomputable from the shipped files. Unit: fraction. |
| `client_slot_idle_fraction` | number | fraction | Client-side slot idle fraction, V17 only: 1 minus the sum of duration_s in client_request_timing.csv, divided by 10 times the largest value of t0_rel_s plus duration_s. Unit: fraction. |
| `notes` | string |  | Context and caveats for the row. |

## Provenance

- **Serve logs.** We parsed SGLang's stderr lines with fixed regular expressions. `Decode batch` lines give running requests, KV usage, accept length and accept rate, generation throughput and queue length. `Prefill batch` lines give new tokens and input throughput. Times are seconds since the first timestamped line of each run. Timestamps are the container clock as printed; the time zone was not recorded.
- **Cross-check.** The decode counts and means in `rows.csv` can be recomputed from `server_metrics.csv` (for example V17: 957 decode batches, mean accept length 2.7052, mean 660.56 tok/s).
- **Per-stream records.** Response records carry the usage block. We aggregated every V17 response record and kept only numeric usage and finish reasons. A 5% random sample was drawn and written with only the fields listed in `schema.json`.
- **Client timing.** Each request's start and end times were taken from the harness timing log for the V17 run. Times are epoch seconds on the notebook clock; only differences are meaningful.
- **Official rows.** Row ids, public scores, status and submission times were taken from the Kaggle submission records in our account's snapshot (see the table above). Submission descriptions are quoted verbatim.
- **Notebook runs and scored runs.** The serve logs and client timing come from notebook runs (Save and Run) of each version. They are not logs of the scored submission run behind each official row.
- **Demo game labels.** The per-game files use labels `demo_01` to `demo_10` assigned by us, not the original public game identifiers.
- **Removed fields.** Game results (scores, levels, benchmark states) and game-progress counters (action counts, action and analysis step indices) were removed from the published files. See `NOTICE.md`.
- **Sanitisation.** No message text, game frames, observations, action identities, original game identifiers, file paths, machine names or credentials are included. We checked the files for local paths, machine names, e-mail addresses and credentials before publishing.

## Credits

People and projects whose work the measurements depend on. None of their code or model weights is redistributed here. The licence of each component is given in the dependency table below.

- Daniel Franzen (`dfranzen`): Milestone-2 recipe and harness patch.
- Jeroen Cottaar and Tufa Labs: Duck harness and TAAF source bundle.
- Intel: AutoRound quantisation of Qwen3.8-Flash-Next.
- Qwen team: Qwen3.8-Flash-Next model.
- Albucino: draft checkpoint used for speculative decoding.
- John Pezzulli: Pennyroyal SGLang fork. The Kaggle wheelhouse we ran is a separate dataset (`dfranzen/pennyroyal-v253`).
- Gabriel Olympie and Mamy Ratsimbazafy: patches credited in the Kaggle description of that wheelhouse.
- SGLang project.
- Authors of EAGLE speculative decoding (Li et al., ICML 2024) and of FR-Spec frequency-ranked speculative sampling (Zhao et al., 2025).
- Publisher: prvsiyan.

### Dependency and component licences

Licence entries show how each licence was obtained. "Dependency table" means the licence name is taken from the component's published licence, and it was not independently re-verified for this dataset. "As shown on the Kaggle page on 2026-10-08" means the Kaggle page metadata was read on that date; it was not independently re-verified.

| Component | Used for | Licence | Basis |
|---|---|---|---|
| pandas | Quick-start code in this README | BSD-3-Clause | Dependency table, not independently re-verified |
| PyTorch | Runtime of SGLang | BSD-3-Clause | Dependency table, not independently re-verified |
| SGLang | Serving engine | Apache-2.0 | Dependency table, not independently re-verified |
| Pennyroyal SGLang build (Kaggle wheelhouse `dfranzen/pennyroyal-v253`) | Serving build | Unknown ("unknown" in the Kaggle licence field) | As shown on the Kaggle page on 2026-10-08 (not independently re-verified) |
| EAGLE speculative decoding | Speculative decoding | Apache-2.0 | Dependency table, not independently re-verified |
| FR-Spec token map | Frequency-ranked vocabulary subset for drafting | Apache-2.0 | Dependency table, not independently re-verified |
| Intel AutoRound (quantisation tool) | W4A16 quantisation | Apache-2.0 | Dependency table, not independently re-verified |
| Qwen3.8-Flash-Next model weights | Base model | Qwen Community License 1.0 | Stated in the Kaggle model description of the Intel quantised instance, as shown on the Kaggle page on 2026-10-08 (not independently re-verified) |
| Intel W4A16 quantised weights | Serving model | Qwen Community License 1.0 | As above |
| Albucino draft checkpoint | Speculative drafting | Not verified | No licence record in the sources we checked on 2026-10-08. Treat as unverified. |
| Duck harness and TAAF source bundle (Jeroen Cottaar, Tufa Labs) | Game-playing harness | MIT | As shown on the Kaggle page of the bundle `jeroencottaar/taaf-kaggle-source-share` on 2026-10-08 (not independently re-verified) |
| Franzen M2 recipe code | Recipe | Apache-2.0 | As stated in our submission records for V16 and V17 (not independently re-verified) |
| Serving-build patches by Gabriel Olympie and Mamy Ratsimbazafy | Patches in the Pennyroyal wheelhouse | No licence stated in our sources | Credit only: no code from these patches is redistributed |

Model weights are not redistributed.

## Licence

- The dataset is released under **Apache-2.0** (see `LICENSE`, the full licence text). This is the licence field of the Kaggle dataset.
- `NOTICE.md` gives the per-file terms. Our measurement files are Apache-2.0. The official-row facts (row id, submission time, public score, status and the quoted submission description for the three rows with `is_official_row` true, and the two other pre-M2 scores quoted in the selection rule) are a compilation of public Kaggle submission facts and our own submission rows, offered under **CC-BY-4.0**. Both licences require attribution.
- Competition content is not included: no game environments, frames, observations, action identities, prompts, model outputs or per-game results. Model weights are not included.

## Citation

prvsiyan (2026). *ARC-AGI-3 Milestone-2 Serving Logs (RTX PRO 6000)*. Kaggle dataset. Measurements of Daniel Franzen's Milestone-2 recipe.

## Caveats

- Public leaderboard scores are computed on the public part of the test data. The private ranking may differ.
- Each notebook run is a single run, and each official row is a single draw. Treat differences of a few points as unresolved, not as effects.
- Serve logs and client timing come from notebook runs, not from the scored submission run behind each official row.
- Only V15 to V17 serve logs and V17 per-stream data are included. The pre-M2 stack logs are not.
- Timestamps are container-clock values with the time zone unrecorded.
- Hardware is an RTX PRO 6000 inside Kaggle GPU notebooks. Other hosts may boot and serve at different speeds.
- Seven request records have no matching response record, and six requests have no HTTP status recorded. We did not reconcile these differences.
- The benchmark's generated-token count (879,780) and the usage completion-token count (898,976) come from different logs and differ by about 2%.

## Changelog

- **v1, 2026-10-10.** First release: V15 to V17 serve logs, V17 per-stream token and cache aggregates, a 31-record usage sample, V17 request timing, official rows 2.95, 27.83 and 30.65, and the steps-4 finding.
