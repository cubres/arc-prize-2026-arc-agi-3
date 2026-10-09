# Reading ARC3 request traces without mistaking reasoning for waste

`analyze_recorded_responses.py` is an original, standard-library-only passive
analyzer. It reads your own JSONL response logs, hashes their bytes, and groups
consecutive responses by action counter. It reports token counts, finish
reasons and the largest repeated-counter groups; it executes no model or game
and sends no network request.

The current CLI expects ten `*_p0_requests.jsonl` files and writes a new output
with exclusive creation. Supply logs you are allowed to analyze; no request
log, prompt, game state, private payload or checkpoint is included here.

```bash
python3 analyze_recorded_responses.py /absolute/path/your_demo_logs \
  /absolute/path/new_response_aggregates.json
```

An unchanged action counter can include valuable inspection, shape matching,
program search and planning. These counts do not establish wasted compute or
the benefit of an action cap. Logged late responses can also fall outside the
native game metric's cutoff; do not substitute aggregate token totals for
official evaluation.

The [current Franzen write-up](https://raw.githubusercontent.com/da-fr/arc-agi-3-solution/main/WRITEUP.md)
reports inconclusive benefits from remembered fatal/no-op/death guards.
Speculative decoding steps 3 versus 4 is a separable serving question: measure
it under equal request windows and unchanged model/cache/prompts, then require
paired equal-time gameplay qualification. A throughput improvement is not
automatically a score improvement.

The analyzer and this documentation are original work for `cubres`, MIT.
Third-party solver, source bundle, runtime and model licenses remain separate.
No third-party implementation is included.
