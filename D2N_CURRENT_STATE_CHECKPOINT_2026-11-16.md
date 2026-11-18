# D2N+ current state checkpoint
**Date:** 16 November 2026

## Current prototype
`D2N_integrated_prototype_v4`

## Verified platform state
- Streamlit Community Cloud deployment works with Python 3.12.
- Linux packages required: `libgl1`, `libxrender1`.
- ELLI STEP processes successfully.
- Step 7 A/B/C integration works.
- Current A/B/C capability map: 13 A-capable, 24 B, 43 C.
- ELLI rotor access suggestion is `>5` when G20 is identified as rotor_core.
- Step 8 Results & Diagnosis works.
- Evidence and redesign resources are accessible in the merged interface.

## Approved Modular Architecture scoring method
The user approved the following method as the current methodology:

`MA = 0.35M + 0.25W + 0.25E + 0.15S`

where `M` is the arithmetic mean of the module access-depth scores:

`M = sum of module access-depth scores / number of modules assessed`

This replaces the previous inherited 0.30 implementation and fixes the earlier native percentage-helper error.

The preserved demonstration assessment now produces:
- Overall: 71.121
- DfD: 74.954 approximately
- Circularity: 71.013 approximately
- Robotic: 61.75
- Modular Architecture: 69.625

The corrected reference workbook is:
`Design_for_Disassembly_Guidelines_EV_evidence_augmented_v7.xlsx`

## Step 7 usability decisions
- Keep `Load demonstration assessment` for presentations and video recording.
- Demonstration values are explicitly illustrative and are not derived from the uploaded STEP model.
- Keep A/B/C evidence logic.
- Show scoring/assessment guidance directly beside the question so the assessor does not need to open another panel before answering.
- Optional question context is `Why · Evidence · Visual`.
- Do not show methodology discrepancy warnings to routine users.
- Critical Failure Check should remain simple: one-line explanation, condition selection, and clearly labelled maximum category score.
- A-capable inputs can generate suggestions only when prerequisite evidence exists. Missing prerequisites do not become zeros or guesses.
- Step 7 may allow direct target selection for bearing, cooling, accessibility or inspection questions without forcing the user back to Step 2.

## Step 8 results decisions
Step 8 now restores the visual score bars from the original HTML concept:
- horizontal coloured bars for Overall, DfD, Circularity and Robotic scores;
- horizontal coloured bars for all 11 category scores;
- cap shown in the label where applicable;
- detailed score table retained in a collapsible section.

## Evidence and redesign resources preserved
- 101 Evidence Register entries
- 40 Crosswalk rows
- 19 Assessment Criteria rows
- 115 Critical Failure reference rows
- 41 references
- 35 literature figures
- 69 EV motor guidelines
- 29 general DfD guidelines
- 59 circularity guidelines

## Recommendation architecture
Keep the two recommendation layers separate for this prototype:

1. Design-specific recommendations from the colleague-owned platform, based on the uploaded motor's CAD, features, relationships, sequence and robotic evidence. The colleague can restore/develop the existing API/LLM layer later.
2. Literature-backed redesign guidance from the circularity evidence base and assessment.

Do not merge the two recommendation engines in this version.

## LLM/API position
Do not build a new LLM layer in Step 7. The circularity adapter consumes the existing platform's final upstream outputs when available. The colleague can restore the API key later. Geometry and human-correction workflows continue to work without the key.

## Protected baseline principle
Do not destructively rewrite colleague-owned algorithms. Preserve provenance and regression tests. Missing information remains explicitly unavailable rather than becoming zero.
