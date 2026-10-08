"""Read-only sanity check of an ARC3 public-notebook commit output before submitting from that version.

Usage: python -I check_commit_output_arc3.py <output_dir> <out.json>
Checks (all must pass): submission.parquet exists, has exactly the placeholder schema
[row_id, game_id, end_of_game, score], at least one row, no null cells; benchmark.json has >= 1 run,
every game has at least one non-RESET action and > 0 generated tokens in its history, no game state 'crashed'/'error';
summary.txt reports runs == number of game_runs.
"""
import json, re, sys
from pathlib import Path
import pyarrow.parquet as pq

d, out = Path(sys.argv[1]), Path(sys.argv[2])
res, ok = {"output_dir": str(d), "checks": {}}, True
def chk(name, cond, detail):
    global ok
    res["checks"][name] = {"pass": bool(cond), "detail": detail}; ok &= bool(cond)
p = d / "submission.parquet"
chk("parquet_exists", p.is_file(), str(p))
if p.is_file():
    t = pq.read_table(p); rows = t.to_pylist()
    chk("parquet_columns", t.column_names == ["row_id", "game_id", "end_of_game", "score"], t.column_names)
    chk("parquet_rows>=1", t.num_rows >= 1, t.num_rows)
    chk("parquet_no_nulls", all(v is not None for r in rows for v in r.values()), rows[:3])
    res["parquet_rows"] = rows[:5]; res["parquet_num_rows"] = t.num_rows
b = d / "benchmark.json"
chk("benchmark_exists", b.is_file(), str(b))
if b.is_file():
    bm = json.loads(b.read_text()); runs = bm.get("game_runs", [])
    chk("runs>=1", len(runs) >= 1, len(runs))
    per = []
    for g in runs:
        h = g.get("history", [])
        acts = [x for x in h if (x.get("action") or {}).get("id") not in (None, "RESET")]
        toks = sum(x.get("generated_tokens", 0) for x in h)
        per.append({"game": g.get("game_id"), "state": g.get("state"), "non_reset_actions": len(acts), "gen_tokens": toks,
                    "levels": g.get("levels_completed"), "score": round(g.get("final_score") or 0, 2)})
    chk("every_game_has_actions", all(x["non_reset_actions"] > 0 for x in per), [x["non_reset_actions"] for x in per])
    chk("every_game_has_tokens", all(x["gen_tokens"] > 0 for x in per), [x["gen_tokens"] for x in per])
    chk("no_crashed_game", not any(str(x["state"]).lower() in ("crashed", "error", "failed") for x in per), sorted({str(x["state"]) for x in per}))
    res["games"] = per
s = d / "summary.txt"
if s.is_file():
    m = re.search(r"runs:\s+(\d+)", s.read_text())
    chk("summary_runs_match", m and b.is_file() and int(m.group(1)) == len(runs), m.group(0) if m else None)
    ms = re.search(r"mean score:\s+([0-9.]+)", s.read_text()); res["summary_mean_score"] = float(ms.group(1)) if ms else None
res["verdict"] = "PASS" if ok else "FAIL"
out.write_text(json.dumps(res, indent=1, default=str))
print(res["verdict"], {k: v["pass"] for k, v in res["checks"].items()}, "rows", res.get("parquet_rows"), "mean", res.get("summary_mean_score"))
sys.exit(0 if ok else 1)
