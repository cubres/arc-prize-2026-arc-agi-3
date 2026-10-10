# ARC-AGI-3 engineering lessons

Each lesson gives the situation, the rule adopted, the evidence (ledger rows or
dates, and repository files), and how the rule was checked. Dates are UTC. Labels
are as defined in the README.

## 1. Size the readiness window from the slowest measured boot

- Situation. A private bench run (version 9, 2026-10-07) hit its readiness limit
  (574 seconds effective) before any game started. Version 10 (2026-10-08 10:29)
  raised readiness to 1,500 seconds and setup to 1,800; readiness returned after 1,185
  seconds. Version 11 (11:46) then timed out at 1,500.2 seconds, because the mounted
  weights took 1,201 seconds to load, against 677 in version 10 [V]. The cause of the
  slower load was not established; other sessions on the account were running.
- Rule adopted. Size readiness from the slowest boot measured, plus margin: readiness
  2,400 seconds, setup 2,700, whole run 3,000, server 3,100. The adapter must set these
  limits. Taking the minimum with the pinned values silently capped readiness at 1,500.
- Evidence. Version 12 (13:27 push): readiness 1,070.1 seconds, returned. Version 13
  (14:20 push): 1,215.2 seconds, returned, and a game ran [V].
- How checked. Phase timings in each version's startup receipt. Five measured boots
  (1,070 to more than 1,500 seconds) are a small sample.

## 2. Run the import gate before the expensive phase

- Situation. Version 10 ran setup for about 1,356 seconds, then failed on a Python
  import: a helper had dropped two path lines. No gameplay ran [V].
- Rule adopted. Resolve every helper import before model setup, in a gate that fails
  within about a minute. Keep the original exception in the exit receipt.
- Evidence. Version 10 result (2026-10-08). Version 11's gate passed at 48.8 seconds
  with every module resolved and none executed [V].
- How checked. Version 11's gate receipt; version 13's canary passed the native checks.

## 3. A transport hook should test the decision the library makes

- Situation. A strict hook rejected any non-empty proxy mapping on the model call. The
  HTTP library would have sent the call directly. The game crashed in 0.073 seconds with
  no model request (version 12, 2026-10-08 13:27 push) [V].
- Rule adopted. Test the proxy the library would select for the target URL. Name only
  the keys in messages, never the values.
- Evidence. Version 13 (14:20 push): 15 model requests carried the current opener's
  hash and returned success; six actions; clean teardown [V].
- How checked. A local reproduction with proxy variables set and unset. The evidence
  gate also held: it rejects any game with zero actions.

## 4. Verify a displayed leaderboard figure before quoting it

- Situation. The top public notebook's page displayed 34.30, and the campaign's prose
  for version 15 quoted it as "around 30". A forum thread (746010) gave the author's
  leaderboard row as 27.89, and a participant's four reruns gave 27 to 28 [P].
- Rule adopted. Quote a leaderboard row or a measured distribution, never a page
  display. Correct the prose before submitting. Give the reference mean and SD.
- Evidence. Ledger 2026-10-08 15:28: prose corrected in a second candidate, pushed as
  version 16. Row 56963315 scored 27.83 (z = +0.52 against 25.77 plus or minus 3.93).
  Row 57016786 scored 30.65 (z = +1.24) [V ledger; the distribution is [P]].
- How checked. The corrected candidate passed its 76 checks; the distribution was not
  re-checked on the board. A related miss: a version 18 launch at 11:33 UTC on
  2026-10-10 still said "version 17 pending", though the ledger had recorded 30.65 at 10:17.

## 5. Check licences of bundled code byte for byte before swapping it

- Situation. The base notebook bundled a copy of a source bundle with an unknown
  licence. The original, on the same platform, is MIT and lists the same byte count [V].
- Rule adopted. Swap to the original only after a file-level hash comparison, and keep
  the hash record in the repository. Keep unknown licences in the prose, and do not
  claim prize eligibility the host has not confirmed.
- Evidence. Hash check on 2026-10-08 (16:34 UTC): 73 files byte-identical, 1,518,896
  bytes, tree hash ea7b8ceb. Version 17 pushed with the MIT copy at 17:43 UTC; row 57016786.
- How checked. The hash record; live licence metadata. The weights are under the Qwen
  Community License 1.0 and the base code is Apache-2.0. Eligibility questions (threads
  743753, 745079, 745837) were unanswered by the host [P].

## 6. Read the serving source for hard limits before benchmarking a parameter

- Situation. A bench compared 4 speculative steps with 3. Independent checks had already
  flagged the runtime's version constraints. The steps-4 server failed at CUDA-graph
  capture after about 300 seconds; the run cost 408 GPU-seconds.
- Rule adopted. Before varying a parameter in a bench, read the serving stack's own
  checks on it and write the bound into the design. Here the attention backend refuses
  more draft tokens than the model's compression ratio of 4, so at most 3 steps.
- Evidence. Ledger 2026-10-10 11:13:47 and 11:16:48; closure note 1cc60a2 in the repository.
- How checked. The relevant lines of the runtime wheel were read after download,
  without execution (sha256 prefix d0620216). The conclusion does not need a live test.

## 7. A replay bench measures only the workload it replays

- Situation. The M2 bench template replayed ten snapshots in loops, with no tool gaps.
  A twelve-stream arm needed twelve snapshots; only ten existed. Duplicates would share
  the prefix cache and hide KV pressure. The pooled 10-against-8 stream comparison
  (+1.9 percent mean) reversed to about -1.6 percent when matched by time [V-derived].
- Rule adopted. Write the tested mechanism into the design and check the workload has
  it (tool gaps, KV tail). Compare arms at matched times. Pre-register the gate and
  state its false-pass rate; a +3 percent gate passes a zero effect about 20 to 30
  percent of the time [V-derived].
- Evidence. Check notes from 2026-10-08 evening on the version 15, 16 and 17 logs.
- How checked. Arithmetic on the logs in matched 150-second bins; a read of the replay loop.

## 8. Passive counts show activity, not waste; live runs show delivery, not quality

- Situation. Server logs showed a 12.8 percent running deficit, first read as idle
  time. Request-trace analysis counts repeated action counters, but a repeat can be
  inspection or planning. A one-game live canary (version 13) showed that feedback
  reached the model; it played six actions, which says nothing about quality.
- Rule adopted. Label passive counts as monitoring. Do not infer waste or benefit from
  them. Use paired live designs for mechanism claims. Keep canary pass conditions to delivery.
- Evidence. Version 13 result (14:20 push, 96.25 seconds, six actions). Version 17
  analysis (ledger 19:40 UTC). The passive analyzer's README in
  request-trace-diagnostic-2026-10-09/ states the same limit.
- How checked. The version 13 receipts, the version 17 analysis file and the README.

## 9. Pick configurations by mean across rows, not by the best row

- Situation. Two rows of the same recipe gave 27.83 and 30.65; the earlier notebook's
  row (2.95) is a different configuration. A sweep check found that a rule of "mean
  difference of at least +2 across 3+3 rows" passes a true zero effect about 27 percent
  of the time, and conflicts with the variance rule.
- Rule adopted. Compare configurations by mean across rows, with the threshold
  max(4, 2 times SD times sqrt(2/n)): 7.9 for two rows, 6.4 for three, at SD 3.93. Treat
  each row as one draw.
- Evidence. Rows 56963315 and 57016786 differ by 2.82, below the 7.9 threshold.
- How checked. Arithmetic. The SD is borrowed from other people's unchanged copies [P].

## 10. Operations: session timeouts, retries and detached runners

- Situation. (a) A push without a session timeout reserved the machine's maximum (9
  hours, 32,400 GPU-seconds) while it ran, and the quota gate refused other launches
  (ledger 2026-10-08 15:20). (b) An HTTP 429 came back on a read (14:55). The ledger first
  logged a failed pre-push read; a later entry (15:20) showed the first push had gone
  through and the 429 hit the post-push read. A retry would have created a duplicate
  version, and the retry loop was stopped. (c) Detached submission runners died when the
  session restarted before 00:00 UTC on 2026-10-09, so no midnight submission was made
  (ledger 2026-10-09 17:54). The row was submitted by hand at 17:57.
- Rule adopted. Set an explicit session timeout on every push. Before any retry, check
  whether the earlier call already succeeded. Check the daily submission slot by hand,
  not only through a detached runner.
- Evidence. The ledger entries above; the version 15 push at 14:54:22 landed before the 429.
- How checked. The ledger entries and the push receipts.
