"""Original explanatory figure for a frozen ARC3 resolution experiment.

Run with Python 3, numpy, Pillow and matplotlib. This draws an invented grid;
it reads no benchmark games, calls no model and writes no submission.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image


def synthetic_image(scale: int):
    # ARC3's published 16-color palette, independently vectorized for this figure.
    palette = np.array([
        (255,255,255), (204,204,204), (153,153,153), (102,102,102),
        (51,51,51), (0,0,0), (229,58,163), (255,123,204),
        (249,60,49), (30,147,255), (136,216,241), (255,220,0),
        (255,133,27), (146,18,49), (79,204,48), (163,86,214),
    ], dtype=np.uint8)
    row, col = np.indices((64, 64))
    grid = (row + col) % 16
    image = Image.fromarray(palette[grid]).resize(
        (64 * scale, 64 * scale), Image.Resampling.NEAREST)
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    raw = stream.getvalue()
    url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    return image, {
        "scale": scale, "width": image.width, "height": image.height,
        "pixels": image.width * image.height, "png_bytes": len(raw),
        "data_url_characters": len(url), "png_sha256": hashlib.sha256(raw).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="A new output directory; existing directories are refused.")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    images, measurements = zip(*(synthetic_image(scale) for scale in (4, 10)))
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    fig = plt.figure(figsize=(13.8, 7.1), facecolor="#faf8f1")
    fig.text(.05, .92, "One resolution change. Two possible effects.",
             fontsize=24, weight="bold", color="#172c40")
    fig.text(.05, .865, "ARC3 private trial: control4 → image10 • 50 minutes per arm • same 25 public games",
             fontsize=12, color="#526372")
    for index, (image, record) in enumerate(zip(images, measurements)):
        left = .05 + .31 * index
        ax = fig.add_axes([left, .30, .25, .44])
        ax.imshow(image, interpolation="nearest")
        ax.set_axis_off()
        title = "control4" if index == 0 else "image10"
        ax.set_title(f"{title}  ·  {record['width']} × {record['height']}",
                     fontsize=16, weight="bold", color="#172c40", pad=15)
        fig.text(left, .235,
                 f"{record['pixels']:,} pixels\n{record['png_bytes']:,} PNG bytes in this fixture",
                 fontsize=12, color="#526372", linespacing=1.6)
    fig.text(.68, .70, "More rendered pixels", fontsize=17, weight="bold", color="#172c40")
    fig.text(.68, .60, "6.25× as many pixels\nThe same cells may be easier to resolve.",
             fontsize=13, color="#526372", linespacing=1.65)
    fig.text(.68, .465, "A different serialized image", fontsize=17, weight="bold", color="#172c40")
    fig.text(.68, .33, "This harness counts image data as text\nwhen estimating context use. Larger images\ncan change truncation and remaining context.",
             fontsize=12.5, color="#526372", linespacing=1.65)
    fig.text(.05, .12, "Interpret the result as a combined perception + context intervention.",
             fontsize=15, weight="bold", color="#172c40")
    fig.text(.05, .06, "Invented 64 × 64 fixture; bytes depend on image content. Fixed arm order and a reused public panel limit attribution.\n"
             "This figure reports no model response, quality gain, official score or submission.",
             fontsize=10, color="#526372", linespacing=1.5)
    for extension in ("svg", "png"):
        fig.savefig(args.output / f"resolution-context.{extension}", dpi=180,
                    facecolor=fig.get_facecolor(), metadata={"Date": None} if extension == "svg" else None)
    plt.close(fig)
    receipt = {
        "schema": "arc3_resolution_context_illustration_v1",
        "invented_fixture": True, "benchmark_data_read": False,
        "model_calls": 0, "official_score": False, "submission_written": False,
        "nearest_neighbor_renderer": True, "measurements": list(measurements),
        "pixel_ratio": measurements[1]["pixels"] / measurements[0]["pixels"],
        "reference_protocol": "https://github.com/cubres/arc-prize-2026-arc-agi-3/blob/6d108ad7b2b2d700e8e38ca179c147c4c0a620db/experiments/image-resolution-pair/v3/protocol.json",
        "context_estimator_source": {
            "dataset": "https://www.kaggle.com/datasets/jakobbrggen/taaf-kaggle-source-anim-20260807-anim",
            "path": "src/ARC3-Inference/inference/agent/tool_agent.py",
            "sha256": "856bf9b895d0ad8b959c8f828c7132b0e09eaa47f4c5cc6173785354090f8be7",
            "behavior": "JSON-serialize the entire request, then estimate max(1, (characters + 2) // 3); old message blocks can be dropped at the context budget.",
            "foreign_source_included": False,
        },
        "data_url_warning": "Character counts are not processor image-token counts or a model throughput measurement.",
        "figure_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(args.output.iterdir())
        },
    }
    (args.output / "illustration.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
