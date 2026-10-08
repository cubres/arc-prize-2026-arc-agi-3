"""Zero-GPU analysis of an M2 (Pennyroyal SGLang) serve.log plus benchmark.json from a commit run.

Usage: python -I analyze_m2_serving_log.py <output_dir_with_serve.log> <out.json>
Reports: boot timeline, speculative acceptance (accept len / rate) overall and by #running-req,
decode throughput, and slot occupancy over the play window (time-weighted #running-req, idle gaps).
Read-only on its inputs; writes one JSON.
"""
import json, re, statistics as st, sys
from datetime import datetime
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
TS = re.compile(r'^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (.*)$')
lines = open(src / 'serve.log', errors='replace').read().splitlines()
ev = []
for l in lines:
    m = TS.match(l)
    if m:
        ev.append((datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S'), m.group(2)))
t0 = ev[0][0]
rel = lambda t: (t - t0).total_seconds()
def first(pat):
    for t, s in ev:
        if re.search(pat, s): return rel(t), s[:160]
    return None, None
boot = {k: first(p) for k, p in [('load_weight_begin', r'Load weight begin'), ('load_weight_end', r'Load weight end'),
        ('kv_allocated', r'KV Cache is allocated'), ('first_prefill', r'^Prefill batch'), ('first_http_200', r'POST /v1/chat/completions HTTP/1.1" 200')]}
num = lambda key, s: (lambda m: float(m.group(1)) if m else None)(re.search(re.escape(key) + r':\s*([0-9.]+)', s))
dec, pre = [], []
for t, s in ev:
    if s.startswith('Decode batch'):
        dec.append(dict(t=rel(t), run=num('#running-req', s), acc_len=num('accept len', s), acc_rate=num('accept rate', s),
                        gen_tps=num('gen throughput (token/s)', s), queue=num('#queue-req', s), full_usage=num('full token usage', s), mamba_usage=num('mamba usage', s)))
    elif s.startswith('Prefill batch'):
        pre.append(dict(t=rel(t), run=num('#running-req', s), new_tok=num('#new-token', s), cached=num('#cached-token', s), queue=num('#queue-req', s)))
def summ(xs):
    xs = [x for x in xs if x is not None]
    if not xs: return None
    q = st.quantiles(xs, n=10) if len(xs) >= 10 else None
    return dict(n=len(xs), mean=round(st.mean(xs), 4), median=round(st.median(xs), 4), p10=round(q[0], 4) if q else None, p90=round(q[-1], 4) if q else None, min=min(xs), max=max(xs))
by_run = {}
for d in dec:
    by_run.setdefault(int(d['run']), []).append(d)
acc_by_run = {k: dict(acc_len=summ([d['acc_len'] for d in v]), gen_tps=summ([d['gen_tps'] for d in v])) for k, v in sorted(by_run.items())}
# Occupancy over the play window: piecewise-constant #running-req between consecutive scheduler log lines;
# gaps longer than GAP_S with no scheduler line are counted as idle (0 running).
GAP_S = 15.0
sched = sorted([(d['t'], d['run']) for d in dec] + [(p['t'], p['run']) for p in pre])
w0, w1 = sched[0][0], sched[-1][0]
area = idle = 0.0
gaps = []
for (ta, ra), (tb, rb) in zip(sched, sched[1:]):
    dt = tb - ta
    if dt > GAP_S:
        gaps.append(round(dt, 1)); idle += dt
    else:
        area += ra * dt
window = w1 - w0
bm = json.loads((src / 'benchmark.json').read_text()) if (src / 'benchmark.json').exists() else None
games = []
if bm:
    for g in bm['game_runs']:
        h = g['history']
        games.append(dict(game=g['game_id'], state=g['state'], levels=g['levels_completed'], score=round(g['final_score'], 2), actions=len(h),
                          gen_tokens=sum(x.get('generated_tokens', 0) for x in h), action_wall_s=round(sum(x.get('wallclock_seconds', 0) for x in h), 1),
                          final_wall_s=round(g['final_wallclock_seconds'], 1)))
res = dict(source=str(src), serve_log_lines=len(lines), t0=str(t0), boot_seconds_from_first_log=boot,
           decode_lines=len(dec), prefill_lines=len(pre),
           accept_len_all=summ([d['acc_len'] for d in dec]), accept_rate_all=summ([d['acc_rate'] for d in dec]),
           gen_tps_all=summ([d['gen_tps'] for d in dec]), by_running_req=acc_by_run,
           full_token_usage=summ([d['full_usage'] for d in dec]), queue_req=summ([d['queue'] for d in dec]),
           occupancy=dict(window_s=round(window, 1), gap_threshold_s=GAP_S, idle_gap_s=round(idle, 1), n_gaps=len(gaps), longest_gaps=sorted(gaps)[-5:],
                          time_weighted_mean_running=round(area / window, 3) if window else None, max_streams=10,
                          slot_idle_fraction=round(1 - (area / window) / 10, 3) if window else None),
           games=games)
out.write_text(json.dumps(res, indent=1))
print(json.dumps({k: res[k] for k in ('boot_seconds_from_first_log', 'decode_lines', 'accept_len_all', 'accept_rate_all', 'gen_tps_all', 'occupancy')}, indent=1))
for k, v in acc_by_run.items(): print('running', k, 'n', v['acc_len']['n'], 'acc_len mean', v['acc_len']['mean'], 'gen_tps mean', v['gen_tps']['mean'])
