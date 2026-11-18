# Changes from integrated prototype v2 to v3

## Existing files modified

### `circularity/evaluator.py`
- Step 7 now opens preserved Why / Evidence / Scoring / Visual context on demand for each question.
- Step 8 now exposes the full Evidence & Audit library.
- Step 10 now exposes literature-backed redesign guidance alongside the existing recommendation stage.
- Prototype audit version updated to `prototype-4-integrated` for new assessment states.

### `verify_core.py`
- Adds evidence/guideline/figure preservation checks.

### `INTEGRATION_README.md`
- Updated for v3 behaviour and deployment/testing.

## New files

- `circularity/evidence.py`
- `circularity/data/support_data.json`
- `circularity/data/figure_catalog.json`
- `circularity/data/category_visuals.json`
- `circularity/data/redesign_visuals.json`
- `circularity/data/EVIDENCE_MIGRATION_MANIFEST.json`
- `circularity/assets/figures/` containing 35 extracted literature figures
- `D2N_CURRENT_STATE_CHECKPOINT_2026-11-16.md`

## Explicitly unchanged from v2

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

The colleague-owned recommendation generator is unchanged. v3 makes the preserved redesign guidance accessible beside it but does not yet feed literature guidance into the deterministic recommendation rules.
