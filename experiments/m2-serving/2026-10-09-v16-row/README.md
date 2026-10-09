# First leaderboard row of the M2 recipe: Version 16 scored 27.83 (2026-10-09)

## Result

**Public Version 16 scored 27.83** on the public leaderboard (about half of the hidden games). It is the credited rerun of Daniel Franzen's Milestone 2 recipe (his Version 1), with settings unchanged.

- This notebook's previous best was 2.95.
- **Against the unchanged-copy distribution:** one-shot leaderboard rows of unchanged copies of this recipe average 25.77 with SD 3.93 (median 26.19, range about 20–34; public forum figures). 27.83 is z = +0.52, about the 70th percentile of that distribution.
- **Against Franzen's own row:** his row is 27.89, and reruns of the unchanged notebook have been reported at 27–28. Our row is within 0.06 of his.
- **Verdict:** the rebase reproduced the recipe. The row is an ordinary draw, not evidence of any change of ours.
- **Placement:** a row of 27.83 sits around rank 250–300 on the public board as read on 2026-10-09; rank 200 was 30.73.

## Submissions

- **Version 17**, submitted on 2026-10-09, is the second draw of the same recipe. It adds a robustness pack:
  - input checks with fallbacks, none of which triggered;
  - an MIT copy of the source bundle, byte-identical to the earlier one;
  - startup and teardown checks;
  - a logging-only timing log.

  Its interactive run showed no behaviour change (see `2026-10-08-v17/`). Its row is pending.
- **Version 18** only records rows in the notebook's introduction. Its code and settings are Version 17's.

## Decisions

1. **Treat every row as one draw.** One row's SD is about 3.9, so a single row cannot show a change of a few points.
2. **Variance-aware selection.** Rows from Versions 16, 17 and 19 (the instrumentation candidate, all switches off by default) are draws of one recipe.
   - Final selection compares configurations by their mean over rows.
   - A configuration counts as better only if its mean beats the other's by max(4, 2·SD·√(2/n)) points: 6.4 at 3 rows each and 7.9 at 2.
3. **Speculative-steps bench after the weekly quota reset (2026-10-10).** Steps 4 against steps 3, with the pre-registered gate in `2026-10-09-plan/`. A steps change reaches the leaderboard only through a new version after that gate passes.
4. **Not pursued:** closing tool-gap idle time. It is worth about +0.04 points, as measured in `2026-10-08-v17/`.
