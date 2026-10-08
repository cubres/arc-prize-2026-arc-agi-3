"""Read-only V17 commit-output check = the V15/V16 checks (check_commit_output_arc3.py) plus V17's own report:
every input check ok, no fallback, no warning, teardown recorded, and the timing summary present.
Usage: python -I check_commit_output_arc3_v17.py <output_dir> <out.json>   (exit 0 only if everything passes)"""
import json, subprocess, sys
from pathlib import Path
d, out = Path(sys.argv[1]), Path(sys.argv[2])
base_out = out.with_name(out.stem + '_base.json')
base = subprocess.run([sys.executable, '-I', str(Path(__file__).with_name('check_commit_output_arc3.py')), str(d), str(base_out)], capture_output=True, text=True)
res = {'base_check_exit': base.returncode, 'base_check': json.loads(base_out.read_text()) if base_out.exists() else None, 'v17': {}}
ok = base.returncode == 0
p = d / 'v17_report.json'
if not p.is_file():
    res['v17']['report'] = 'missing'; ok = False
else:
    r = json.loads(p.read_text()); t = r.get('timing') or {}
    checks = {
        'all_input_checks_ok': bool(r.get('checks')) and all(str(v).startswith('ok') for v in r['checks'].values()),
        'no_fallbacks': r.get('fallbacks') == [],
        'no_warnings': r.get('warnings') == [],
        'interactive_run': r.get('rerun') is False,
        'teardown_recorded': 'teardown' in r,
        'timing_summary_present': t.get('completed', 0) > 0 and t.get('threads', 0) >= 1 and t.get('logging_errors', 1) == 0,
    }
    res['v17'] = {'checks': checks, 'failed_input_checks': {k: v for k, v in (r.get('checks') or {}).items() if not str(v).startswith('ok')},
                  'fallbacks': r.get('fallbacks'), 'warnings': r.get('warnings'),
                  'timing': {k: v for k, v in t.items() if k != 'per_thread'}}
    ok = ok and all(checks.values())
res['verdict'] = 'PASS' if ok else 'FAIL'
out.write_text(json.dumps(res, indent=1, default=str)); print(res['verdict'], res['v17'].get('checks', res['v17']))
sys.exit(0 if ok else 1)
