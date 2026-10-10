# Second row of the M2 recipe: Version 17 scored 30.65 (2026-10-10)

## Result

**Public Version 17 scored 30.65** on the public leaderboard (about half of the hidden games). It is the second draw of Daniel Franzen's Milestone 2 recipe (his Version 1).
- **What differs from Version 16:** Version 17 adds input checks with fallbacks (none triggered), an MIT copy of the source bundle (byte-identical), startup and teardown checks, and a logging-only timing log. Its interactive run showed no behaviour change (see `2026-10-08-v17/`).
- **Against the unchanged-copy distribution** (25.77 ± 3.93, public forum figures): z = +1.24, about the 89th percentile.
- **Against Version 16 (27.83):** the difference is +2.82. The SD of a difference between two single rows is about 5.6, so the gap is noise. Version 17 changed nothing that reaches the model.
- **Placement:** rank 200 on the public board is about 30.7, so 30.65 sits near it.

## Two draws, one configuration

Versions 16 and 17 run the same serving stack and the same harness, so their rows are two draws of one configuration.

| Draw | Public leaderboard | z vs unchanged copies |
|---|---|---|
| Version 16 | 27.83 | +0.52 |
| Version 17 | 30.65 | +1.24 |
| Mean of 2 | **29.24** | +1.25 (SE of a 2-row mean about 2.78) |

The two-row mean is higher than the copy average, but not by more than two standard errors. It does not show that our copy is better than other unchanged copies.

## Selection rule (unchanged)

- Configurations are compared by their mean over rows. One configuration counts as better only if its mean beats the other's by max(4, 2·SD·√(2/n)) points: 7.9 at 2 rows each, 6.4 at 3.
- Rows of the same configuration are pooled, not picked. Taking the higher of two draws as "the" score would overstate the configuration by about the expected maximum of two noisy rows.
- **Version 18 is bookkeeping only.** It records the Version 16 row in the introduction; its code and settings are Version 17's. Its row will be a third draw of this configuration.

## Next

- The speculative-steps bench (steps 4 against steps 3) runs after the weekly quota reset, with the gate registered in `2026-10-09-plan/`.
- A steps change reaches the leaderboard only through a new version after that gate passes. It would then be compared with this configuration by the rule above.
