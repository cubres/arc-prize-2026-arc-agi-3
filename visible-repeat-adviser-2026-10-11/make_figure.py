"""Render an original SVG from the published aggregate counters only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / "PUBLIC_RESULTS.json").read_text())
c = data["counts"]


def txt(x, y, text, size=20, colour="#dce7f5", weight=400):
    from html import escape
    return f'<text x="{x}" y="{y}" font-family="system-ui,sans-serif" font-size="{size}" fill="{colour}" font-weight="{weight}">{escape(text)}</text>'


parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="760" viewBox="0 0 1280 760" role="img" aria-labelledby="title desc">',
         '<title id="title">Unchanged visible frames are not permanent no-op proofs</title>',
         '<desc id="desc">Historical native V2 snapshot audit. Of 254 same-visible-key revisits following an unchanged observation, 135 changed next frame. Level 2 or higher: 41 of 66. No policy or score effect is inferred.</desc>',
         '<rect width="1280" height="760" fill="#101b2b"/>',
         txt(50, 66, "UNCHANGED ≠ USELESS", 34, "#f5bd71", 700),
         txt(50, 103, "Visible-state evidence for an advisory that always permits execution", 23),
         txt(50, 141, "Historical native V2 · 25 public-game streams · 4,940 recorded actions", 17, "#9eadc2")]

for x, headline, caption in ((50, str(c["eligible_same_level_nonterminal_transitions"]), "same-level nonterminal transitions"),
                             (440, str(c["unchanged_final_visible_frame"]), "unchanged final visible frames"),
                             (830, str(c["crop4_same_but_full_frame_changed"]), "crop-4 equal / full frame changed")):
    parts += [f'<rect x="{x}" y="176" width="355" height="110" rx="14" fill="#1d2c40"/>',
              txt(x+20, 223, headline, 36, "#f3f7fd", 700),
              txt(x+20, 258, caption, 16, "#a8bdd4")]

for y, totalkey, changedkey, label in ((350, "revisited_after_previous_unchanged", "changed_after_previous_unchanged", "All levels"),
                                      (470, "level2plus_revisited_after_unchanged", "level2plus_changed_after_unchanged", "Level 2+")):
    n, k = c[totalkey], c[changedkey]
    parts += [txt(50, y, label, 20, "#f3f7fd", 600),
              txt(270, y, f"{k} of {n} repeated visible keys changed next frame", 22),
              f'<rect x="270" y="{y+22}" width="750" height="23" rx="6" fill="#24384f"/>',
              f'<rect x="270" y="{y+22}" width="{750*k/n:.2f}" height="23" rx="6" fill="#f5bd71"/>',
              txt(1040, y+41, f"{100*k/n:.1f}%", 20, "#f5bd71", 600)]

parts += [txt(50, 595, "Same key = same attempt, level, whole visible frame and action (including coordinates).", 18, "#a8bdd4"),
          txt(50, 627, "Final-frame snapshots only; complete animation evidence unavailable. Native readiness: HOLD.", 18, "#a8bdd4"),
          txt(50, 675, "These are descriptive record counts, not measured false blocks, saved actions or score gains.", 18, "#f5bd71"),
          txt(50, 713, "Original tool: warn briefly after qualified evidence; keep every deliberate repeat executable.", 18),
          '</svg>']

# Rendering only updates this original figure in place. No notebook artifact is touched.
(ROOT / "visible-repeat-audit.svg").write_text("\n".join(parts) + "\n")
