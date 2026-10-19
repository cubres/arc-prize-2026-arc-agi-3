ARC3 prospective empty-animation schema refinement

STATUS: separate source-only future proposal. Not integrated into any notebook,
solver, approved R3/R4 packet, freeze, dispatcher, guard or attempt marker.
No actual game, model, competition API or network was run for this proposal.

The observed failure mechanism
------------------------------
The pinned baseline enables ARC3_ANIMATION=1; its timeline option defaults true.
Its build_animation_view returns an error-only dictionary when the record is
absent or the collapsed chain has at most two entries. The producer stores no
animation record when summarize_animation returns None. A single engine frame
therefore normally reaches this branch with record=None.

The exact sandbox _LazyAnimation proxy forwards indexing to that dictionary.
A synthetic call to proxy["frames"] or proxy["steps"] consequently raises
KeyError. This is an executable interface reproducer, not a claim that a scored
production run was observed to fail there or that models always use indexing.

Small independent change
------------------------
complete_empty_animation_view recognizes only the exact one-key legacy error.
It retains the error and adds action, frames=0 and steps=[]. It returns normal,
precompleted, disabled and unrelated-error dictionaries by identity. It does not
coerce other errors, retry, invent action provenance or execute an action.

    executed action -> observed chain -> stored record (or None)
                                             |
                                      read-only query
                                             |
                                       legacy renderer
                                             |
                                      narrow pure adapter
                                             |
                                       lazy tool proxy

Frames=0 means no animation timeline is reported. It does NOT mean that the
engine returned no frame, that a preceding action cost zero, or that a level was
solved. In particular, record=None supplies action=None, without guessing the
last action. Existing error text stays visible. RESET/fatal-action provenance
and the producer's record selection are not changed by this helper.

Evidence and cost
-----------------
18 workspace source-bound fixtures pass. They cover 256 synthetic binary 2x2
single-frame transitions, exact baseline/proposed missing-key behavior through
the real lazy proxy code, normal transient and large-change pass-through,
malformed/disabled paths, provenance and mutation isolation. Exact query/tool
function bodies replayed with action/normalization sentinels leave action_count
17 unchanged after 1,024 read queries. The real SDK action path separately calls
env.step and increments action bookkeeping once; this proposal does not invoke
that path and claims no reduction in the price of an executed action.

For a null action label, completing the empty result adds 36 compact JSON bytes.
That is pipe/output size, not a measured number of prompt tokens or a score gain.
Normal timeline dictionaries are returned by identity without a render change.
The fixture color palette and ASCII formatting are synthetic dependencies; no
production-renderer equivalence claim is made from the toy visual examples.

Portable runnable example
-------------------------
Requires Python >=3.10; independently tested with Python 3.12.14. Python 3.9 is
unsupported because the unchanged helper uses PEP604 annotation syntax.
Copy these seven files together, retaining both notice files:
empty_animation_schema.py, portable_replay_demo.py,
pinned_animation_reference.source.py, pinned_lazy_animation_reference.source.py,
portable_reference_functions.json, NOTICE.txt and
ORIGINAL_SOURCE_MIT_NOTICE_ADDENDUM.txt. Run:

    python3.12 -B portable_replay_demo.py

The demo uses relative paths and the Python standard library. It replays pinned
AST-selected function bodies against synthetic state only; it imports no game
SDK/model, opens no network connection and starts no subprocess. It reproduces
the missing-key failure, the completed result, zero-action repeated queries and
normal-timeline identity preservation. It is not a gameplay benchmark.

The deeper 18-test audit also needs the retained workspace source pins named in
PROVENANCE_INPUTS.json and ADDITIONAL_SOURCE_PINS.json. From Neurogolf:

    PYTHONDONTWRITEBYTECODE=1 .kaggle-venv/bin/python3 -B -m unittest discover -s research/codex_arc3_empty_animation_schema_proposal_20261020 -p test_empty_animation_schema.py -v

Credit and scoring limits
-------------------------
Daniel Franzen's Apache2.0 recipe and Tufa Labs' Duck harness are the baseline.
Root's 19 Oct 20:30 UTC native UI audit bound Jingshui V1/native357384371 to33.22
and Apache2.0. Its harness patch and serving CFG match our reviewed family;
its score is not evidence of a distinct new solver. Our own previously verified
row57016786/V17/native356491543 is30.65; these are unpaired observations.

The schema-completion idea is credited to Heliosli V5/native359864604, Apache2.0.
That inspected version's public score is29.88. Its notebook's best32.60 belongs
to different V1/native354517385, which was not inspected in this bounded pass.
SPEC_STEPS=3 already matches our baseline and is not a new optimization.

Our contribution here is an independently written narrow adapter, pinned-source
failure/semantics proof, mutation/action-budget fixtures and a portable replay.
It is a reliability experiment, not a novel model or a proven score improvement.

Next gate
---------
Keep the first authorized output-repair run unchanged. After its full-workload
qualification, a separate reviewed candidate may integrate this adapter around
the existing build_animation_view call using the very same record. Paired real
public-game evaluation must count model exceptions, queries, executed actions,
latency and score before any claimed gain. No such evaluation or integration
is performed or authorized by this packet.
