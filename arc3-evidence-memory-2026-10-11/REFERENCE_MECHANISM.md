# The 34.30 reference: what actually differs

Checked October 11, 2026, using the public Kaggle source and notebook score card.

| Part | Released Franzen reference, V3 | Our retained public V18 / native control |
|---|---|---|
| Agent harness | Tool-using Python agent and a released 10,087-line harness patch | Exact same patch bytes |
| Reasoning model | Intel AutoRound Qwen3.8 Flash Next W4A16 | Same checkpoint route |
| Speculation | Albucino quantized drafter; FR-Spec map | Same route, with checked inputs and explicit fallback |
| Serving | Pennyroyal; SM120; chunked prefill and speculative decoding | Same principal configuration, with runtime/input checks |
| Context | 128k window, 12k output, 58k drain | Same |
| History | 150 assistant turns, 30-turn drain, coalesced eviction | Same |
| Benchmark | Four public-game passes in diagnostic mode; one official pass | Separate bounded native control: 25 games, one pass, ten slots, 2,200 seconds/game |
| Notebook operations | Released baseline | Added input/source verification, bounded startup, timing logs, owned teardown, presentation and provenance |

The [released reference](https://www.kaggle.com/code/dfranzen/arc-agi-3-milestone-2-solution)
showed notebook-best **34.30**, linked to ARC-AGI-3, at 21:17:54 UTC. The
displayed current and most-recent run IDs matched, but that still does not bind
the card's best score to an exact completed submission row for V3. Our **30.65**
was bound to our own completed official submission. The visible gap is **3.65
points**; it is not a measured effect of any particular source difference.

Our two identical controls produced local means **44.238** and **35.882**. Their
8.356-point difference is substantial relative to a proposed +2-point screen
threshold. That threshold is a budget filter, not evidence of a new best agent.

The most useful new factor is a closed loop that preserves executed observations
after the conversation discards their source turns. The existing world-model
sections summarize the model's beliefs. This tool carries a bounded sample of
observed endpoints and exact action displays, leaving the model free to revise
its beliefs when identical visible inputs have produced different results.

The new source has not run in a native ARC environment. It cannot establish a
score gain, official readiness, complete animation capture or hidden-state
identity. It will first be evaluated on the same complete 25-game screen.

All third-party baseline attribution and terms remain separate. This package
provides an original interoperation adapter and tests; it reproduces no foreign
harness implementation or checkpoint. Franzen/Tufa, Pennyroyal, Qwen, Intel
AutoRound and Albucino retain credit for their respective contributions.
