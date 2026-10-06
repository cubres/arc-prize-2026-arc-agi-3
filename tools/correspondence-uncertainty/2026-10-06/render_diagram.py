"""Render a deterministic SVG from the synthetic example, with no dependencies."""

import argparse
from html import escape
from pathlib import Path

from example import example_report


def render_svg():
    report = example_report()
    if report["status"] != "CERTIFIED_UNDER_COST_MODEL":
        raise ValueError("example must qualify")
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1440" height="1100" viewBox="0 0 1440 1100" role="img" aria-labelledby="title desc">',
             '<title id="title">Assignment ambiguity: a tied pair and an isolated anchor</title>',
             '<desc id="desc">Synthetic three-object example. Two complete assignments cost eight doubled-center units. A and B have zero exclusion regret and abstain. C has regret thirty-two, so only C is separated under the declared cost model.</desc>',
             '<style>text{font-family:Arial,Helvetica,sans-serif;fill:#16243d}.title{font-size:42px;font-weight:700}.h{font-size:25px;font-weight:700}.p{font-size:20px}.small{font-size:16px}.mono{font-family:monospace;font-size:24px}.pill{font-size:17px;font-weight:700}</style>',
             '<rect width="1440" height="1100" fill="#f4f7fb"/>',
             '<rect x="0" y="0" width="1440" height="13" fill="#6c4ed9"/>']
    def text(x, y, value, cls="p", fill=None):
        color = ' fill="' + fill + '"' if fill else ""
        parts.append(f'<text x="{x}" y="{y}" class="{cls}"{color}>{escape(str(value))}</text>')
    def rect(x, y, w, h, fill="#ffffff", stroke="#dae3ee", radius=18):
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')
    text(56, 78, "An optimal match can still be ambiguous", "title")
    text(56, 119, "Exact assignment certificates • synthetic geometry • no identity or probability claim", "p")
    rect(48, 158, 690, 570)
    rect(758, 158, 634, 570)
    text(76, 204, "1  Two equally good complete assignments", "h")
    text(76, 238, "Connections are schematic; coordinates are written beside each object.", "small")
    text(102, 279, "BEFORE", "pill")
    text(485, 279, "AFTER", "pill")
    rows = [330, 430, 558]
    # Display the selected assignment and one equally good alternate for A/B.
    for index in range(3):
        color = "#6c4ed9" if index < 2 else "#247eaa"
        parts.append(f'<line x1="240" y1="{rows[index]}" x2="492" y2="{rows[index]}" stroke="{color}" stroke-width="4"/>')
    parts.append('<path d="M240 330 L492 430 M240 430 L492 330" stroke="#159b91" stroke-width="3" stroke-dasharray="9 7" fill="none"/>')
    before_labels = [("A", "(0, 0)"), ("B", "(2, 0)"), ("C", "(10, 0)")]
    after_labels = [("U", "(1, −1)"), ("V", "(1, 1)"), ("W", "(10, 0)")]
    for index, (left, right) in enumerate(zip(before_labels, after_labels)):
        for x, label, point in ((127, left[0], left[1]), (525, right[0], right[1])):
            fill = "#eee9ff" if index < 2 else "#e3f2fa"
            rect(x - 23, rows[index] - 25, 48, 48, fill, radius=12)
            text(x - 7, rows[index] + 8, label, "h")
            text(x - 35, rows[index] + 58, point, "small")
    text(77, 652, "Solid purple: selected optimum", "small")
    text(77, 680, "Dashed green: another optimum; both totals = 8", "small")
    text(789, 204, "2  Cost alone cannot resolve the pair", "h")
    text(789, 240, "c[i,j] = |cx2[i] − cx2[j]| + |cy2[i] − cy2[j]|", "p")
    text(789, 270, "cx2 = xmin + xmax; cy2 = ymin + ymax", "small")
    matrix_x, matrix_y = 860, 323
    text(790, matrix_y, "from / to", "small")
    for column, label in enumerate(report["after_ids"]):
        text(matrix_x + column * 130, matrix_y, label, "h")
    for row, values in enumerate(report["cost_matrix2"]):
        y = matrix_y + 56 + row * 56
        text(803, y, report["before_ids"][row], "h")
        for column, value in enumerate(values):
            if report["primary_certificate"]["columns"][row] == column:
                rect(matrix_x - 12 + column * 130, y - 30, 68, 44, "#eee9ff", radius=8)
            text(matrix_x + column * 130, y, value, "mono")
    text(789, 548, "Best total C* = " + str(report["primary_certificate"]["total_cost"]), "h")
    text(789, 586, "Best distinct-assignment gap = " + str(report["global_best_distinct_gap2"]), "p")
    text(789, 625, "Forbid one selected edge and solve again.", "p")
    text(789, 658, "Its regret is an entire-assignment cost difference.", "small")
    text(789, 688, "A low global gap does not make every edge ambiguous.", "small")
    rect(48, 750, 1344, 191)
    text(76, 794, "3  Abstain per edge, using a threshold declared in advance", "h")
    for index, edge in enumerate(report["edges"]):
        x = 80 + index * 442
        color = "#eee9ff" if edge["abstain"] else "#e3f2fa"
        rect(x - 4, 819, 415, 91, color, radius=12)
        text(x + 13, 852, edge["before_id"] + " → " + edge["after_id"] + "    regret = " + str(edge["exclusion_regret2"]), "h")
        text(x + 13, 885, "ABSTAIN: exact tie" if edge["abstain"] else "Separated under this cost model", "small")
    text(57, 982, "Every assignment within C* + threshold must retain an edge whose regret exceeds that threshold.", "p")
    text(57, 1016, "Here threshold = 0. Positive regret certifies cost robustness; physical identity still needs appearance and context.", "small")
    text(57, 1061, "Reproduce: python -B render_diagram.py --output reproduced.svg    •    Original MIT implementation, 2026-10-06", "small")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="create a new SVG file")
    args = parser.parse_args()
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(render_svg())
