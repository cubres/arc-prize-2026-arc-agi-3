# Speculative steps cannot go above 3 on this serving stack, so the steps lever is dropped (2026-10-10)

## What ran

This was the private serving bench registered in `2026-10-09-plan/`, comparing steps 4 with the Version 16/17 control (steps 3). It ran once after the quota reset and ended after 408 s with no decision.

- **Steps-4 arm:** the server was configured with `--speculative-num-steps 4`, `--speculative-eagle-topk 1`, and 5 draft tokens. It died during CUDA-graph capture, about 300 s into its boot, with:
  > Qwen QSA requires speculative_num_draft_tokens <= the QSA compress ratio (4): the pending index-key ring holds one group; got 5
- **Control arm:** skipped, because a gate decision needs both arms.

## Why steps 4 is impossible here

Source read from the Pennyroyal SGLang build that the recipe ships (`sglang-0.5.19+gd00d88efc8d6`):

- `srt/layers/attention/qwen_sparse_attn_backend.py`, `_require_chain_speculation`. For this model's sparse attention (QSA):
  - target verification supports only `speculative_eagle_topk=1` (a chain, no draft tree);
  - verification also needs `speculative_num_draft_tokens` ≤ the QSA compress ratio, which is 4 for this model. A wider window would collide in the pending index-key ring.
- `srt/arg_groups/speculative_hook.py`: with `speculative_eagle_topk=1`, `speculative_num_draft_tokens` is always set to `speculative_num_steps + 1`.

Together these give steps + 1 ≤ 4, so **steps ≤ 3**.
- Steps 4 with 4 or fewer draft tokens has no valid form: topk 1 rewrites the draft tokens to 5, and topk > 1 is rejected.
- The Version 16/17 setting (steps 3, 4 draft tokens) is already at the limit.
- The only other valid settings are steps 1–2. They lower the accept-length ceiling (steps 2 is about −15% on a geometric fit to the measured accept length 2.68 of 4), so their expected value is not positive.

## Decision

- The speculative-steps lever is dropped, and serving stays exactly as in Versions 16 and 17.
- The earlier +0.1 to +0.3 point estimate no longer applies.
- No further steps run is planned.

## Lesson

Read the serving source for hard constraints on the parameter being swept before spending GPU time. Here the limit was in the attention backend, and the run cost 408 GPU-seconds.
