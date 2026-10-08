"""CPU tests of the M2 bench cell. Usage: python -I -B test_m2_bench.py <built m2_bench_cell.py> <V15 prompts dir>"""
import ast, hashlib, json, os, shutil, socket, subprocess, sys, tempfile, time
from pathlib import Path
CELL, PROMPTS = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
HERE = Path(__file__).resolve().parent
passed = []
def ok(name, cond, detail=''):
    if not cond: raise SystemExit('FAIL %s %s' % (name, detail))
    passed.append(name); print('PASS', name, detail)
src = CELL.read_text(); tree = ast.parse(src)
ok('first_statement_is_clock', isinstance(tree.body[0], ast.Assign) and tree.body[0].targets[0].id == '_m2_started')
ok('last_statement_is_guarded_main', isinstance(tree.body[-1], ast.Try))
ok('no_submit_or_push_calls', not any(w in src for w in ('competition_submit', 'kernels_push', 'kaggle competitions submit', 'SaveKernel')))
def load(out_dir):
    os.environ['M2_BENCH_OUT'] = str(out_dir)
    ns = {'__name__': '__main__'}
    exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), str(CELL), 'exec'), ns)
    return ns
tmp = Path(tempfile.mkdtemp(prefix='m2t_'))
ns = load(tmp / 'out0')
# recipe pins
for k, (d, code) in ns['M2_RECIPE'].items():
    ok('pin_' + k, hashlib.sha256(code.encode()).hexdigest() == d)
ok('cell9_subset_has_no_harness_patch', 'git", "apply' not in ns['M2_RECIPE']['v16_cell09_paths_and_env_without_harness_patch'][1] and "'LOCAL_ANALYZER_TEMPERATURE': '0.7'" in ns['M2_RECIPE']['v16_cell09_paths_and_env_without_harness_patch'][1])
ok('cell17_prefix_stops_before_launch', 'Popen' not in ns['M2_RECIPE']['v16_cell17_launcher_before_launch'][1] and 'args += ["--speculative-token-map", str(tok)]' in ns['M2_RECIPE']['v16_cell17_launcher_before_launch'][1])
ok('sampling_matches_v16_env', ns['M2_SAMPLING'] == dict(temperature=0.7, top_p=0.95, top_k=20) and ns['M2_MAX_TOKENS'] == 2048 and ns['M2_STREAMS'] == 10)
# parser on all ten V15 snapshots
files = sorted(PROMPTS.glob('*_p0.log')); ok('ten_snapshots', len(files) == 10, len(files))
sizes = []
for f in files:
    msgs, desc = ns['m2_parse_snapshot'](f.read_text())
    roles = [m['role'] for m in msgs]
    alt = all(a != b for a, b in zip(roles[1:], roles[2:]))
    ok('parse_' + f.name[:4], roles[0] == 'system' and roles[-1] == 'user' and alt and desc.startswith('Run one ephemeral Python snippet'), '%d msgs' % len(msgs))
    p = ns['m2_payload'](msgs, desc, 'flashnext'); b = json.dumps(p).encode(); sizes.append(len(b))
    ok('payload_' + f.name[:4], p['tools'][0]['function']['name'] == 'python' and p['temperature'] == 0.7 and p['top_k'] == 20, '%d B' % len(b))
for bad in ('', 'LATEST MODEL CALL SNAPSHOT\n[AVAILABLE TOOLS]\n- python: x\n', 'nonsense\n[MODEL INPUT]\n[SYSTEM]\nx\n[TURN TRANSCRIPT SO FAR]\n'):
    try:
        ns['m2_parse_snapshot'](bad); ok('parse_rejects_bad', False)
    except ValueError:
        passed.append('parse_rejects_bad')
print('payload bytes', sizes)
def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); return s.getsockname()[1]
# owned stop escalates to SIGKILL and kills the child in the group
port = free_port(); env = dict(os.environ, FAKE_IGNORE_TERM='1')
srv = ns['M2OwnedServer']([sys.executable, str(HERE / 'fake_sglang_server.py'), '--port', str(port)], env, tmp / 'stop.log')
pid = srv.start(); time.sleep(2.5)
ok('owned_after_start', srv.owned() and ns['m2_group_alive'](pid))
how = srv.stop(grace=2.0)
ok('stop_escalates_and_group_gone', 'kill' in how and not ns['m2_group_alive'](pid), how)
st = ns['m2_settle'](port, timeout=10); ok('settle_port_closed', st['settled'], st)
# end-to-end m2_main with a fake recipe, three streams, short windows
def e2e(out, whole_s, label):
    ns = load(out)
    port = free_port(); pdir = out.parent / (label + '_prompts'); (pdir / 'prompts').mkdir(parents=True)
    for f in files[:3]: shutil.copy(f, pdir / 'prompts' / f.name)
    fake = ('import os, sys\nSERVED_MODEL_PORT = %d\nSERVED_MODEL_NAME = "flashnext"\nMODEL_DIR = %r\nDRAFT_MODEL_DIR = %r\n'
            'env = dict(os.environ)\nargs = [sys.executable, %r, "--port", str(SERVED_MODEL_PORT), "--speculative-algorithm", "NEXTN", "--speculative-token-map", "/x/hot.pt"]\n'
            'def precache(*paths, times=1, delay=0, threads=16):\n    return None\n') % (port, str(out), str(out), str(HERE / 'fake_sglang_server.py'))
    ns['M2_RECIPE'] = {'fake': (hashlib.sha256(fake.encode()).hexdigest(), fake)}
    ns['m2_find_snapshots'].__defaults__ = ((str(pdir),), '/nonexistent')
    ns.update(M2_MIN_READY_CAP_S=2.0, M2_STREAMS=3, M2_WINDOW_MAX_S=6.0, M2_WINDOW_MIN_S=3.0, M2_GRACE_S=2.0, M2_TEARDOWN_S=8.0, M2_READY_CAP_S=20.0)
    ns['M2_DEADLINE'] = time.monotonic() + whole_s
    exec(compile(ast.Module(body=[tree.body[-1]], type_ignores=[]), str(CELL), 'exec'), ns)
    return ns, json.loads((out / 'receipt.json').read_text())
ns2, r = e2e(tmp / 'e2e', 120.0, 'a')
g = r['gate']
ok('e2e_two_arms', r['status'] == 'TWO_ARMS' and r['plan']['arms'] == 2 and r['plan']['window_s'] == 6.0, r.get('plan'))
ok('e2e_args_diff', r['args']['frspec_off_removed'] == ['--speculative-token-map', '/x/hot.pt'])
ok('e2e_gate_adopt_on_fake_11pct', g['decision'] == 'ADOPT_FRSPEC_OFF' and 0.15 < g['client_tps_gain'] < 0.6 and g['kv_pool_equal'] and g['errors'] == 0, g)
ok('e2e_server_log_parsed', r['arms']['control_v16']['server_log']['kv_pool_tokens'] == 1011264 and r['arms']['frspec_off']['server_log']['accept_len_all'] == 2.8, r['arms']['frspec_off']['server_log'])
ok('e2e_groups_stopped', all(not ns2['m2_group_alive'](r['arms'][a]['pid']) for a in ('control_v16', 'frspec_off')))
ok('e2e_order', [json.loads(l)['arm'] for l in (tmp / 'e2e' / 'events.jsonl').read_text().splitlines() if json.loads(l)['kind'] == 'arm_spawned'] == ['frspec_off', 'control_v16'])
# too little budget for two equal windows -> one arm only, no exception
ns3, r3 = e2e(tmp / 'e2e_one', 42.0, 'b')
ok('e2e_one_arm_when_short', r3['plan']['arms'] == 1 and r3['status'] == 'INCOMPLETE' and r3['gate']['decision'] == 'NO_DECISION' and 'skipped' in r3['arms']['control_v16'], r3.get('plan'))
ok('e2e_one_arm_group_stopped', not ns3['m2_group_alive'](r3['arms']['frspec_off']['pid']))
# watchdog unit: deadline passes while an owned server runs -> group stopped, receipt marked, main thread interrupted
ns4 = load(tmp / 'wd'); port = free_port()
srv = ns4['M2OwnedServer']([sys.executable, str(HERE / 'fake_sglang_server.py'), '--port', str(port)], dict(os.environ), tmp / 'wd.log')
pid = srv.start(); ns4['M2_CURRENT']['server'] = srv; ns4['M2_DEADLINE'] = time.monotonic() + 3.0
import threading
threading.Thread(target=ns4['m2_watchdog'], daemon=True).start()
interrupted = False
try:
    time.sleep(30)
except KeyboardInterrupt:
    interrupted = True
r4 = json.loads((tmp / 'wd' / 'receipt.json').read_text())
ok('watchdog_interrupts_and_stops', interrupted and r4['status'] == 'WATCHDOG_DEADLINE' and not ns4['m2_group_alive'](pid))
print('ALL PASS', len(passed))
