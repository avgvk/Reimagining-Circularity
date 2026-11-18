# D2N+ Integrated Prototype v3

## Purpose

This prototype continues the protected v2 integration and adds the full evidence/recommendation support layer from the original circularity evaluator into the merged Streamlit workflow.

The colleague-owned CAD/disassembly modules remain unchanged. The protected `circularity_evaluator.html` remains unchanged and is retained as the scoring/content reference baseline.

## Current 11-step workflow

1. STEP Visualisation
2. Components
3. Disassembly Features
4. Relationship Matrix
5. Sequence
6. Interactive Sequence
7. Circularity Assessment
8. Circularity Results & Diagnosis
9. Robotic Assessment
10. Improvement Suggestions
11. Export & Audit

## What v3 adds

### Step 7: question-level evidence access

Each assessment input now includes an on-demand **Why · Evidence · Visual** button.

Opening it shows:
- the preserved question explanation;
- relevant rows from the EV Evidence Register;
- the Evidence Crosswalk context;
- the current category formula and selectable score bands where applicable;
- the literature figures linked to that assessment category.

The context opens only when requested so the 80-input page does not render all evidence and figures on every Streamlit rerun.

### Step 8: full Evidence & Audit library

The native Results & Diagnosis stage now exposes the preserved library:
- Visual Evidence;
- Evidence Register;
- Evidence Crosswalk;
- Assessment Criteria;
- Critical Failure Rules;
- References;
- Methodology/evidence-scope notes.

Search and filtering are available for the larger tables.

### Step 10: literature-backed redesign guidance

The original redesign guideline libraries are now accessible beside the design-specific recommendation stage.

If a circularity assessment exists, the interface identifies up to four focus categories from:
1. confirmed critical conditions; then
2. the relatively lowest completed category scores.

For those focus areas it shows the preserved EV-motor redesign guidelines, benefits, evidence references, evidence status, interpretation notes and relevant literature figures.

This guidance does **not** alter the colleague-owned recommendation generator yet. It supports the recommendation stage while preserving the rule that a specific physical recommendation requires design-specific evidence or explicit human-confirmed information.

## Evidence resources preserved from the original HTML

The structured evidence resources and images are extracted directly from the protected `circularity_evaluator.html` into native files:

- 101 EV Evidence Register entries
- 40 Evidence Crosswalk rows
- 41 references
- 19 Assessment Criteria rows
- 115 Critical Failure reference rows
- 69 EV-motor redesign guidelines
- 29 general DfD guidelines
- 59 circularity guidelines
- 35 literature figures

See:
`circularity/data/EVIDENCE_MIGRATION_MANIFEST.json`

The manifest records the source HTML SHA256 and extracted figure hashes for preservation/audit purposes.

## A/B/C integration state

Current capability mapping:
- A capable: 13
- B: 24
- C: 43

A remains a human-confirmed preliminary suggestion. If its required evidence is absent, the adapter does not invent a value.

## Demonstration mode

`Load demonstration assessment` remains intentionally available in Step 7.

It loads the preserved completed example so the full workflow can be demonstrated or recorded without manually completing all 80 inputs. The interface explicitly states that these values are illustrative and are not derived from the uploaded STEP model.

## Approved scoring method

Modular Architecture now uses the approved method consistently:

`MA = 0.35M + 0.25W + 0.25E + 0.15S`

The module-access subscore is the arithmetic mean of the module access-depth scores. The previous inherited 0.30 coefficient and percentage-helper error are resolved.

The preserved demonstration assessment now produces an overall score of:
`71.121`

The corrected workbook reference is `Design_for_Disassembly_Guidelines_EV_evidence_augmented_v7.xlsx`.

## Files changed relative to v2

Existing integration file changed:
- `circularity/evaluator.py` only

New files:
- `circularity/evidence.py`
- `circularity/data/support_data.json`
- `circularity/data/figure_catalog.json`
- `circularity/data/category_visuals.json`
- `circularity/data/redesign_visuals.json`
- `circularity/data/EVIDENCE_MIGRATION_MANIFEST.json`
- `circularity/assets/figures/*` (35 files)

Verification/readme files are also updated.

No additional changes are made to:
- `app.py`
- `assessment.py`
- `cad_engine.py`
- `classifier.py`
- `disassembly.py`
- `feature_engine.py`
- `llm_reasoner.py`
- `viewer.py`
- `circularity/scoring.py`
- `circularity/integration.py`
- `circularity_evaluator.html`

## Deployment

The current Streamlit Community Cloud configuration remains:
- Python 3.12
- entry point `app.py`
- `packages.txt` containing `libgl1` and `libxrender1`

No API key is required to test the geometry and circularity integration. The colleague can restore the existing OpenAI API configuration later; the circularity adapter consumes final upstream outputs when available rather than implementing a separate LLM system.

## Verification

Run:

`python verify_core.py`

Expected checks include:
- 11 categories
- 80 inputs
- 13 / 24 / 43 A/B/C capability map
- ELLI rotor access suggestion `>5`
- approved corrected demonstration score `71.121`
- complete evidence/guideline/figure counts
