"""Run a relative-path, stdlib-only synthetic replay. No game or model imports.

This uses exact public reference function bodies with synthetic state and
fail-on-action sentinels. It does not play a game or estimate a score.
"""
from __future__ import annotations

import ast
from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from empty_animation_schema import complete_empty_animation_view

HERE = Path(__file__).resolve().parent
PINS = {
    'pinned_animation_reference.source.py':
        'b835584ead6d449c3bfb72f1c1df03186907ae882e4325cfc97dd584684c3824',
    'pinned_lazy_animation_reference.source.py':
        '8000d9470d4ce33220c8fb53f0463c77693f85af611f11eae391280086fb3d96',
    'portable_reference_functions.json':
        '7b82d87c919c54654adaed3ab007390934712098e69d46ff1642f3ff07032ac7',
}


def pinned(name):
    raw = (HERE / name).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PINS[name]:
        raise RuntimeError('Reference source changed: ' + name)
    return raw.decode()


def load_definitions(source, names, namespace):
    selected = [node for node in ast.walk(ast.parse(source))
                if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                and node.name in names]
    if sorted(node.name for node in selected) != sorted(names):
        raise RuntimeError('Exact reference definitions required')
    module = ast.Module(body=[ast.ImportFrom(
        module='__future__', names=[ast.alias(name='annotations')], level=0),
        *copy.deepcopy(selected)], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<synthetic reference replay>', 'exec'), namespace)
    return namespace


def forbid_action(*_args, **_kwargs):
    raise AssertionError('An action or action normalization was attempted')


def main():
    animation = load_definitions(pinned('pinned_animation_reference.source.py'), {
        '_color_char', '_cell_at', '_diff_cells', '_bbox_text', '_format_changes',
        'build_animation_view',
    }, {'defaultdict': defaultdict, 'ARC_COLOR_CHARS': tuple('0123456789abcdef'),
        'ANIMATION_MAX_CELLS_PER_STEP': 24, 'ANIMATION_MAX_TOTAL_CELLS': 80})
    render = animation['build_animation_view']
    old = render(None)
    new = complete_empty_animation_view(old, None)
    lazy_before = load_definitions(pinned('pinned_lazy_animation_reference.source.py'),
                                   {'_LazyAnimation'}, {'_animation_fetch': lambda kind: old})
    try:
        _ = lazy_before['_LazyAnimation']('timeline', {})['frames']
    except KeyError as error:
        before_missing_key = error.args[0]
    else:
        raise AssertionError('Expected exact legacy consumer failure')
    lazy_after = load_definitions(pinned('pinned_lazy_animation_reference.source.py'),
                                  {'_LazyAnimation'}, {'_animation_fetch': lambda kind: new})
    proxy = lazy_after['_LazyAnimation']('timeline', {})
    if (proxy['frames'], proxy['steps'], proxy['action']) != (0, [], None):
        raise AssertionError('Completed empty schema differs')

    references = json.loads(pinned('portable_reference_functions.json'))['functions']
    for descriptor in references.values():
        if hashlib.sha256(descriptor['source'].encode()).hexdigest() != descriptor['source_sha256']:
            raise RuntimeError('Reference function changed')
    query = load_definitions(references['step_env']['source'], {'step_env'},
                             {'ANIMATION_ENABLED': True})['step_env']
    state = SimpleNamespace(animation_record=None, action_count=17,
                            _normalize_actions=forbid_action,
                            _execute_action=forbid_action)
    queries = 0

    def read_animation(arguments):
        nonlocal queries
        queries += 1
        return query(state, arguments)

    handler = load_definitions(references['_handle_animation']['source'],
        {'_handle_animation'}, {
            'self': SimpleNamespace(_step_env_callback=read_animation),
            'build_animation_view': lambda record: complete_empty_animation_view(render(record), record),
            'build_animation_frames': forbid_action,
            '_animation_timeline_enabled': lambda: True,
        })['_handle_animation']
    for _ in range(1024):
        result = handler({'kind': 'timeline'})
        if result['frames'] != 0 or result['steps'] != []:
            raise AssertionError('Repeated query changed the result')
    if state.action_count != 17 or queries != 1024:
        raise AssertionError('Unexpected query/action accounting')
    normal = render({'action_display': 'ACTION1',
                     'chain': [((0,),), ((1,),), ((0,),)]})
    if complete_empty_animation_view(normal, None) is not normal:
        raise AssertionError('Normal animation result was changed')

    compact = lambda value: json.dumps(value, separators=(',', ':')).encode()
    print(json.dumps({
        'status': 'PASS_SYNTHETIC_REPLAY_ONLY',
        'legacy_exact_lazy_consumer_missing_key': before_missing_key,
        'completed_empty_view': new,
        'replayed_read_queries': queries,
        'synthetic_action_count_before': 17,
        'synthetic_action_count_after': state.action_count,
        'normal_timeline_preserved_by_identity': True,
        'empty_json_additional_bytes_for_null_action': len(compact(new)) - len(compact(old)),
        'real_game_model_api_network_calls': 0,
        'score_or_production_failure_frequency_claim': None,
        'frames_zero_meaning': 'No reported animation timeline; not zero engine frames or prior action cost.',
        'palette_used_only_in_synthetic_normal_example': '0123456789abcdef',
    }, indent=2))


if __name__ == '__main__':
    main()
