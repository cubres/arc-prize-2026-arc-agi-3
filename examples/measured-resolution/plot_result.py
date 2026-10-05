"""Reproduce the measured ARC3 resolution diagnostic from its 25 retained pairs.

Requires Python 3, numpy and matplotlib. The JSON contains measured scores;
no benchmark environment, model download, GPU or submission is required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="New directory; existing outputs are preserved.")
    args = parser.parse_args()
    data = json.loads(args.data.read_text())
    pairs = data["all_25_pairs"]
    assert len(pairs) == len({r["game_id"] for r in pairs}) == 25
    assert [r["panel_index"] for r in pairs] == list(range(25))
    assert data["official_score"] is False and data["promoted"] is False
    control = np.array([r["control4_score"] for r in pairs], dtype=float)
    image = np.array([r["image10_score"] for r in pairs], dtype=float)
    differences = image - control
    assert np.isfinite(control).all() and np.isfinite(image).all()
    assert ((control >= 0) & (control <= 100)).all()
    assert ((image >= 0) & (image <= 100)).all()
    assert np.allclose(differences, [r["difference"] for r in pairs], atol=1e-12, rtol=0)
    assert abs(float(differences.mean()) - data["image10_minus_control4_mean"]) < 1e-12
    assert all(data["arms"][arm]["state_counts"]["cancelled"] == 25
               for arm in ("control4", "image10"))
    args.output.mkdir(parents=True, exist_ok=False)
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.hashsalt": "arc3-measured-resolution-20261005"})
    ink, muted, positive, negative = "#183144", "#596976", "#21826b", "#c96536"
    fig = plt.figure(figsize=(14.5, 10.0), facecolor="#faf8f2")
    fig.text(.055, .946, "Sharper images. A lower measured score.",
             fontsize=25, weight="bold", color=ink)
    fig.text(.055, .903,
             "ARC3 diagnostic · 25 retained public game pairs · 50 minutes per arm · control4 followed by image10",
             fontsize=11.3, color=muted)
    ax = fig.add_axes([.105, .205, .48, .645], facecolor="#faf8f2")
    y = np.arange(25)
    colors = [positive if d > 0 else negative if d < 0 else "#aaaeb0" for d in differences]
    ax.barh(y, differences, height=.68, color=colors, zorder=3)
    zeros = np.flatnonzero(differences == 0)
    ax.scatter(np.zeros(len(zeros)), zeros, s=16, color="#aaaeb0", zorder=4)
    ax.axvline(0, color=ink, linewidth=1, zorder=2)
    ax.set_yticks(y, [r["game_id"].split("-")[0] for r in pairs], color=muted, fontsize=9)
    ax.set_ylim(24.7, -.7)
    ax.set_xlim(-37, 16)
    ax.set_xticks([-30, -20, -10, 0, 10])
    ax.tick_params(axis="x", labelsize=10, colors=muted)
    ax.grid(axis="x", color="#deded7", alpha=.65, zorder=0)
    ax.set_xlabel("Image10 minus control4 score points", fontsize=11, color=ink, labelpad=10)
    ax.set_title("Every game stays in the comparison", loc="left", fontsize=15,
                 weight="bold", color=ink, pad=14)
    for idx, value in enumerate(differences):
        if abs(value) >= 10:
            ax.text(value - .8 if value < 0 else value + .6, idx, f"{value:+.2f}",
                    ha="right" if value < 0 else "left", va="center", fontsize=9, color=ink)
    x = .635
    mean = data["image10_minus_control4_mean"]
    lo, hi = data["reporting_only_bootstrap"]["percentile_95"]
    fig.text(x, .823, f"{mean:+.3f} score points", fontsize=25, weight="bold", color=ink)
    fig.text(x, .774, f"Control4 {control.mean():.3f} → image10 {image.mean():.3f}\n"
             f"7 improvements · 5 declines · 13 ties", fontsize=12, color=muted, linespacing=1.7)
    fig.text(x, .686, f"Paired descriptive interval: [{lo:.3f}, {hi:.3f}]",
             fontsize=11.7, color=ink)
    fig.text(x, .634, "20,000 game-pair resamples; reused panel.\nThis interval is not hidden-game evidence.",
             fontsize=10.7, color=muted, linespacing=1.6)
    fig.text(x, .551, "More progress required more actions", fontsize=15,
             weight="bold", color=ink)
    fig.text(x, .489, "Completed levels   21 → 24\nRecorded actions   760 → 902",
             fontsize=12, color=muted, linespacing=1.8)
    metrics = data["shared_backend_metrics"]
    fig.text(x, .387, "The shared backend was under pressure", fontsize=15,
             weight="bold", color=ink)
    fig.text(x, .354, f"{int(metrics['preemptions'])} preemptions across both arms and setup\n"
             f"Mean queue time {metrics['mean_queue_seconds_per_completed_request']:.1f}s\n"
             f"Mean inference time {metrics['mean_inference_seconds_per_completed_request']:.1f}s",
             fontsize=12, color=muted, linespacing=1.6, va="top")
    fig.text(.055, .117,
             "Both 25-game arms completed and were independently audited. Final backend teardown failed.",
             fontsize=12, weight="bold", color=ink)
    fig.text(.055, .058,
             "All 50 games ended at the time limit; none won or crashed. Fixed arm order and coupled rendering/context effects limit attribution.\n"
             "No game was excluded. Shared server counters cannot establish a per-arm runtime effect. No official score or model promotion.",
             fontsize=10.4, color=muted, linespacing=1.65)
    for ext in ("svg", "png"):
        fig.savefig(args.output / f"measured-resolution-result.{ext}", dpi=180,
                    facecolor=fig.get_facecolor(), metadata={"Date": None} if ext == "svg" else None)
    plt.close(fig)
    receipt = {"input_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
               "retained_pairs": 25, "mean_difference": float(differences.mean()),
               "measured_data": True, "model_calls": 0, "official_score": False,
               "figure_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(args.output.iterdir())}}
    with (args.output / "plot-receipt.json").open("x") as out:
        out.write(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
