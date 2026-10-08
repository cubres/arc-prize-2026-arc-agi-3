"""Build the M2-based bench candidate for prvsiyan/zz-gpuchk-899422 (successor of the V13 head) offline.
New top cells: markdown + one code cell (m2_bench_cell_template.py filled with the exact V16 recipe code, sha256-pinned).
All 29 V13 cells kept verbatim (code -> inactive raw). No compressed copies. Packet dataset not attached and not touched.
Usage: python -I -B build_m2_bench.py <new build dir>"""
import copy, hashlib, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; A = HERE.parent
B = Path(sys.argv[1]).resolve(); B.mkdir(parents=False, exist_ok=False)
sha = lambda b: hashlib.sha256(b).hexdigest()
def require(ok, m):
    if not ok: raise RuntimeError(m)
V13_SERVER_SHA = 'feea48507612c51cc0ee21f9deb413e84515e33ee1c4af2b4097253a7b8e702a'
META_SHA = '59137137241227996c3d2f5a27b158863cdb6278500857bd6907fbb9eafbd497'
V16_SHA = 'a02293f9363ae348fc997ec5d89d255c767c4988def3494adf6e9d66a7d811f3'
pull = A / 'v14b_build_20261008T150804Z/fresh_pull_v13'
v13_raw, meta_raw = (pull / 'zz-gpuchk-899422.ipynb').read_bytes(), (pull / 'kernel-metadata.json').read_bytes()
require(sha(v13_raw) == V13_SERVER_SHA and sha(meta_raw) == META_SHA, 'V13 head copy drift')
v16_raw = (A / 'candidate_public_v16_20261008T151232Z/arc-agi-3-stock-taaf-action7-shadow.ipynb').read_bytes()
require(sha(v16_raw) == V16_SHA, 'V16 candidate drift')
v16 = json.loads(v16_raw)
src = lambda c: ''.join(c['source']) if isinstance(c['source'], list) else c['source']
cells = {i: src(v16['cells'][i]) for i in (8, 9, 11, 17)}
for i in cells: require(v16['cells'][i]['cell_type'] == 'code', 'V16 cell %d not code' % i)
require(cells[8].startswith('# V15 (prvsiyan, Apache-2.0): Kaggle mounts inputs'), 'cell 8 identity')
require(cells[11].startswith('import os\nimport threading'), 'cell 11 identity')
require(cells[17].startswith('# Paste this entire file into the launcher cell.'), 'cell 17 identity')
# cell 9 without the harness-bundle copy and patch (server-only bench); every removed line counted exactly once
removed = ["ORIG_BUNDLE_DIR   = v15_input('/kaggle/input/datasets/dfranzen/taaf-kaggle-source-bundle-copy')  # V15\n",
           "# Apply harness patch\nBUNDLE_DIR = Path('/kaggle/taaf-kaggle-source-share')\n!rm -Rf $BUNDLE_DIR\n!cp -a $ORIG_BUNDLE_DIR $BUNDLE_DIR\n"
           "subprocess.run([\"git\", \"apply\", \"--include=ARC3-Inference/*\", \"-v\", \"/kaggle/harness-changes.patch\"], cwd=f\"{BUNDLE_DIR}/src\", check=True)\n"
           "print('harness patch applied successfully')\n"]
c9 = cells[9]
for r in removed:
    require(c9.count(r) == 1, 'cell 9 removal not unique: ' + r[:40]); c9 = c9.replace(r, '')
require('!' not in ''.join(l[:1] for l in c9.splitlines()), 'IPython magic left in cell 9 subset')
marker = '# ---- launch detached and wait for health ----\n'
require(cells[17].count(marker) == 1, 'cell 17 marker'); c17 = cells[17].split(marker)[0]
require('Popen' not in c17 and 'precache_model_thread' not in c17, 'cell 17 prefix contains the launch')
parts = {'CELL08': cells[8], 'CELL09D': c9, 'CELL11': cells[11], 'CELL17P': c17}
for k, v in parts.items(): compile(v, k, 'exec')
derivation = {'v16_source_sha256': V16_SHA,
              'cell08': {'v16_index': 8, 'verbatim': True, 'sha256': sha(cells[8].encode())},
              'cell09': {'v16_index': 9, 'verbatim': False, 'v16_sha256': sha(cells[9].encode()), 'removed_exact_text_sha256': [sha(r.encode()) for r in removed],
                         'removed_what': 'ORIG_BUNDLE_DIR line and the harness-bundle copy + git apply block (server-only bench needs no harness)'},
              'cell11': {'v16_index': 11, 'verbatim': True, 'sha256': sha(cells[11].encode())},
              'cell17': {'v16_index': 17, 'verbatim': 'prefix', 'v16_sha256': sha(cells[17].encode()), 'cut_before': marker.strip(),
                         'note': 'server spawn, readiness and teardown are owned by the bench cell; the argument list is used as built'}}
t = (HERE / 'm2_bench_cell_template.py').read_text()
fill = {'__V16_SOURCE_SHA__': repr(V16_SHA), '__DERIVATION__': repr(derivation)}
for k, v in parts.items():
    fill['__%s_SHA__' % k] = repr(sha(v.encode())); fill['__%s__' % k] = repr(v)
for k, v in fill.items():
    require(t.count(k) == 1, 'placeholder ' + k); t = t.replace(k, v)
require('__' + 'CELL' not in t, 'unfilled placeholder')
compile(t, 'bench', 'exec'); first = __import__('ast').parse(t).body[0]
require(first.targets[0].id == '_m2_started', 'owned clock must be the first statement')
(B / 'm2_bench_cell.py').write_text(t)
original = json.loads(v13_raw); require(len(original['cells']) == 29, 'V13 cell count drift')
retained = []
for i, cell in enumerate(original['cells']):
    value = copy.deepcopy(cell)
    if cell['cell_type'] == 'code':
        value = {k: copy.deepcopy(v) for k, v in cell.items() if k not in ('execution_count', 'outputs')}
        value['cell_type'] = 'raw'; value.setdefault('metadata', {})['format'] = 'text/plain'; value['metadata']['arc3_preserved_original_v13_cell_index'] = i
    require(value['source'] == cell['source'], 'source drift'); retained.append(value)
nb = copy.deepcopy(original)
nb['cells'] = [dict(cell_type='markdown', metadata={}, source=[
    '# ARC3: speculative-decoding / FR-Spec check on the M2 serving stack (worker V14-M2)\n',
    '\n',
    'Our public notebook now runs the Franzen M2 recipe (Apache-2.0 code; Qwen Community License weights). This private bench boots that exact '
    'serving stack twice: once without the FR-Spec hot-token map, once exactly as in public V16. Each boot replays the ten per-game model-call '
    'snapshots from the public commit run at ten concurrent streams with the V16 sampling settings, and records accepted tokens per step and decode tokens per second. '
    'The pre-registered gate adopts the change only at +10% decode tok/s with zero errors and an equal KV pool. Owned clock, owned server process group, 2,700 s session.\n',
    '\n',
    'All 29 version 13 cells remain below with code inactive. No compressed copies are stored; prior versions remain on Kaggle as their own versions.\n']),
    dict(cell_type='code', metadata={}, execution_count=None, outputs=[], source=t.splitlines(keepends=True))] + retained
nb['metadata']['arc3_v13_preservation'] = dict(original_source_sha256=V13_SERVER_SHA, original_source_bytes=len(v13_raw), original_cell_count=29, original_cells_offset=2,
    all_original_cell_source_representations_preserved=True, original_code_cells_inactive=True, compressed_copy_stored=False)
nb['metadata']['arc3_m2_bench'] = dict(template_sha256=sha((HERE / 'm2_bench_cell_template.py').read_bytes()), cell_sha256=sha(t.encode()), recipe_derivation=derivation)
C = B / 'candidate'; C.mkdir()
raw = (json.dumps(nb, indent=1, ensure_ascii=False) + '\n').encode()
(C / 'zz-gpuchk-899422.ipynb').write_bytes(raw)
meta = json.loads(meta_raw)
overrides = dict(is_private=True, enable_gpu=True, enable_tpu=False, enable_internet=False, machine_shape='NvidiaRtxPro6000', keywords=['gpu'],
                 docker_image='gcr.io/kaggle-private-byod/python@sha256:57e612b484cf3df5026ee4dcc3cb176974b22b2bc0937fb1e16132a8be4cb13c',
                 dataset_sources=['dfranzen/pennyroyal-v253'], kernel_sources=['prvsiyan/arc-agi-3-stock-taaf-action7-shadow'],
                 competition_sources=['arc-prize-2026-arc-agi-3'],
                 model_sources=['dfranzen/albucino-qwen3-8-flash-next-drafter/Transformers/default/1', 'dfranzen/intel-qwen3.8-flash-next-w4a16-autoround/Transformers/default/1'])
pm = dict(meta); pm.update(overrides)
(C / 'kernel-metadata.json').write_text(json.dumps(pm, indent=1) + '\n')
(B / 'PROPOSED_OVERRIDES.json').write_text(json.dumps(dict(overrides=overrides, timeout_seconds=2700,
    note='identity id_no 135090365 / title / code_file unchanged; packet dataset prvsiyan/arc3-native-canary-packet NOT attached and NOT modified; candidate_session_A untouched'), indent=1) + '\n')
rec = dict(built_utc=__import__('time').strftime('%Y-%m-%dT%H:%M:%SZ', __import__('time').gmtime()), candidate_sha256=sha(raw), candidate_bytes=len(raw),
           bench_cell_bytes=len(t.encode()), bench_cell_sha256=sha(t.encode()), v13_head_sha256=V13_SERVER_SHA, v16_source_sha256=V16_SHA,
           cells=len(nb['cells']), active_code_cells=sum(c['cell_type'] == 'code' for c in nb['cells']))
(B / 'BUILD_RECEIPT.json').write_text(json.dumps(rec, indent=1) + '\n'); print(json.dumps(rec, indent=1))
