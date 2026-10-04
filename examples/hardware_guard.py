"""Original fail-closed inventory check before ARC3 CUDA/model setup.

Only standard-library modules are used. This verifies allocated hardware;
it makes no assertion about Kaggle's quota billing rate.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import re
import subprocess
from decimal import Decimal, InvalidOperation
from pathlib import Path


QUERY = [
    "nvidia-smi", "--query-gpu=name,compute_cap,memory.total",
    "--format=csv,noheader,nounits",
]
TIMEOUT_SECONDS = 15
MINIMUM_MEMORY_MIB = 90 * 1024


def validate_inventory(stdout: str, returncode: int) -> dict:
    if returncode != 0:
        raise ValueError(f"nvidia-smi exited with {returncode}")
    rows = [row for row in csv.reader(io.StringIO(stdout)) if any(x.strip() for x in row)]
    if len(rows) != 1:
        raise ValueError(f"Expected exactly one physical GPU; observed {len(rows)}")
    if len(rows[0]) != 3:
        raise ValueError("GPU query must return name, compute capability, and memory")
    name, capability_text, memory_text = [part.strip() for part in rows[0]]
    if re.search(r"\bRTX\s+PRO\s+6000\b", name, flags=re.IGNORECASE) is None:
        raise ValueError(f"Expected RTX PRO 6000; observed {name!r}")
    try:
        capability = Decimal(capability_text)
        memory_mib = Decimal(memory_text)
    except InvalidOperation as exc:
        raise ValueError("Non-numeric GPU capability or memory") from exc
    if not capability.is_finite() or capability != Decimal("12.0"):
        raise ValueError(f"Expected SM120; observed capability {capability_text!r}")
    if not memory_mib.is_finite() or memory_mib < MINIMUM_MEMORY_MIB:
        raise ValueError(f"Expected at least90GiB; observed memory {memory_text!r}MiB")
    return {
        "physical_gpu_count": 1,
        "name": name,
        "compute_capability": capability_text,
        "sm": 120,
        "memory_total_mib": str(memory_mib),
        "minimum_memory_mib": MINIMUM_MEMORY_MIB,
    }


def run_guard(output_root: str = "/kaggle/working") -> dict:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    output = root / f"codex_arc3_hardware_{stamp}.json"
    receipt = {
        "checked_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "query": QUERY,
        "timeout_seconds": TIMEOUT_SECONDS,
        "phase": "BEFORE_NON_STDLIB_IMPORTS_AND_MODEL_SETUP",
        "quota_multiplier_verified": False,
        "model_calls": 0,
        "status": "FAIL",
    }
    try:
        result = subprocess.run(QUERY, capture_output=True, text=True,
                                check=False, timeout=TIMEOUT_SECONDS)
        receipt["returncode"] = result.returncode
        receipt["gpu"] = validate_inventory(result.stdout, result.returncode)
        receipt["status"] = "PASS"
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        output.write_text(json.dumps(receipt, indent=2) + "\n")
        print(f"ARC3_HARDWARE_GATE_FAIL receipt={output} error={receipt['error']}", flush=True)
        raise RuntimeError(receipt["error"]) from exc
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(f"ARC3_HARDWARE_GATE_PASS receipt={output} gpu={receipt['gpu']}", flush=True)
    return {"path": str(output), **receipt}

