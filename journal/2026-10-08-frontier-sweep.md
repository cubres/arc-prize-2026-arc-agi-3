# ARC-AGI-3 public frontier, 2026-10-08

This is the frontier sweep for the ARC-AGI-3 campaign. The read-only sweep ran
from 14:41 to 15:20 UTC on 2026-10-08, and a verification pass followed the same
day. Everything came from public pages: the leaderboard view, notebook source and
metadata, dataset and model metadata, and public discussion threads. Nothing was
run, forked or submitted. The sweep read the discussion pages in a signed-out
browser, because the forum API calls were rate-limited.

Labels are defined in the README.

## 1. The leaderboard

Leaderboard view, read at 14:39 UTC [V page]. It covers about half of the test
data and 3,984 teams.

| Rank | Team | Score |
|---|---|---|
| 1 | Tufa Labs | 55.89 |
| 2 | Yi-Chia Chen | 55.77 |
| 3 | Majkel1337 | 42.66 |
| 10 | (not named in sweep) | 37.07 |
| 21 to 49 | (dense band) | 34.30 down to 33.09 |
| 50 | (not named in sweep) | 33.09 |
| 100 | (not named in sweep) | 31.76 |
| 200 | (not named in sweep) | 30.73 |

- The top two teams did not publish a recipe. A discussion post says the first
  and second place teams and the ninth place team will not release their methods
  before the end of the competition [P]. The method behind 55.89 is unknown.
- The campaign's own displayed score on the leaderboard was 2.95 (row 56432721,
  2026-09-21) [V]. That is outside the top 200.

## 2. Two notebook families

The public notebooks fall into two families [V page].

- The Milestone 2 family. A Tufa Labs harness with a patch from dfranzen, the
  Qwen3.8-Flash-Next model (W4A16 quantization) with an INT4 multi-token-prediction
  drafter, served by SGLang Pennyroyal 2.5.3, with 10 resident game streams and
  priority scheduling. Displayed scores run from 20 to 34.30.
- The older vLLM NVFP4 family. This includes the campaign's own notebook.
  Displayed scores run from 1.3 to 6.1. The sweep listed keithtyser 3.38,
  wuliao0 4.33, chiakazirim 4.5, one further notebook at 6.09, and the
  campaign's notebook 2.95.

Two notebooks with different model and runtime inputs from the base recipe scored
above 20: lordhansolo's own vLLM build (23.84, mixed NVFP4-FP8 checkpoint, 14 streams) and sirikilohit's
rellik13 notebook (22.53, Pennyroyal 2.5.0, 16 streams) [V page].

Top entries by displayed score [V page, unless tagged]:

| Displayed (version) | Notebook (public slug) | Change over the base recipe | Machine |
|---|---|---|---|
| 34.30 (V1) | dfranzen/arc-agi-3-milestone-2-solution | Base. Apache-2.0 | RTX PRO 6000 |
| 31.93 (V9) | sujanmajhisuzan/arc-agi-3-m2-top-submission | Prompt hooks and a changed slot priority | RTX PRO 6000 |
| 31.73 | leoprovorov/[...]-handbook-harness | Unchanged copy of the base [P], plus a CPU analysis layer | CPU |
| 31.66 | skarin/arc-agi-3-27-80-lb-100-trajectory-audit | Unchanged v1 solver plus a CPU audit | RTX PRO 6000 |
| 31.54 | shiiin9/affectify-arc-31-54-in-a-single-sub | Only the slot priority changed; coefficients not published | RTX PRO 6000 |
| 31.27 | sigeward/arc-agi-3-milestone-2-solution | Robustness only: input checks, a 7-minute startup timeout, fallbacks | RTX PRO 6000 |
| 28.52 | hknight888/hknight3-0 | Byte-identical to the base [V sha] | RTX PRO 6000 |

Most notebooks from 29 to 32 sit inside one standard deviation of the
unchanged-copy distribution (25.77 plus or minus 3.93, see section 3). The sweep
found no public notebook with a measured gain over the base [I].

## 3. Displayed figures that were checked

1. 34.30 for the base notebook's version 1. The notebook page displayed it
   [V page]. A forum thread (746010, read 14:57 UTC) says the author's own
   leaderboard row is 27.89 [P]. It also says the same page showed 31.47 about
   2026-10-04 [P]. One participant ran the unchanged notebook four times and got
   27 to 28 each time [P]. The sweep treats 34.30 as a display figure, not a
   score, and gives the leaderboard row as the reference.
2. Unchanged copies on the leaderboard: mean 25.77, SD 3.93, median 26.19,
   range about 20 to 34 (thread 745062) [P]. The sweep did not check these rows
   on the board. Later the campaign used this mean and SD as the reference for
   z values.
3. Public-25 mean 46.49 for the base notebook's version 3 (4 passes, 417 of 732
   levels, 33 of 100 wins). It was recomputed [V] from 100 trajectory records
   embedded in a public notebook. Its ratio to the leaderboard row (27.89) is
   0.60 [I, one pair]. Applied to the campaign's own public-25 mean of 4.33, that
   gives about 2.6, close to the campaign's 2.95 row [I].
4. Runtime. A figure in the task brief says 12 hours. The host post (697944) says
   9 hours, and every pulled notebook pins 32,400 seconds [V]. The sweep uses 9
   hours.
5. Pass means of the public-25 runs look stable (SD 0.93). That stability is an
   artefact of coupling: the passes share one scheduler. Within-game SD is 17.4 and
   the per-game paired-difference SD is 24 to 40 [V computed].
6. A draft quota statement said a 15,600 GPU-second test would use about 30
   percent of the remaining weekly quota. That was wrong. It is 9.6 percent of
   the 162,000-second weekly allowance [V arithmetic].
7. The campaign's own public-25 mean was 4.33 on 21 of 183 levels, with 0 wins
   [V measured data].
8. "Scored reruns are not charged to GPU quota" comes from an earlier measurement
   [P]. The sweep flagged it for re-checking. A short rerun of another notebook on
   the same account showed no visible charge, but the campaign's own rerun window
   was confounded by concurrent commits [I]. It stays open.

## 4. Datasets, models and licences

Metadata and live checks [V], unless tagged otherwise.

| Asset | Licence as shown | Notes |
|---|---|---|
| Base notebook code | Apache-2.0 (its GitHub repository) | The notebook metadata has no licence field. Its markdown says third-party code and weights keep their own licences. |
| dfranzen/pennyroyal-v253 (wheelhouse) | Unknown | The description says bundled packages keep their upstream licences. The SGLang-derived source is Apache-2.0 on GitHub [V]. Other wheels were not inspected. |
| dfranzen/taaf-kaggle-source-bundle-copy | Unknown | Described as an identical copy of the Tufa Labs bundle. Same byte size as the MIT original. |
| jeroencottaar/taaf-kaggle-source-share | MIT | Same total bytes (1,518,896) as the copy. A file-level hash check was still needed. |
| dfranzen/intel-qwen3.8-flash-next-w4a16-autoround | Listed as "Other"; described as Qwen Community License 1.0 | Model weights. |
| dfranzen/albucino-qwen3-8-flash-next-drafter | Qwen Community License 1.0 | Drafter. |
| nvidia/qwen3-8-flash-next-nvfp4 | NVIDIA Open Model License | Not used by the top notebooks. |
| lordhansolo vLLM runtimes and TAAF source | Apache-2.0 | Alternative path. |
| Runtime datasets of the campaign's earlier notebook | Unknown | In use before the sweep. |

Whether an unknown-licence dependency or the Qwen licence blocks prize
eligibility was not answered by the host. The threads are 743753, 745079 and
745837 [P].

## 5. Discussion and write-up claims

All items are [P] unless tagged. They are paraphrased.

- Host posts [V]: a 9-hour runtime (697944); one submission per day, with
  surplus submissions invalidated (705405). The milestone deadline times in
  713634 concern the milestone prizes, not this final deadline.
- Queue waits of 6 to 17 hours for RTX PRO 6000 were reported from 2026-10-05
  to 10-08 (745951). Two concurrent GPU sessions per user were also reported
  (742148).
- Some reruns ended after 2 to 4 hours instead of 9 (744995). Such a run could
  silently lower a score.
- The base author's write-up (dfranzen) reports that the 10x image scale was the
  largest image gain, and that undo, action information, level transfer and
  persistent functions together gave "a large improvement" (not isolated). It
  reports that a structured world model, summarisation and stronger verification
  did not clearly help, and about 150 rented GPU-hours.
- rellik13's write-up gives a leaderboard history from 0.99 (August) to 22.53
  (end of September). It attributes +8.0 to a change in KV-cache precision plus a longer
  history, which was confounded with other changes. It reports -2.3 for extra
  prompt text on every call and -3.4 for level-start advice.
- lordhansolo's write-up says the score follows the number of turns each game
  gets, and that no harness change could be confirmed as an improvement without
  A/B compute.
- A harness-experiments thread (743723) reports isolated harness layers at or
  below baseline. It also reports that 83 percent of stuck-run forks had already
  tried the decisive action type, so the failure lies in goal judgement.
- Fine-tuning reported no gain (742835, 743319). A DeepSeek V4 Flash attempt was worse
  than Flash-Next on token efficiency and decode speed (742788).
- ACTION7: the public docs call it a simple undo. Naming it UNDO helped one
  author's score (n=1). The base patch maps ACTION7 to UNDO [V diff] (742477).

## 6. Lever verdicts from the sweep's verification

The sweep listed nine levers (L1 to L9). Its verification pass kept five and
dropped four. The verdicts below are the verification's, dated 2026-10-08.

| Lever | Verdict | Verification note |
|---|---|---|
| L1 Rebase on the Milestone 2 recipe | Kept, rank 1 | Expected +20 conservative, +23 point, to about 26. One-row 90 percent band about 18 to 33 [I]. |
| L2 Redirect the private bench to the M2 stack | Kept, rank 4 (process) | No leaderboard effect. Map the hooks onto the M2 patch on CPU first. |
| L3 Variance-aware submission protocol | Kept, rank 3 (protective) | Threshold max(4, 2 times SD times sqrt(2/n)): 6.4 at n = 3, 7.9 at n = 2. The finals rule is unverified. |
| L4 Robustness pack | Kept, rank 2 (protective) | Reject the 7-minute startup cap. Keep at least 720 seconds, because the base's healthy startups took about 531 seconds [P]. |
| L5 Scheduler calibration | Dropped | The leaderboard rule is underpowered: a true zero effect passes about 27 percent of the time. |
| L6 Solved-level digest | Dropped | Level transfer and persistent functions are already on in the run config. The +2.8 is inside row noise. |
| L7 NVFP4/FP8 checkpoint | Dropped | Its footprint argument fails: the mirror is 180.17 GB against 181.24 GB for the current checkpoint [V metadata]. |
| L8 Close tool-gap idle time | Kept, benchmark-gated | Best case +0.2 to +0.8. Measured later on the campaign's own logs (see the strategy and state documents). |
| L9 Indicator-notes and budget-alert layer | Dropped | Evidence is n=10 observational copies. Added text has hurt in measured cases [P]. |

Missing levers added by the verification:

- M-A, deadline-aware final schedule. No GPU. The rerun can take up to 9 hours
  [P], and queues of 6 to 17 hours were reported [P]. The last useful submission
  must start about 26 hours before the deadline. The deadline's time of day was
  not confirmed.
- M-B, a speculative-decoding step and FR-Spec check. The source uses 3 steps and
  an FR-Spec map of 64k [V source]. Expected 0 to +1, not measured. It was later
  closed by a serving-source limit (see the strategy document).
- M-C, a pre-declared licence fallback to an Apache-2.0 path, if unknown-licence
  dependencies are ruled ineligible. Expected 0 on score. It protects eligibility.

Corrections the verification made to the sweep itself:

- The campaign's notebook was already at version 15 when checked, and its live
  datasets showed the two unknown licences. The bundle copy can be swapped for the
  MIT original after a hash check.
- The final-selection rule and the deadline time of day were not verified. The
  rules, overview and evaluation pages returned shells.

Open items when the sweep ended: the finals rule and deadline time; whether
reruns are charged to quota; the coordinator's decision on the Pennyroyal licence;
whether reruns honour the container image digest pin, which is not confirmed by
the host (745654) [P].

## 7. What followed the same day

- Version 15, the credited rebase, was pushed at 14:54 UTC. Its commit run played 10
  demo games (mean 42.78, median 41.67). Demo games are not leaderboard rows.
- Version 16, with corrected text, was pushed at 16:05 UTC and submitted at 16:50 UTC
  as row 56963315 (score in the state document).
- Version 17 added a robustness pack, the MIT bundle swap and a timing log. It changed
  no measured behaviour; tool gaps were 3.5 percent of slot time. L8 was dropped at 19:40 UTC.
