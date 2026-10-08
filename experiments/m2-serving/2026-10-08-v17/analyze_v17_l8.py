"""Zero-GPU L8 + behaviour analysis for public V15/V16/V17 commit runs (read-only on inputs; writes one JSON).
Usage: python -I analyze_v17_l8.py <v17 timing requests.jsonl> <v17 report json> <out.json> <label:summary.txt:serving_analysis.json>...
- Client side (V17 timing log): per-thread tool-gap idle, error records, requests in flight over the window.
- Server side (each run's serve.log analysis): time-weighted running requests, gen tok/s by running count, accept length, KV use.
- L8 worth: slot-time the tool gaps leave idle, converted to throughput with the measured gen-tok/s-vs-running curve,
  then to points with elasticity 0.25 (frontier sweep) on a 26-28 leaderboard base.
- Behaviour: summary.txt per-game scores, actions, tokens; paired per-game differences."""
import json, re, statistics as st, sys
from pathlib import Path
recs = [json.loads(l) for l in open(sys.argv[1])]; rep = json.loads(Path(sys.argv[2]).read_text()); out = Path(sys.argv[3])
runs = {}
for spec in sys.argv[4:]:
    label, summ, serv = spec.split(':'); runs[label] = {'summary': Path(summ).read_text(), 'serving': json.loads(Path(serv).read_text())}
done = sorted((r for r in recs if 't1' in r), key=lambda r: r['t0'])
errs = [r for r in done if 'error' in r]; t_end = max(r['t1'] for r in done); t_start = min(r['t0'] for r in done)
err_info = [{'thread': r['thread'], 'error': r['error'], 'seconds_before_window_end': round(t_end - r['t1'], 1), 'duration_s': round(r['t1'] - r['t0'], 1)} for r in errs]
per = {}
for r in done: per.setdefault(r['thread'], []).append(r)
gaps = sorted(max(0.0, b['t0'] - a['t1']) for rs in per.values() for a, b in zip(rs, rs[1:]))
lat = sorted(r['t1'] - r['t0'] for r in done if 'error' not in r)
q = lambda xs, f: round(xs[min(len(xs) - 1, int(f * len(xs)))], 2)
client = {'records': len(recs), 'threads': len(per), 'window_s': round(t_end - t_start, 1), 'error_records': err_info,
          'request_latency_s': {'p10': q(lat, .1), 'p50': q(lat, .5), 'p90': q(lat, .9), 'max': round(lat[-1], 1)},
          'tool_gap_s': {'n': len(gaps), 'sum': round(sum(gaps), 1), 'p50': q(gaps, .5), 'p90': q(gaps, .9), 'p99': q(gaps, .99), 'max': round(gaps[-1], 1)},
          'report_timing': {k: v for k, v in rep['timing'].items() if k != 'per_thread'}}
mean_in_flight = rep['timing']['mean_in_flight']; slots = rep['timing']['slots']
# server-side curve pooled over runs: gen tok/s by running count (decode-line means weighted by line counts)
pool = {}
for label, r in runs.items():
    for k, v in r['serving']['by_running_req'].items():
        n, m = v['gen_tps']['n'], v['gen_tps']['mean']; pool.setdefault(int(k), []).append((n, m))
curve = {k: round(sum(n * m for n, m in v) / sum(n for n, _ in v), 1) for k, v in sorted(pool.items())}
def tps(x):  # linear interpolation on the pooled curve
    ks = sorted(curve); lo = max(k for k in ks if k <= x); hi = min(k for k in ks if k >= x)
    return curve[lo] if lo == hi else curve[lo] + (curve[hi] - curve[lo]) * (x - lo) / (hi - lo)
v17_running = runs['V17']['serving']['occupancy']['time_weighted_mean_running']
window = t_end - t_start
idle_slots = slots - mean_in_flight                         # client view: slots with no request in flight
tool_gap_slots = sum(gaps) / window                         # ... of which: a stream between two of its requests (tool execution, game step)
edge_slots = idle_slots - tool_gap_slots                    # ... and: before a stream's first / after its last request (a finished game)
queued_slots = mean_in_flight - v17_running                 # in flight at the client but not in the running batch (queue / prefill)
filled = min(slots, v17_running + tool_gap_slots)           # L8 = admit beyond the slots so tool gaps are covered
gain_curve = tps(filled) / tps(v17_running) - 1
gain_linear = filled / v17_running - 1
E, base = 0.25, (26.0, 28.0)
l8 = {'slots': slots, 'client_mean_in_flight': mean_in_flight, 'server_time_weighted_running_v17': v17_running,
      'client_idle_slots': round(idle_slots, 3), 'client_idle_share': round(idle_slots / slots, 4),
      'tool_gap_idle_slots': round(tool_gap_slots, 3), 'tool_gap_idle_share': round(tool_gap_slots / slots, 4),
      'edge_idle_slots_first_last_request': round(edge_slots, 3), 'edge_note': 'mostly harness-game_8, whose game ended about 370 s before the window; in the rerun a queued game takes that slot',
      'queued_or_prefill_slots': round(queued_slots, 3), 'pooled_gen_tps_by_running': curve,
      'throughput_gain_if_tool_gaps_filled': {'measured_curve': round(gain_curve, 4), 'linear_upper_bound': round(gain_linear, 4)},
      'points_at_elasticity_0.25': {'measured_curve': [round(E * gain_curve * b, 2) for b in base], 'linear_upper_bound': [round(E * gain_linear * b, 2) for b in base]},
      'kv_usage_max': {k: r['serving']['full_token_usage']['max'] for k, r in runs.items()}}
def parse_summary(t):
    g = {m.group(1): dict(score=float(m.group(2)), levels=float(m.group(3)), max_levels=int(m.group(4)), actions=int(m.group(5)), tokens=int(m.group(6)))
         for m in re.finditer(r'^\s+(\S+): score=([0-9.]+), levels=([0-9.]+)/(\d+), actions=(\d+), tokens=(\d+)', t, re.M)}
    f = lambda k: float(re.search(k + r':\s+([0-9.]+)', t).group(1))
    return dict(mean=f('mean score'), median=f('median score'), total_actions=int(f('total actions')), total_tokens=int(f('total tokens')),
                gen_tps_job=f(r'generated tokens/sec'), won=int(re.search(r'won: (\d+)', t).group(1)), duration=re.search(r'duration:\s+(.+)', t).group(1).strip(), games=g)
beh = {k: parse_summary(r['summary']) for k, r in runs.items()}
games = sorted(set.intersection(*[set(b['games']) for b in beh.values()]))
table = {k: {'mean_score': b['mean'], 'median': b['median'], 'won': b['won'], 'duration': b['duration'], 'actions_per_game': round(b['total_actions'] / len(b['games']), 1),
             'tokens_per_game': round(b['total_tokens'] / len(b['games'])), 'tokens_per_game_sd': round(st.pstdev([g['tokens'] for g in b['games'].values()])),
             'levels_total': sum(g['levels'] for g in b['games'].values()), 'gen_tps_job': b['gen_tps_job'],
             'server_accept_len': runs[k]['serving']['accept_len_all']['mean'], 'server_gen_tps': runs[k]['serving']['gen_tps_all']['mean'],
             'server_boot_first_200_s': runs[k]['serving']['boot_seconds_from_first_log']['first_http_200'][0]} for k, b in beh.items()}
pairs = {}
for a, b in (('V15', 'V16'), ('V15', 'V17'), ('V16', 'V17')):
    d = [beh[b]['games'][g]['score'] - beh[a]['games'][g]['score'] for g in games]
    pairs['%s->%s' % (a, b)] = {'mean_diff': round(st.mean(d), 2), 'sd_diff': round(st.stdev(d), 2), 'se': round(st.stdev(d) / len(d) ** .5, 2), 'n_up': sum(x > 0 for x in d), 'n_down': sum(x < 0 for x in d)}
per_game_sd = {g: round(st.pstdev([beh[k]['games'][g]['score'] for k in beh]), 1) for g in games}
res = {'client_v17': client, 'l8': l8, 'behaviour': {'runs': table, 'paired_per_game_score': pairs, 'per_game_score_sd_across_runs': per_game_sd,
       'per_game': {g: {k: beh[k]['games'][g] for k in beh} for g in games}}}
out.write_text(json.dumps(res, indent=1)); print(json.dumps({'client': {k: v for k, v in client.items() if k != 'report_timing'}, 'l8': l8, 'runs': table, 'pairs': pairs}, indent=1))
