from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import streamlit as st

from .scoring import CATEGORIES

_ROOT = Path(__file__).resolve().parent
_DATA = _ROOT / "data"
_FIGURES = _ROOT / "assets" / "figures"

SUPPORT = json.loads((_DATA / "support_data.json").read_text(encoding="utf-8"))
FIGURE_CATALOG = json.loads((_DATA / "figure_catalog.json").read_text(encoding="utf-8"))
CATEGORY_VISUALS = json.loads((_DATA / "category_visuals.json").read_text(encoding="utf-8"))
REDESIGN_VISUALS = json.loads((_DATA / "redesign_visuals.json").read_text(encoding="utf-8"))

CATEGORY_BY_ID = {c["id"]: c for c in CATEGORIES}
CATEGORY_BY_NAME = {c["name"]: c for c in CATEGORIES}

_GUIDELINE_CATEGORY = {
    "Modular Architecture": "Design for Modular Architecture",
    "Fastener Removal": "Design for Fastener Removal",
    "Accessibility": "Design for Accessibility",
    "Electrical Isolation": "Design for Electrical Isolation",
    "Rotor & Magnet Recovery": "Design for Rotor and Magnet Recovery",
    "Bearing Replacement": "Design for Bearing Replacement",
    "Cooling System Disassembly": "Design for Cooling System Disassembly",
    "Robotic Disassembly": "Design for Robotic Disassembly",
    "Material Separation": "Design for Material Separation",
    "Inspection": "Design for Inspection",
    "Traceability": "Design for Traceability",
}

_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "before", "after", "existing", "current",
    "number", "count", "condition", "component", "components", "motor", "design", "assessment",
    "required", "total", "target", "targets", "existing", "use", "using", "select", "score",
}


def evidence_counts() -> Dict[str, int]:
    return {
        "ev_guidelines": len(SUPPORT.get("evGuidelines", [])),
        "dfd_guidelines": len(SUPPORT.get("disassemblyGuidelines", [])),
        "circularity_guidelines": len(SUPPORT.get("circularityGuidelines", [])),
        "crosswalk": len(SUPPORT.get("crosswalk", [])),
        "evidence_register": len(SUPPORT.get("evidenceRegister", [])),
        "references": len(SUPPORT.get("references", [])),
        "assessment_criteria": len(SUPPORT.get("assessmentCriteria", [])),
        "critical_rules": len(SUPPORT.get("criticalRules", [])),
        "figures": len(FIGURE_CATALOG),
    }


def _refs(text: Any) -> List[int]:
    return [int(x) for x in re.findall(r"\[(\d+)\]", str(text or ""))]


def _tokens(*parts: Any) -> set[str]:
    text = " ".join(str(x or "") for x in parts).lower()
    toks = set(re.findall(r"[a-z0-9]+", text))
    return {t for t in toks if len(t) > 2 and t not in _STOPWORDS}


def _category_refs(cat: Dict[str, Any]) -> List[int]:
    return _refs(cat.get("evidence", ""))


def _rank_rows(rows: Iterable[Dict[str, Any]], query_tokens: set[str], fields: Iterable[str]) -> List[Dict[str, Any]]:
    scored = []
    for idx, row in enumerate(rows):
        text_tokens = _tokens(*(row.get(f, "") for f in fields))
        score = len(query_tokens & text_tokens)
        scored.append((score, -idx, row))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [x[2] for x in scored]


def relevant_evidence(cat: Dict[str, Any], q: Optional[Dict[str, Any]] = None, limit: int = 6) -> List[Dict[str, Any]]:
    rows = SUPPORT.get("evidenceRegister", [])
    refs = set(_category_refs(cat))
    if refs:
        filtered = [r for r in rows if int(r.get("Ref No.") or -1) in refs]
    else:
        filtered = []
    if not filtered:
        return []
    qt = _tokens(q.get("l") if q else "", q.get("h") if q else "", cat.get("name"))
    ranked = _rank_rows(
        filtered,
        qt,
        ["Evaluation area", "Design feature", "Design condition / state", "Potential evaluator input", "Potential evaluation output affected"],
    )
    # If lexical ranking is weak, the category evidence set is still the authoritative support set.
    return ranked[:limit]


def relevant_crosswalk(cat: Dict[str, Any], q: Optional[Dict[str, Any]] = None, limit: int = 5) -> List[Dict[str, Any]]:
    name = cat.get("name", "")
    rows = []
    for row in SUPPORT.get("crosswalk", []):
        model_cat = str(row.get("Most relevant existing model category", ""))
        if name in model_cat or (name == "Rotor & Magnet Recovery" and "Rotor & Magnet Recovery" in model_cat):
            rows.append(row)
    qt = _tokens(q.get("l") if q else "", q.get("h") if q else "", name)
    ranked = _rank_rows(rows, qt, ["Candidate evaluator input", "Evaluation area", "What literature says it affects"])
    return ranked[:limit]


def _figures_for(cat_id: str, mode: str = "assessment") -> List[Dict[str, Any]]:
    mapping = REDESIGN_VISUALS if mode == "redesign" else CATEGORY_VISUALS
    rows = set(mapping.get(cat_id, []))
    return [f for f in FIGURE_CATALOG if int(f.get("row") or -1) in rows]


def _show_figure(fig: Dict[str, Any], key_suffix: str = "") -> None:
    path = _FIGURES / str(fig.get("file"))
    if path.exists():
        st.image(str(path), use_container_width=True)
    st.markdown(f"**{fig.get('paper','')} · {fig.get('figure','')}**")
    st.caption(str(fig.get("design", "")))
    if fig.get("why"):
        st.write(str(fig["why"]))
    if fig.get("ref"):
        st.caption(f"Evidence reference: {fig['ref']} · Priority: {fig.get('priority','')}")


@st.dialog("Assessment context", width="large")
def _question_context_dialog(cat: Dict[str, Any], q: Dict[str, Any], adapter_row: Dict[str, Any]) -> None:
    st.markdown(f"### {q.get('c','')} · {q.get('l','')}")
    why_tab, ev_tab, vis_tab = st.tabs(["Why", "Evidence", "Visual"])
    with why_tab:
        st.write(q.get("h", ""))
        if adapter_row.get("human_role"):
            st.write("**Human role:**", adapter_row.get("human_role"))
        if adapter_row.get("limitation"):
            st.caption(f"Limitation: {adapter_row.get('limitation')}")

    with ev_tab:
        evidence_label = str(cat.get("evidence") or "")
        if "gap" in evidence_label.lower():
            st.warning("The focused EV-motor evidence review did not specifically validate this category. The criterion is retained as part of the wider evaluation framework.")
        else:
            st.caption(f"Category evidence set: {evidence_label}")
        rows = relevant_evidence(cat, q, limit=6)
        if rows:
            df = pd.DataFrame(rows)
            cols = [
                "ID", "Paper", "Evaluation area", "Design feature", "Design condition / state",
                "Evidence-backed effect on disassemblability or recoverability", "Priority",
                "Scope / limitation", "Source location", "Source URL",
            ]
            show = df[[c for c in cols if c in df.columns]]
            cfg = {"Source URL": st.column_config.LinkColumn("Source URL")} if "Source URL" in show.columns else None
            st.dataframe(show, use_container_width=True, hide_index=True, column_config=cfg)
        else:
            st.info("No category-specific entries from the focused EV-motor evidence register are linked here. This is an evidence gap, not evidence that the factor is unimportant.")
        cross = relevant_crosswalk(cat, q, limit=4)
        if cross:
            st.markdown("**Evidence-to-model crosswalk**")
            cdf = pd.DataFrame(cross)
            cols = ["Candidate evaluator input", "What literature says it affects", "Evidence refs", "Evidence status", "Important caution", "Recommended use in this scoring model"]
            st.dataframe(cdf[[c for c in cols if c in cdf.columns]], use_container_width=True, hide_index=True)


    with vis_tab:
        figs = _figures_for(cat.get("id", ""), mode="assessment")
        if not figs:
            st.info("No literature figure is linked to this category in the preserved visual-evidence map.")
        else:
            st.caption("Literature figures provide design/process context. They do not independently determine the score.")
            cols = st.columns(2)
            for i, fig in enumerate(figs):
                with cols[i % 2]:
                    _show_figure(fig, key_suffix=f"{cat.get('id')}_{q.get('k')}_{i}")


def render_question_context(cat: Dict[str, Any], q: Dict[str, Any], adapter_row: Dict[str, Any]) -> None:
    """Open the preserved question context on demand so the 80-input page stays light."""
    if st.button("Why · Evidence · Visual", key=f"context_{cat.get('id')}_{q.get('k')}"):
        _question_context_dialog(cat, q, adapter_row)


def _contains(row: Dict[str, Any], query: str) -> bool:
    if not query:
        return True
    q = query.lower().strip()
    return q in " ".join(str(v or "") for v in row.values()).lower()


def render_evidence_library(default_category: Optional[str] = None, key_prefix: str = "evidence") -> None:
    counts = evidence_counts()
    st.markdown("### Evidence & Audit")
    st.caption(
        f"Preserved from the original evaluator: {counts['evidence_register']} evidence-register entries, "
        f"{counts['crosswalk']} crosswalk rows, {counts['assessment_criteria']} assessment criteria, "
        f"{counts['critical_rules']} critical-rule rows, {counts['references']} references and {counts['figures']} literature figures."
    )
    with st.expander("Open full evidence library", expanded=False):
        tabs = st.tabs(["Visual Evidence", "Evidence Register", "Crosswalk", "Assessment Criteria", "Critical Failure Rules", "References", "Methodology"])

        with tabs[0]:
            opts = [c["id"] for c in CATEGORIES]
            names = {c["id"]: c["name"] for c in CATEGORIES}
            default_id = default_category if default_category in opts else opts[0]
            idx = opts.index(default_id)
            cat_id = st.selectbox("Category", opts, index=idx, format_func=lambda x: names[x], key=f"{key_prefix}_visual_cat")
            figs = _figures_for(cat_id, "assessment")
            if figs:
                cols = st.columns(2)
                for i, fig in enumerate(figs):
                    with cols[i % 2]:
                        _show_figure(fig, key_suffix=f"library_{i}")
            else:
                st.info("No linked visual evidence for this category.")

        with tabs[1]:
            rows = SUPPORT.get("evidenceRegister", [])
            search = st.text_input("Search evidence, design features, conditions or papers", key=f"{key_prefix}_register_search")
            priorities = sorted({str(r.get("Priority")) for r in rows if r.get("Priority")})
            p = st.selectbox("Priority", ["All"] + priorities, key=f"{key_prefix}_register_priority")
            areas = sorted({str(r.get("Evaluation area")) for r in rows if r.get("Evaluation area")})
            area = st.selectbox("Evaluation area", ["All"] + areas, key=f"{key_prefix}_register_area")
            filtered = [r for r in rows if _contains(r, search) and (p == "All" or str(r.get("Priority")) == p) and (area == "All" or str(r.get("Evaluation area")) == area)]
            st.caption(f"Showing {len(filtered)} of {len(rows)} entries")
            df = pd.DataFrame(filtered)
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)

        with tabs[2]:
            rows = SUPPORT.get("crosswalk", [])
            search = st.text_input("Search crosswalk", key=f"{key_prefix}_cross_search")
            filtered = [r for r in rows if _contains(r, search)]
            st.caption(f"Showing {len(filtered)} of {len(rows)} rows")
            if filtered:
                st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)

        with tabs[3]:
            rows = SUPPORT.get("assessmentCriteria", [])
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        with tabs[4]:
            rows = SUPPORT.get("criticalRules", [])
            cats = sorted({str(r.get("category")) for r in rows if r.get("category")})
            cat = st.selectbox("Critical-rule category", ["All"] + cats, key=f"{key_prefix}_critical_cat")
            search = st.text_input("Search critical rules", key=f"{key_prefix}_critical_search")
            filtered = [r for r in rows if (cat == "All" or str(r.get("category")) == cat) and _contains(r, search)]
            st.caption(f"Showing {len(filtered)} of {len(rows)} rule rows")
            if filtered:
                st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)

        with tabs[5]:
            rows = SUPPORT.get("references", [])
            search = st.text_input("Search references by number, title, author or key point", key=f"{key_prefix}_refs_search")
            filtered = [r for r in rows if _contains(r, search)]
            st.caption("References 1–15 are the original general DfD/circularity sources. References 16–41 are the EV-motor-focused evidence base.")
            if filtered:
                st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)

        with tabs[6]:
            st.markdown("**Human-in-the-loop principle**")
            st.write("AI may suggest values or conditions from CAD, BOM and product data. The human confirms those inputs. The score is then calculated deterministically from the current model.")
            st.markdown("**Evidence status**")
            st.write("Evidence references support why a factor matters. Unless a source directly establishes a threshold, the exact numerical score bands and caps remain model-defined rather than universal empirical laws.")
            st.markdown("**Focused evidence scope**")
            st.write("Permanent-magnet EV motor recoverability, with strongest coverage of rotor and magnet recovery. This complements the wider evaluation framework.")
            st.markdown("**Current scoring model**")
            st.write("The assessment uses the current approved category equations. Literature evidence supports why factors matter; exact numerical bands remain part of the evaluation model unless directly established by a source.")


def _guidelines_for_category(category_name: str) -> List[Dict[str, Any]]:
    target = _GUIDELINE_CATEGORY.get(category_name)
    if not target:
        return []
    return [x for x in SUPPORT.get("evGuidelines", []) if x.get("category") == target]


def render_redesign_guidance(result: Optional[Dict[str, Any]], snapshot: Optional[Dict[str, Any]], key_prefix: str = "redesign") -> None:
    st.markdown("### Literature-backed redesign guidance")
    st.caption("These preserved guidelines support redesign after evaluation. They do not alter the assessment score and do not replace design-specific CAD evidence.")
    if snapshot and snapshot.get("demo_mode"):
        st.info("Demonstration assessment active: the focus areas below are illustrative. The design-specific recommendations above remain based on the uploaded motor.")

    focus: List[str] = []
    if result:
        # Confirmed critical conditions first, then the relatively lowest completed categories.
        for r in result.get("categories", []):
            if r.get("critical") not in (None, "", "none") and r.get("name") not in focus:
                focus.append(r.get("name"))
        completed = [r for r in result.get("categories", []) if r.get("final") is not None]
        for r in sorted(completed, key=lambda x: x.get("final"))[:3]:
            if r.get("name") not in focus:
                focus.append(r.get("name"))
    focus = focus[:4]

    if focus:
        st.write("**Suggested focus areas from the confirmed assessment:** " + "; ".join(focus))
        for category_name in focus:
            cat = CATEGORY_BY_NAME.get(category_name)
            if not cat:
                continue
            with st.expander(category_name, expanded=(category_name == focus[0])):
                gl = _guidelines_for_category(category_name)
                if gl:
                    df = pd.DataFrame(gl)
                    cols = ["guideline", "benefit", "refs", "evidence_status", "interpretation"]
                    st.dataframe(df[[c for c in cols if c in df.columns]], use_container_width=True, hide_index=True)
                else:
                    st.info("No EV-specific redesign guideline is mapped to this category in the preserved library.")
                figs = _figures_for(cat.get("id"), "redesign")
                if figs:
                    st.markdown("**Relevant visual evidence**")
                    c1, c2 = st.columns(2)
                    for i, fig in enumerate(figs[:4]):
                        with (c1 if i % 2 == 0 else c2):
                            _show_figure(fig, key_suffix=f"redesign_{cat.get('id')}_{i}")
    else:
        st.info("Complete the circularity assessment to generate focus areas. The full guideline library remains available below.")

    with st.expander("Browse complete redesign guideline library", expanded=False):
        library = st.radio("Guideline library", ["EV motor guidelines", "General DfD guidelines", "Circularity guidelines"], horizontal=True, key=f"{key_prefix}_library")
        search = st.text_input("Search redesign guidelines", key=f"{key_prefix}_search")
        if library == "EV motor guidelines":
            rows = SUPPORT.get("evGuidelines", [])
        elif library == "General DfD guidelines":
            rows = SUPPORT.get("disassemblyGuidelines", [])
        else:
            rows = SUPPORT.get("circularityGuidelines", [])
        filtered = [r for r in rows if _contains(r, search)]
        st.caption(f"Showing {len(filtered)} of {len(rows)} guidelines")
        if filtered:
            st.dataframe(pd.DataFrame(filtered), use_container_width=True, hide_index=True)
