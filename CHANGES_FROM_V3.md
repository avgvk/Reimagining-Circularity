# Changes from integrated prototype v3 to v4

## Approved scoring correction

Modular Architecture now uses the approved method consistently:

`MA = 0.35M + 0.25W + 0.25E + 0.15S`

The module-access subscore `M` is the arithmetic mean of the module access-depth scores:

`M = sum of module access-depth scores / number of modules assessed`

This resolves both previously documented Modular Architecture issues:
- the inherited interactive 0.30 coefficient has been changed to 0.35;
- the native implementation no longer treats the module-access average as a percentage ratio.

The preserved demonstration assessment now produces an overall score of `71.121` under the approved corrected method.

## Step 7 usability changes

- Scoring guidance is shown directly beside each assessment input.
- The optional context dialog now contains `Why · Evidence · Visual` only.
- Methodology discrepancy warnings are no longer shown to routine users.
- Critical Failure Check uses a short explanatory prompt and a clearly labelled maximum category score.
- Demonstration mode remains available and clearly states that its values are illustrative rather than derived from the uploaded motor.

## Step 8 results changes

- Summary scores now use horizontal coloured progress bars.
- All 11 category scores now use horizontal coloured progress bars similar to the protected HTML results view.
- A capped category identifies its cap beside the category label.
- The detailed numerical score table remains available under `View score table`.

## Unchanged

- A/B/C capability mapping remains 13 / 24 / 43.
- Evidence Register, Crosswalk, Assessment Criteria, Critical Failure Rules, references, figures and redesign guidance remain preserved.
- The colleague-owned CAD, classification, feature, relationship, sequence, robotic assessment and design-specific recommendation algorithms remain unchanged.
- The two recommendation layers remain separate.
