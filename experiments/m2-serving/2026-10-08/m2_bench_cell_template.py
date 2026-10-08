# ARC3 private bench (worker V14-M2): serving-only check of speculative decoding with and without the FR-Spec hot-token map,
# on the exact public V16 serving stack (Pennyroyal SGLang 2.5.3, Intel Qwen3.8-Flash-Next W4A16 + albucino MTP drafter, NEXTN 3 steps).
# Owned clock from this first statement; owned server process group; nothing here can submit.
_m2_started = __import__('time').monotonic()
import _thread, hashlib, json, os, re, signal, socket, subprocess, sys, threading, time, urllib.request
from pathlib import Path

M2_SESSION_TIMEOUT_S = 2700            # the push timeout; Kaggle ends the session here
M2_WHOLE_S = 2580.0                    # owned budget from the first statement (120 s reserve before the session timeout)
M2_DEADLINE = _m2_started + M2_WHOLE_S
M2_ARM_ORDER = ('frspec_off', 'control_v16')   # new information first; the control is the exact V16 argument list
M2_WINDOW_MAX_S, M2_WINDOW_MIN_S = 300.0, 150.0  # equal replay windows for both arms, fixed after the first boot
M2_TEARDOWN_S = 60.0                   # owned stop + port/GPU settle, per arm
M2_GRACE_S = 60.0                      # in-flight requests may finish after the window closes (2048 tokens at ~70 tok/s per stream ~ 30 s)
M2_READY_CAP_S = 1200.0                # one boot (V15 measured 767 s from the first server log line to the first 200)
M2_MIN_READY_CAP_S = 300.0             # do not start a boot that cannot plausibly finish
M2_STREAMS = 10                        # = MAXREQ = CUDAGRAPH_MAXBS = ARC3_MAX_ACTIVE_STREAMS in V16
M2_MAX_TOKENS = 2048                   # = LOCAL_ANALYZER_YIELD_TOKENS in V16
M2_SAMPLING = dict(temperature=0.7, top_p=0.95, top_k=20)  # = LOCAL_ANALYZER_TEMPERATURE / TOP_P / TOP_K in V16
M2_GATE = dict(min_tps_gain=0.10, max_errors=0, kv_pool_equal=True)  # pre-registered (frontier sweep M-B)
if os.environ.get('KAGGLE_IS_COMPETITION_RERUN', '').strip().lower() in ('1', 'true'):
    raise RuntimeError('A diagnostic bench cannot run as a competition submission')
M2_OUT = Path(os.environ.get('M2_BENCH_OUT', '/kaggle/working/m2_bench'))
M2_OUT.mkdir(parents=True, exist_ok=False)
RECEIPT = dict(schema='arc3-m2-bench-v1', worker='prvsiyan/zz-gpuchk-899422', status='STARTED', arms={},
               question='On replayed V15 game contexts at 10 streams, does dropping the FR-Spec hot-token map change accepted tokens per step and decode tok/s?',
               budgets=dict(session_timeout_s=M2_SESSION_TIMEOUT_S, whole_s=M2_WHOLE_S, window_max_s=M2_WINDOW_MAX_S, window_min_s=M2_WINDOW_MIN_S,
                            teardown_s=M2_TEARDOWN_S, ready_cap_s=M2_READY_CAP_S), gate=M2_GATE, arm_order=list(M2_ARM_ORDER),
               sampling=dict(M2_SAMPLING, max_tokens=M2_MAX_TOKENS, streams=M2_STREAMS))

def m2_left():
    return M2_DEADLINE - time.monotonic()

def m2_event(kind, **kw):
    rec = dict(t=round(time.monotonic() - _m2_started, 1), kind=kind, **kw)
    with (M2_OUT / 'events.jsonl').open('a') as f:
        f.write(json.dumps(rec, default=str) + '\n')
    print('[m2]', json.dumps(rec, default=str)[:600], flush=True)

def m2_write_receipt():
    (M2_OUT / 'receipt.json').write_text(json.dumps(RECEIPT, indent=1, default=str))

# ---------- replay workload: the V15 commit's per-game latest-model-call snapshots ----------
M2_SNAPSHOT_ROOTS = ('/kaggle/input/arc-agi-3-stock-taaf-action7-shadow', '/kaggle/input/notebooks/prvsiyan/arc-agi-3-stock-taaf-action7-shadow')
_M2_ROLE = re.compile(r'^\[(SYSTEM|USER|ASSISTANT|REASONING)\]$')
M2_CONTINUE = 'The python tool output for your last call was not recorded in this replay. Continue the turn.'

def m2_find_snapshots(roots=M2_SNAPSHOT_ROOTS, base='/kaggle/input'):
    for r in roots:
        files = sorted(Path(r, 'prompts').glob('*_p0.log'))
        if files:
            return Path(r), files
    for pattern in ('*/prompts/*_p0.log', '*/*/*/prompts/*_p0.log'):
        found = sorted(Path(base).glob(pattern))
        if found:
            d = found[0].parent
            return d.parent, [p for p in found if p.parent == d]
    raise RuntimeError('Replay snapshots (public notebook output prompts/*_p0.log) are not mounted')

def m2_parse_snapshot(text):
    """Snapshot -> (messages, python tool description). Tool round trips are elided in the snapshot, so consecutive
    assistant blocks are merged (content + reasoning_content), as are consecutive user blocks."""
    head, sep, rest = text.partition('\n[MODEL INPUT]\n')
    if not sep or not head.startswith('LATEST MODEL CALL SNAPSHOT'):
        raise ValueError('not a model-call snapshot')
    body, sep2, _ = rest.partition('\n[TURN TRANSCRIPT SO FAR]\n')
    if not sep2:
        raise ValueError('snapshot has no turn transcript marker')
    desc = next((l[len('- python: '):] for l in head.split('\n') if l.startswith('- python: ')), None)
    if not desc:
        raise ValueError('snapshot has no python tool description')
    blocks, cur = [], None
    for line in body.split('\n'):
        m = _M2_ROLE.match(line)
        if m:
            cur = [m.group(1), []]
            blocks.append(cur)
        elif cur is not None:
            cur[1].append(line)
        elif line.strip():
            raise ValueError('text before the first role marker')
    msgs, i = [], 0
    while i < len(blocks):
        role, lines = blocks[i]
        txt = '\n'.join(lines).strip('\n')
        if role == 'SYSTEM':
            if msgs:
                raise ValueError('system block not first')
            msgs.append({'role': 'system', 'content': txt})
        elif role == 'USER':
            if msgs and msgs[-1]['role'] == 'user':
                msgs[-1]['content'] = msgs[-1]['content'] + '\n\n' + txt
            else:
                msgs.append({'role': 'user', 'content': txt})
        elif role == 'ASSISTANT':
            reasoning = ''
            if i + 1 < len(blocks) and blocks[i + 1][0] == 'REASONING':
                reasoning = '\n'.join(blocks[i + 1][1]).strip('\n')
                i += 1
            if msgs and msgs[-1]['role'] == 'assistant':
                msgs[-1]['content'] = (msgs[-1]['content'] + '\n\n' + txt).strip('\n')
                msgs[-1]['reasoning_content'] = (msgs[-1]['reasoning_content'] + '\n\n' + reasoning).strip('\n')
            else:
                msgs.append({'role': 'assistant', 'content': txt, 'reasoning_content': reasoning})
        else:
            raise ValueError('reasoning block without an assistant block')
        i += 1
    if msgs and msgs[-1]['role'] == 'assistant':
        # mid-turn snapshot (request_index_within_turn > 1): the elided tool result is replaced by a short user note
        msgs.append({'role': 'user', 'content': M2_CONTINUE})
    if not msgs or msgs[0]['role'] != 'system' or msgs[-1]['role'] != 'user' or len(msgs) < 3:
        raise ValueError('unexpected message layout')
    return msgs, desc

def m2_payload(msgs, desc, served_name):
    tool = {'type': 'function', 'function': {'name': 'python', 'description': desc, 'parameters': {
        'type': 'object', 'properties': {'code': {'type': 'string', 'description': 'Python snippet to run against the game state.'}}, 'required': ['code']}}}
    return dict(model=served_name, messages=msgs, tools=[tool], tool_choice='auto', max_tokens=M2_MAX_TOKENS, stream=False,
                chat_template_kwargs={'enable_thinking': True, 'preserve_thinking': True}, **M2_SAMPLING)

# ---------- owned server process group ----------
class M2OwnedServer:
    def __init__(self, args, env, log_path):
        self.args, self.env, self.log_path, self.proc, self.pid = list(args), dict(env), Path(log_path), None, None
    def start(self):
        with open(self.log_path, 'ab', buffering=0) as logf:
            self.proc = subprocess.Popen(self.args, env=self.env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
        self.pid = self.proc.pid
        if not self.owned():
            raise RuntimeError('server process group is not owned by this cell')
        return self.pid
    def owned(self):
        """Leader not yet reaped by us (returncode None), and it leads its own process group and session."""
        if self.proc is None or self.proc.returncode is not None:
            return False
        try:
            return os.getpgid(self.pid) == self.pid and os.getsid(self.pid) == self.pid
        except ProcessLookupError:
            return False
    def alive(self):
        return self.proc is not None and self.proc.poll() is None
    def stop(self, grace=20.0):
        """SIGTERM the owned group, then SIGKILL; reap the leader last so its pid stays reserved while the group is signalled."""
        if self.proc is None:
            return 'never_started'
        steps = []
        # The group id is our leader's pid; Linux does not reuse a pid while it still names a live process group,
        # so a group whose leader already exited (and was reaped by poll) is still ours to signal.
        if self.owned() or m2_group_alive(self.pid):
            try:
                os.killpg(self.pid, signal.SIGTERM); steps.append('term')
            except ProcessLookupError:
                steps.append('term_gone')
            t = time.monotonic()
            while time.monotonic() - t < grace and m2_group_alive(self.pid):
                time.sleep(0.5)
            if m2_group_alive(self.pid):
                try:
                    os.killpg(self.pid, signal.SIGKILL); steps.append('kill')
                except ProcessLookupError:
                    steps.append('kill_gone')
        try:
            self.proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            steps.append('leader_not_reaped')
        return '+'.join(steps) or 'already_exited'

def m2_group_alive(pgid):
    """True while any process other than a zombie leader remains in the group."""
    try:
        for d in os.listdir('/proc'):
            if d.isdigit():
                try:
                    stat = Path('/proc', d, 'stat').read_text()
                    fields = stat[stat.rindex(')') + 2:].split()
                    if int(fields[2]) == pgid and fields[0] != 'Z':
                        return True
                except (OSError, ValueError, IndexError):
                    pass
        return False
    except FileNotFoundError:   # no /proc (local CPU tests on macOS): fall back to signal 0
        try:
            os.killpg(pgid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

def m2_settle(port, timeout=45.0):
    """Port closed and two consecutive empty nvidia-smi compute-app samples (when nvidia-smi exists)."""
    t, empty, smi = time.monotonic(), 0, None
    while time.monotonic() - t < timeout:
        with socket.socket() as s:
            s.settimeout(1)
            port_open = s.connect_ex(('127.0.0.1', int(port))) == 0
        try:
            out = subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], capture_output=True, text=True, timeout=10)
            smi = out.stdout.strip()
            gpu_empty = out.returncode == 0 and not smi
        except FileNotFoundError:
            smi, gpu_empty = 'nvidia-smi unavailable', True
        empty = empty + 1 if (gpu_empty and not port_open) else 0
        if empty >= 2:
            return dict(settled=True, s=round(time.monotonic() - t, 1), smi=smi)
        time.sleep(2)
    return dict(settled=False, s=round(time.monotonic() - t, 1), smi=smi)

M2_CURRENT = {'server': None}

def m2_watchdog():
    while not M2_CURRENT.get('done'):
        if m2_left() <= 0:
            srv = M2_CURRENT.get('server')
            how = srv.stop(grace=10.0) if srv is not None else 'no_server'
            m2_event('watchdog_deadline', stop=how)
            RECEIPT['status'] = 'WATCHDOG_DEADLINE'
            m2_write_receipt()
            _thread.interrupt_main()
            return
        time.sleep(1.0)

# ---------- one arm: boot, replay, measure, owned stop ----------
_M2_TS = re.compile(r'^\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (.*)$')

def m2_num(key, s):
    m = re.search(re.escape(key) + r':\s*([0-9.]+)', s)
    return float(m.group(1)) if m else None

def m2_mean(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs), 4) if xs else None

def m2_log_stats(log_path, after_wall=None):
    dec, kv, load_s = [], None, None
    for line in Path(log_path).read_text(errors='replace').splitlines():
        m = _M2_TS.match(line)
        if not m:
            continue
        s = m.group(2)
        if s.startswith('KV Cache is allocated'):
            kv = m2_num('#tokens', s)
        elif s.startswith('Load weight end'):
            m3 = re.search(r'elapsed=([0-9.]+)', s)
            load_s = float(m3.group(1)) if m3 else None
        elif s.startswith('Decode batch'):
            if after_wall is not None and time.mktime(time.strptime(m.group(1), '%Y-%m-%d %H:%M:%S')) < after_wall:
                continue
            dec.append((m2_num('#running-req', s), m2_num('accept len', s), m2_num('accept rate', s), m2_num('gen throughput (token/s)', s)))
    full = [d for d in dec if d[0] == M2_STREAMS]
    return dict(decode_lines=len(dec), decode_lines_full=len(full), kv_pool_tokens=kv, weight_load_s=load_s,
                accept_len_all=m2_mean([d[1] for d in dec]), accept_len_full=m2_mean([d[1] for d in full]),
                accept_rate_full=m2_mean([d[2] for d in full]), gen_tps_full=m2_mean([d[3] for d in full]))

def m2_replay(url, payloads, window_s, hard_s, sink_path):
    """One thread per stream; each re-sends its own snapshot until the window closes. Returns per-request records."""
    t_start = time.monotonic()
    window_end, hard_end = t_start + window_s, t_start + hard_s
    recs, lock = [], threading.Lock()
    def stream(idx, body):
        k = 0
        while time.monotonic() < window_end:
            t = time.monotonic()
            rec = dict(stream=idx, k=k, t_send=round(t - t_start, 3))
            try:
                req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=max(5.0, hard_end - time.monotonic())) as r:
                    resp = json.loads(r.read())
                u = resp.get('usage') or {}
                rec.update(ok=True, completion_tokens=u.get('completion_tokens'), prompt_tokens=u.get('prompt_tokens'),
                           cached_tokens=(u.get('prompt_tokens_details') or {}).get('cached_tokens'),
                           finish=(resp.get('choices') or [{}])[0].get('finish_reason'))
            except Exception as e:
                rec.update(ok=False, error=(type(e).__name__ + ': ' + str(e))[:240])
                time.sleep(2)
            rec['t_done'] = round(time.monotonic() - t_start, 3)
            with lock:
                recs.append(rec)
                with open(sink_path, 'a') as f:
                    f.write(json.dumps(rec) + '\n')
            k += 1
    threads = [threading.Thread(target=stream, args=(i, b), daemon=True) for i, b in enumerate(payloads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join(timeout=max(0.0, hard_end - time.monotonic()) + 1)
    first_round = [r['t_done'] for r in recs if r['k'] == 0]
    warm = max(first_round) if len(first_round) == len(payloads) else None
    steady = [r for r in recs if warm is not None and r['ok'] and r['t_send'] >= warm]
    span = (max(r['t_done'] for r in steady) - warm) if steady else None
    toks = sum(r['completion_tokens'] or 0 for r in steady)
    return dict(requests=len(recs), ok=sum(r['ok'] for r in recs), errors=sum(not r['ok'] for r in recs), warmup_s=warm,
                steady_requests=len(steady), steady_completion_tokens=toks, steady_span_s=round(span, 2) if span else None,
                client_tps_steady=round(toks / span, 2) if span else None,
                all_completion_tokens=sum(r.get('completion_tokens') or 0 for r in recs if r['ok']),
                stragglers=sum(th.is_alive() for th in threads))

def m2_run_arm(name, args, env, port, payloads, choose_window, ready_cap_s, before_start=None):
    """choose_window(boot_s) -> replay seconds, called once the server is healthy (0 skips the replay)."""
    log_path = M2_OUT / ('serve_%s.log' % name)
    arm = dict(name=name, ready_cap_s=round(ready_cap_s, 1))
    RECEIPT['arms'][name] = arm
    srv = M2OwnedServer(args, env, log_path)
    if before_start:
        before_start()
    t0 = time.monotonic()
    arm['pid'] = srv.start(); M2_CURRENT['server'] = srv
    m2_event('arm_spawned', arm=name, pid=srv.pid)
    health = 'http://127.0.0.1:%d/health' % int(port)
    ready = False
    while time.monotonic() - t0 < ready_cap_s:
        if not srv.alive():
            break
        try:
            with urllib.request.urlopen(health, timeout=5) as r:
                if r.status == 200:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(3)
    arm['boot_s'] = round(time.monotonic() - t0, 1)
    arm['ready'] = ready
    m2_event('arm_ready' if ready else 'arm_not_ready', arm=name, boot_s=arm['boot_s'], alive=srv.alive())
    arm['window_s'] = window_s = choose_window(arm['boot_s']) if ready else 0.0
    if ready and window_s > 0:
        wall0 = time.time()
        arm['replay'] = m2_replay('http://127.0.0.1:%d/v1/chat/completions' % int(port), payloads, window_s, window_s + M2_GRACE_S,
                                  M2_OUT / ('requests_%s.jsonl' % name))
        arm['server_log'] = m2_log_stats(log_path, after_wall=wall0 - 1)
        m2_event('arm_measured', arm=name, replay=arm['replay'], server_log=arm['server_log'])
    arm['stop'] = srv.stop(); M2_CURRENT['server'] = None
    arm['settle'] = m2_settle(port)
    arm['server_log_boot'] = m2_log_stats(log_path)
    m2_event('arm_stopped', arm=name, stop=arm['stop'], settle=arm['settle'])
    m2_write_receipt()
    return arm

def m2_gate(arms):
    c, x = arms.get('control_v16') or {}, arms.get('frspec_off') or {}
    rc, rx = c.get('replay') or {}, x.get('replay') or {}
    if not (rc.get('client_tps_steady') and rx.get('client_tps_steady')):
        return dict(decision='NO_DECISION', reason='an arm has no steady replay measurement')
    gain = rx['client_tps_steady'] / rc['client_tps_steady'] - 1
    kv_eq = (c.get('server_log') or {}).get('kv_pool_tokens') == (x.get('server_log') or {}).get('kv_pool_tokens')
    errors = rc.get('errors', 1) + rx.get('errors', 1)
    adopt = gain >= M2_GATE['min_tps_gain'] and errors <= M2_GATE['max_errors'] and kv_eq
    return dict(decision='ADOPT_FRSPEC_OFF' if adopt else 'KEEP_V16_STACK', client_tps_gain=round(gain, 4), errors=errors, kv_pool_equal=kv_eq,
                accept_len_full=dict(control=(c.get('server_log') or {}).get('accept_len_full'), frspec_off=(x.get('server_log') or {}).get('accept_len_full')),
                gen_tps_full=dict(control=(c.get('server_log') or {}).get('gen_tps_full'), frspec_off=(x.get('server_log') or {}).get('gen_tps_full')))

# ---------- the exact V16 recipe code (verbatim, sha256-pinned; cell 9 minus its harness-bundle copy and patch lines) ----------
M2_V16_SOURCE_SHA256 = __V16_SOURCE_SHA__
M2_RECIPE = {
    'v16_cell08_input_resolver': (__CELL08_SHA__, __CELL08__),
    'v16_cell09_paths_and_env_without_harness_patch': (__CELL09D_SHA__, __CELL09D__),
    'v16_cell11_precache': (__CELL11_SHA__, __CELL11__),
    'v16_cell17_launcher_before_launch': (__CELL17P_SHA__, __CELL17P__),
}
M2_RECIPE_DERIVATION = __DERIVATION__

def m2_main():
    threading.Thread(target=m2_watchdog, daemon=True).start()
    root, files = m2_find_snapshots()
    files = files[:M2_STREAMS]
    if len(files) < M2_STREAMS:
        raise RuntimeError('fewer than %d replay snapshots' % M2_STREAMS)
    snaps = []
    for p in files:
        raw = p.read_bytes()
        msgs, desc = m2_parse_snapshot(raw.decode('utf-8'))
        snaps.append(dict(file=p.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), messages=len(msgs), continued=msgs[-1]['content'] == M2_CONTINUE, chars=sum(len(m['content']) + len(m.get('reasoning_content', '')) for m in msgs), _msgs=msgs, _desc=desc))
    RECEIPT['replay_source'] = dict(root=str(root), snapshots=[{k: v for k, v in s.items() if not k.startswith('_')} for s in snaps])
    m2_event('snapshots', root=str(root), n=len(snaps), chars=[s['chars'] for s in snaps])
    for key, (digest, code) in M2_RECIPE.items():
        if hashlib.sha256(code.encode()).hexdigest() != digest:
            raise RuntimeError('recipe code drift: ' + key)
    g = globals()
    for key, (digest, code) in M2_RECIPE.items():
        m2_event('recipe_exec', part=key, left_s=round(m2_left(), 1))
        exec(compile(code, '<%s>' % key, 'exec'), g)
    control_args = [str(a) for a in g['args']]
    if control_args.count('--speculative-token-map') != 1 or control_args.count('--speculative-algorithm') != 1:
        raise RuntimeError('V16 argument list is not the speculative + FR-Spec stack')
    i = control_args.index('--speculative-token-map')
    arm_args = {'control_v16': control_args, 'frspec_off': control_args[:i] + control_args[i + 2:]}
    RECEIPT['args'] = dict(control_v16=control_args, frspec_off_removed=control_args[i:i + 2])
    env, port, served = g['env'], int(g['SERVED_MODEL_PORT']), g['SERVED_MODEL_NAME']
    payloads = [json.dumps(m2_payload(s['_msgs'], s['_desc'], served)).encode() for s in snaps]
    RECEIPT['payload_bytes'] = [len(b) for b in payloads]
    precache, model_dirs = g['precache'], (g['MODEL_DIR'], g['DRAFT_MODEL_DIR'])
    def start_precache():   # V16 starts this model precache thread right before its server launch
        threading.Thread(target=precache, args=model_dirs, kwargs={'delay': 60, 'threads': 3}, daemon=True).start()
    plan = {}
    def choose_first(boot_s):
        per_arm_fixed = M2_GRACE_S + M2_TEARDOWN_S
        two = (m2_left() - 2 * per_arm_fixed - boot_s - 20) / 2
        if two >= M2_WINDOW_MIN_S:
            plan.update(arms=2, window_s=min(M2_WINDOW_MAX_S, two))
        else:
            plan.update(arms=1, window_s=max(0.0, min(M2_WINDOW_MAX_S, m2_left() - per_arm_fixed - 20)))
        RECEIPT['plan'] = dict(plan, first_boot_s=boot_s)
        m2_event('plan', **RECEIPT['plan'])
        return plan['window_s']
    first, second = M2_ARM_ORDER
    cap1 = min(M2_READY_CAP_S, m2_left() - M2_WINDOW_MIN_S - M2_GRACE_S - M2_TEARDOWN_S - 20)
    if cap1 < M2_MIN_READY_CAP_S:
        raise RuntimeError('budget exhausted during setup')
    m2_run_arm(first, arm_args[first], env, port, payloads, choose_first, cap1, start_precache)
    if plan.get('arms') == 2:
        cap2 = min(M2_READY_CAP_S, m2_left() - plan['window_s'] - M2_GRACE_S - M2_TEARDOWN_S - 20)
        if cap2 >= M2_MIN_READY_CAP_S:
            m2_run_arm(second, arm_args[second], env, port, payloads, lambda boot_s: plan['window_s'], cap2, start_precache)
        else:
            RECEIPT['arms'][second] = dict(name=second, skipped='budget after the first arm')
    else:
        RECEIPT['arms'][second] = dict(name=second, skipped='first boot too slow for two equal windows')
    RECEIPT['gate'] = m2_gate(RECEIPT['arms'])
    RECEIPT['status'] = 'TWO_ARMS' if all((RECEIPT['arms'].get(n) or {}).get('replay') for n in M2_ARM_ORDER) else 'INCOMPLETE'
    m2_write_receipt()
    m2_event('done', status=RECEIPT['status'], gate=RECEIPT['gate'])


try:
    m2_main()
except BaseException as e:
    srv = M2_CURRENT.get('server')
    if srv is not None:
        RECEIPT['emergency_stop'] = srv.stop(grace=10.0)
    if RECEIPT.get('status') in ('STARTED', None):
        RECEIPT['status'] = 'FAILED'
    RECEIPT['error'] = (type(e).__name__ + ': ' + str(e))[:600]
    m2_write_receipt()
    m2_event('failed', error=RECEIPT['error'])
    if RECEIPT['status'] != 'WATCHDOG_DEADLINE':
        raise
finally:
    M2_CURRENT['done'] = True
    if _m2_started + M2_SESSION_TIMEOUT_S - time.monotonic() < 0:
        print('[m2] WARNING: owned clock passed the session timeout')
