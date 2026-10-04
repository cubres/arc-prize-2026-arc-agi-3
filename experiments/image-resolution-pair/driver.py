# Original diagnostic driver. Executed as a notebook cell after the unchanged owned bootstrap.
import asyncio
import base64
import hashlib
import io
import math
import threading
from types import SimpleNamespace
from urllib.parse import urlsplit

from terminal_evidence import export_terminal_evidence, canonical_sha256


def _write_trial_json(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Trial evidence already exists: {path}")
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _frozen_public_games():
    import arc_agi
    import taaf.game_api
    env_dir = str(Path(_COMP_DIR) / "environment_files")
    spec = taaf.game_api.ArcadeSpec(operation_mode=arc_agi.OperationMode.OFFLINE,
                                 environments_dir=env_dir)
    arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.OFFLINE,
                           environments_dir=env_dir)
    ids = [item.game_id for item in arcade.available_environments]
    expected = TRIAL_PROTOCOL["public_game_ids"]
    if len(ids) != 25 or len(set(ids)) != 25 or set(ids) != set(expected):
        raise RuntimeError(f"Public environment identity drift: {ids}")
    return [taaf.game_api.GameAPI(env_name=game_id, arcade_spec=spec) for game_id in expected]


def _server_request_counts():
    base = urlsplit(os.environ["LOCAL_ANALYZER_BASE_URL"])
    if base.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Quiescence probe requires the local owned backend.")
    url = f"{base.scheme}://{base.netloc}/metrics"
    with urlopen(url, timeout=5) as response:
        payload = response.read().decode("utf-8")
    names = {"vllm:num_requests_running": [], "vllm:num_requests_waiting": []}
    for line in payload.splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        metric = fields[0].split("{", 1)[0]
        if metric in names:
            value = float(fields[1])
            if not math.isfinite(value) or value < 0:
                raise RuntimeError(f"Invalid quiescence metric: {line}")
            names[metric].append(value)
    if any(not values for values in names.values()):
        raise RuntimeError("Required running/waiting request gauges are absent.")
    return {name: sum(values) for name, values in names.items()}


async def _wait_for_quiescence(label):
    start = time.monotonic()
    deadline = min(start + TRIAL_PROTOCOL["transition_drain_s"],
                   NOTEBOOK_START_MONOTONIC + TRIAL_PROTOCOL["outer_soft_wall_s"] - 300)
    samples, consecutive, last_error = [], 0, None
    while time.monotonic() < deadline:
        threads = [thread.name for thread in threading.enumerate()
                   if thread.is_alive() and thread.name.startswith("harness-game")]
        try:
            counts = _server_request_counts()
            last_error = None
        except Exception as exc:
            counts = None
            last_error = repr(exc)
        sample = {"elapsed_s": time.monotonic() - start, "worker_threads": threads,
                  "request_counts": counts, "error": last_error}
        samples.append(sample)
        quiet = not threads and counts is not None and all(value == 0 for value in counts.values())
        consecutive = consecutive + 1 if quiet else 0
        if consecutive >= 2:
            receipt = {"label": label, "pass": True, "samples": samples,
                       "required_consecutive_idle_samples": 2,
                       "no_model_request_sent_by_probe": True}
            _write_trial_json(TRIAL_ROOT / f"quiescence_{label}.json", receipt)
            return receipt
        await asyncio.sleep(5)
    receipt = {"label": label, "pass": False, "samples": samples,
               "required_consecutive_idle_samples": 2, "last_error": last_error}
    _write_trial_json(TRIAL_ROOT / f"quiescence_{label}.json", receipt)
    raise RuntimeError(f"Backend/workers did not quiesce at {label}; next arm is prohibited.")


def _attest_resolution(scale):
    from PIL import Image
    import inference.agent.vision_context as vision
    if _tool_agent.current_grid_image_part is not vision.current_grid_image_part:
        raise RuntimeError("Analyzer is not consuming the verified image renderer.")
    if vision.current_grid_image_upscale() != scale:
        raise RuntimeError("Dynamic renderer did not consume the arm setting.")
    fixture = SimpleNamespace(grid=[[(row + col) % 16 for col in range(64)] for row in range(64)])
    image = vision.current_grid_image_part(fixture)
    raw = base64.b64decode(image["image_url"]["url"].split(",", 1)[1], validate=True)
    with Image.open(io.BytesIO(raw)) as opened:
        size = list(opened.size)
        if size != [64 * scale, 64 * scale]:
            raise RuntimeError(f"Unexpected rendered fixture size: {size}")
    return {"scale": scale, "grid_shape": [64, 64], "image_size": size,
            "png_sha256": hashlib.sha256(raw).hexdigest(),
            "fixture_only": True, "no_game_outcomes_or_model_call": True}


def _restore_arm(arm, arm_dir):
    with open(ANIM_BUNDLE_DIR / "deploy_target.pkl", "rb") as stream:
        arm_target = pickle.load(stream)
    arm_target.actual_run_as_submission = False
    arm_target.is_competition_rerun = False
    if float(arm_target.max_runtime_s) != 32400:
        raise RuntimeError("Original deployment-target budget drift.")
    with open(ANIM_BUNDLE_DIR / "benchmark_initial.pkl", "rb") as stream:
        arm_bm = pickle.load(stream)
    if arm_bm.label != "anim-20260807-anim" or type(arm_bm.solver).__module__ != "inference.framework.solver":
        raise RuntimeError("Original solver/benchmark identity drift.")
    if arm_bm.solver.animation_awareness is not True or arm_bm.solver.hard_noop_guard is not True:
        raise RuntimeError("Original animation/noop settings drift.")
    arm_bm.job_dir = arm_dir
    arm_bm.games = _frozen_public_games()
    arm_bm.n_passes, arm_bm.game_weights = 1, None
    arm_bm.solver.max_runtime_s_per_game = 7920.0
    arm_bm.solver.analyzer_timeout = 900.0
    arm_bm.solver.concurrency = 28
    arm_bm.solver.max_actions_per_game = None
    arm_bm.solver.save_request_logs = False
    return arm_bm, arm_target


if TRUE_SUBMISSION:
    raise RuntimeError("This private diagnostic trial cannot run as a competition submission.")
if TRIAL_PROTOCOL["arms"] != [{"label": "control4", "scale": 4}, {"label": "image10", "scale": 10}]:
    raise RuntimeError("Frozen arm order/settings changed.")
required = 2 * TRIAL_PROTOCOL["active_wall_s_per_arm"] + 2 * TRIAL_PROTOCOL["transition_drain_s"] + 300
remaining = NOTEBOOK_START_MONOTONIC + TRIAL_PROTOCOL["outer_soft_wall_s"] - time.monotonic()
if remaining < required:
    raise RuntimeError(f"Setup left insufficient wall time for both frozen arms: {remaining} < {required}")

if str(BUNDLE_DIR) not in sys.path:
    sys.path.insert(0, str(BUNDLE_DIR))
import vllm_server_watchdog as vllm_watchdog
watchdog_setup = vllm_watchdog.load_setup(BUNDLE_DIR / "serving_setup.py")
watchdog_controller, watchdog_thread = vllm_watchdog.start_background(
    watchdog_setup, vllm_watchdog.WatchdogConfig(interval_seconds=15.0, request_timeout_seconds=5,
                                              failure_threshold=4, max_restart_attempts=2))

arm_evidence = []
try:
    await _wait_for_quiescence("before_control4")
    for arm in TRIAL_PROTOCOL["arms"]:
        scale, label = arm["scale"], arm["label"]
        arm_dir = TRIAL_ROOT / label
        arm_dir.mkdir(exist_ok=False)
        os.environ["MULTIMODAL_UPSCALE"] = str(scale)
        persisted = json.loads(SETUP_ENV_PATH.read_text())
        persisted["MULTIMODAL_UPSCALE"] = str(scale)
        SETUP_ENV_PATH.write_text(json.dumps(persisted, indent=2, sort_keys=True) + "\n")
        expected_env = TRIAL_PROTOCOL["fixed_analyzer_env"]
        for key, expected in expected_env.items():
            if os.environ.get(key) != expected:
                raise RuntimeError(f"Fixed analyzer setting drift: {key}")
        fixture_receipt = _attest_resolution(scale)
        arm_bm, arm_target = _restore_arm(arm, arm_dir)
        started_epoch, started_mono = time.time(), time.monotonic()
        _write_trial_json(arm_dir / "arm_pre_run.json", {
            "arm": arm, "started_epoch": started_epoch,
            "active_wall_s": TRIAL_PROTOCOL["active_wall_s_per_arm"],
            "protocol_sha256": TRIAL_PROTOCOL_SHA256, "fixture": fixture_receipt,
            "watchdog_restarts_before": watchdog_controller.restart_attempts,
            "all_other_analyzer_settings": expected_env,
            "restored_fresh_original_benchmark_and_target": True})
        print(f"ARC3_ARM_START label={label} scale={scale} games=25 seconds={TRIAL_PROTOCOL['active_wall_s_per_arm']}", flush=True)
        try:
            await arm_bm.run(
                soft_end_time=datetime.fromtimestamp(started_epoch + TRIAL_PROTOCOL["active_wall_s_per_arm"]),
                runtime_environment=arm_target, minimal_diagnostics=True)
        finally:
            arm_bm._save_json()
        evidence, evidence_receipt = export_terminal_evidence(
            arm_dir / "benchmark.json", TRIAL_PROTOCOL["public_game_ids"],
            arm_dir / "actual_terminal_evidence", arm=label)
        from inference.tools.eval import evaluate_runs, save_score_file
        score_summary = evaluate_runs([arm_dir])
        score_path = Path(save_score_file(score_summary, run_dirs=[arm_dir],
                                         output_path=arm_dir / "score.json"))
        if score_path != arm_dir / "score.json" or not score_path.is_file():
            raise RuntimeError("Frozen bundled evaluator did not write the arm score.")
        await _wait_for_quiescence(f"after_{label}")
        _write_trial_json(arm_dir / "arm_post_run.json", {
            "arm": arm, "elapsed_with_drain_s": time.monotonic() - started_mono,
            "terminal_evidence": evidence_receipt,
            "state_counts": evidence["state_counts"],
            "watchdog_restarts_after": watchdog_controller.restart_attempts,
            "score_json_sha256": hashlib.sha256(score_path.read_bytes()).hexdigest(),
            "no_submission_file_written": True})
        arm_evidence.append(evidence)
        print(f"ARC3_ARM_TERMINAL label={label} denominator=25 actions={evidence['history_action_count']} states={evidence['state_counts']}", flush=True)
    if [row["arm"] for row in arm_evidence] != ["control4", "image10"]:
        raise RuntimeError("Both frozen arms did not complete.")
    paired = [{"game_id": first["game_id"], "control4_score": first["final_score"],
               "image10_score": second["final_score"],
               "difference": second["final_score"] - first["final_score"],
               "control4_state": first["state"], "image10_state": second["state"]}
              for first, second in zip(arm_evidence[0]["games"], arm_evidence[1]["games"])]
    _write_trial_json(TRIAL_ROOT / "paired_public25_diagnostic.json", {
        "purpose": "REUSED_PUBLIC25_FIXED_ORDER_SINGLE_RUN_DIAGNOSTIC", "denominator": 25,
        "official_score": False, "independent_quality_validation": False,
        "image10_minus_control4_mean": sum(row["difference"] for row in paired) / 25,
        "watchdog_restarts": watchdog_controller.restart_attempts,
        "sequential_arm_order_confound": True, "no_parameter_selection": True,
        "perception_and_serialized_image_context_effects_are_coupled": True,
        "throughput_claim": False, "no_submission_file_written": True, "games": paired})
    _write_trial_json(TRIAL_ROOT / "pair_terminal_receipt.json", {
        "status": "COMPLETE_DIAGNOSTIC", "arms": 2, "games_per_arm": 25,
        "protocol_sha256": TRIAL_PROTOCOL_SHA256,
        "elapsed_notebook_s": time.monotonic() - NOTEBOOK_START_MONOTONIC,
        "official_submission_authorized": False, "no_submission_file_written": True})
finally:
    try:
        vllm_watchdog.stop_background(timeout_seconds=15.0)
    finally:
        for command in json.loads((BUNDLE_DIR / "teardown_commands.json").read_text()):
            print(f"taaf.kaggle: teardown command: {command}", flush=True)
            subprocess.run(command, shell=True, check=False, cwd=WORKING_DIR,
                           env=_command_env(), timeout=30.0)
