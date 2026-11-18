from __future__ import annotations
import json
import hashlib
from pathlib import Path
from typing import Any, Dict, Iterable, Optional
import pandas as pd
import numpy as np

_MAP = Path(__file__).resolve().parent / "data" / "integration_map.json"
MAPPING = json.loads(_MAP.read_text(encoding="utf-8"))


def _df(x):
    if x is None:
        return pd.DataFrame()
    if isinstance(x, pd.DataFrame):
        return x.copy()
    if isinstance(x, list):
        return pd.DataFrame(x)
    return pd.DataFrame()


def _safe_list(v):
    if isinstance(v, (list, tuple, set)):
        return list(v)
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return []
    return []


def _component_source(row) -> str:
    user = row.get("user_label")
    if isinstance(user, str) and user.strip():
        return "human correction"
    source = str(row.get("label_source") or "").lower()
    if "openai" in source or "api" in source:
        return "LLM interpretation"
    return "geometry/algorithm"


def _rotor_access_band(n_preceding: int) -> str:
    if n_preceding <= 1: return "0–1"
    if n_preceding == 2: return "2"
    if n_preceding == 3: return "3"
    if n_preceding == 4: return "4"
    if n_preceding == 5: return "5"
    return ">5"

def _access_depth_band(n_preceding: int) -> str:
    if n_preceding <= 0: return "0"
    if n_preceding == 1: return "1"
    if n_preceding == 2: return "2"
    if n_preceding == 3: return "3"
    if n_preceding == 4: return "4"
    return "5+"

def _bearing_access_band(n_preceding: int) -> str:
    if n_preceding <= 0: return "0"
    if n_preceding == 1: return "1"
    if n_preceding <= 3: return "2–3"
    if n_preceding <= 5: return "4–5"
    return ">5"

def _mag_access_band(n_ops: int) -> str:
    if n_ops <= 0: return "0"
    if n_ops == 1: return "1"
    if n_ops <= 3: return "2–3"
    if n_ops <= 5: return "4–5"
    return ">5"

def _inspection_band(n_preceding: int) -> str:
    if n_preceding <= 0: return "No disassembly required"
    if n_preceding == 1: return "1 minor component removed"
    if n_preceding <= 3: return "2–3 components removed"
    return "Major module removal required"

def _cooling_inspection_band(n_preceding: int) -> str:
    if n_preceding <= 0: return "Inspectable/testable without motor disassembly"
    if n_preceding == 1: return "One minor cover/component removed"
    if n_preceding <= 3: return "2–3 components removed"
    return "Major module dismantling required"

def _sequence_simplicity(seq: pd.DataFrame):
    if seq.empty:
        return None, 0
    ordered=seq.sort_values("final_step") if "final_step" in seq.columns else seq
    pairs=[]
    for _,r in ordered.iterrows():
        pairs.append((str(r.get("tool") or "unknown"), str(r.get("final_direction") or "unknown")))
    transitions=sum(a!=b for a,b in zip(pairs,pairs[1:]))
    if transitions == 0: return "Simple sequence, one tool/orientation", transitions
    if transitions == 1: return "1 tool change or reorientation", transitions
    if transitions == 2: return "2 changes/reorientations", transitions
    if transitions <= 4: return "3–4 changes/reorientations", transitions
    return "Highly complex/manual intervention required", transitions


def _direction_changes(seq: pd.DataFrame) -> int:
    if seq.empty or "final_direction" not in seq.columns:
        return 0
    vals=seq.sort_values("final_step")["final_direction"].astype(str).tolist()
    return sum(a != b for a,b in zip(vals, vals[1:]))


def _relationship_summary(rel: pd.DataFrame) -> str:
    if rel.empty:
        return "No relationship matrix is available."
    col="final_interface_type" if "final_interface_type" in rel.columns else "interface_type"
    counts=rel[col].fillna("unknown").astype(str).value_counts().head(5)
    return "; ".join(f"{k}: {int(v)}" for k,v in counts.items())


def _clearance_summary(rel: pd.DataFrame) -> str:
    if rel.empty or "radial_clearance_estimate" not in rel.columns:
        return "No radial-clearance proxy is available."
    vals=pd.to_numeric(rel["radial_clearance_estimate"], errors="coerce").dropna()
    if vals.empty:
        return "No finite radial-clearance proxy is available."
    return f"{len(vals)} relationship(s) have a geometric radial-clearance proxy; range {vals.min():.4g} to {vals.max():.4g} STEP units. A required tool envelope is still needed before a clearance ratio can be calculated."


def build_evidence_adapter(groups=None, features=None, relationships=None, sequence=None, assessment=None, target_selections=None) -> pd.DataFrame:
    """Return one inspectable row for every existing Step 7 input.

    The adapter is deliberately conservative. Only Class A may produce a direct
    evaluator suggestion. Class B exposes evidence/candidate values without
    making them authoritative. Class C explicitly records the information gap.
    """
    g=_df(groups); f=_df(features); rel=_df(relationships); seq=_df(sequence); ass=_df(assessment)
    target_selections = target_selections or {}
    if not seq.empty and "final_step" in seq.columns:
        seq=seq.sort_values("final_step").reset_index(drop=True)

    comp_by_label={}
    if not g.empty and "final_component" in g.columns:
        for _,r in g.iterrows():
            comp_by_label.setdefault(str(r.get("final_component","unknown")), []).append(r)

    # Useful global evidence summaries.
    seq_n=len(seq)
    zero_blockers=None
    if not seq.empty and "blocker_group_ids" in seq.columns:
        zero_blockers=int(seq["blocker_group_ids"].apply(lambda x: len(_safe_list(x))==0).sum())
    tool_counts=seq["tool"].fillna("unknown").astype(str).value_counts().to_dict() if not seq.empty and "tool" in seq.columns else {}
    direction_changes=_direction_changes(seq)
    rel_summary=_relationship_summary(rel)
    clear_summary=_clearance_summary(rel)

    handling_groups=[]
    if not f.empty and "group_id" in f.columns:
        fc="final_function_class" if "final_function_class" in f.columns else "function_class"
        if fc in f.columns:
            mask=f[fc].astype(str).str.contains("handling", case=False, na=False)
            handling_groups=sorted(pd.to_numeric(f.loc[mask,"group_id"], errors="coerce").dropna().astype(int).unique().tolist())

    rows=[]
    for m in MAPPING:
        key=m.get("Input key")
        cls=m.get("Class")
        source_type="human/external information" if cls=="C" else "mixed upstream evidence"
        source_confidence=None
        evidence=""
        source_ids: Dict[str, Any]={}
        candidate=None
        suggestion=None
        status="human_required" if cls=="C" else "evidence_available"

        # Direct Class A suggestion: rotor access depth band.
        if key=="rotor_access":
            rotor=g[g.get("final_component", pd.Series(dtype=str)).astype(str).str.contains("rotor",case=False,na=False)] if not g.empty else pd.DataFrame()
            if len(rotor)==1 and not seq.empty:
                rr=rotor.iloc[0]; gid=int(rr.group_id)
                ss=seq[pd.to_numeric(seq.group_id,errors="coerce")==gid]
                if len(ss)==1:
                    st=int(float(ss.iloc[0].final_step)); preceding=max(0,st-1)
                    suggestion=_rotor_access_band(preceding)
                    candidate=preceding
                    status="suggestion_available"
                    source_type=_component_source(rr)
                    try: source_confidence=float(rr.get("final_confidence"))
                    except Exception: source_confidence=None
                    source_ids={"group_id":gid,"final_step":st}
                    evidence=(f"Current working rotor label: G{gid} `{rr.final_component}`; label source: {rr.get('label_source')}; "
                              f"component confidence: {rr.get('final_confidence')}; final sequence step: {st}; raw preceding rows: {preceding}. "
                              f"Evaluator band suggestion: `{suggestion}`.")
                else:
                    evidence="A rotor-labelled component exists, but it does not map uniquely to the current final sequence."
            elif len(rotor)>1:
                evidence=f"{len(rotor)} rotor-labelled groups exist; human target selection is required before a direct suggestion."
            else:
                evidence="No unique rotor-labelled group is available in the current component table."

        elif key=="mag_ops":
            rotor_steps=[]; mag_steps=[]
            if not seq.empty and "component" in seq.columns:
                rotor_steps=seq[seq.component.astype(str).str.contains("rotor",case=False,na=False)].final_step.tolist()
                mag_steps=seq[seq.component.astype(str).str.fullmatch("magnet",case=False,na=False)].final_step.tolist()
            if len(rotor_steps)==1 and mag_steps:
                rs=int(rotor_steps[0]); before=[int(x) for x in mag_steps if float(x)<rs]; after=sorted(int(x) for x in mag_steps if float(x)>rs)
                source_ids={"rotor_step":rs,"magnet_steps":[int(x) for x in mag_steps]}
                if before:
                    evidence=f"Rotor appears at step {rs}. Magnet-labelled groups occur before it at steps {before} and after it at steps {after}. The ordering is not coherent enough to generate a magnet-access answer, so the suggestion is withheld."
                elif after:
                    n=max(0,after[0]-rs-1)
                    suggestion=_mag_access_band(n); candidate=n; status="suggestion_available"
                    evidence=f"Rotor appears at step {rs}; the first magnet-labelled group after rotor removal appears at step {after[0]}. There are {n} intervening operation(s), giving preliminary band `{suggestion}`. Sequence order does not prove physical magnet release."
                else:
                    evidence="Magnet-labelled groups are present but none appear after rotor removal in the current final sequence."
            else:
                evidence="A unique rotor and one or more magnet-labelled groups are required before a direct magnet-access suggestion can be generated."

        elif key == "fa_tot":
            fast=g[g.get("final_component", pd.Series(dtype=str)).astype(str).str.fullmatch("fastener",case=False,na=False)] if not g.empty else pd.DataFrame()
            if not fast.empty:
                suggestion=int(len(fast)); candidate=suggestion; status="suggestion_available"
                source_ids={"group_ids":[int(x) for x in fast.group_id.tolist()]}
                evidence=f"{len(fast)} explicit fastener-labelled component group(s) are present in the current model. This is a whole-sequence preliminary count; the assessor can narrow the path."
            else:
                evidence="No explicit fastener-labelled component groups are present. This is not evidence that the design contains zero fasteners, because fasteners may be absent from or merged within the STEP model."

        elif key in {"tools"}:
            evidence=f"Sequence tool assignments: {tool_counts or 'none'}. These are operation/tooling suggestions and require human confirmation before mapping to the evaluator tooling band."
            source_ids={"sequence_steps":seq_n}

        elif key in {"req_ops","rob_tot","grasp_tot"}:
            candidate=seq_n
            suggestion=seq_n if seq_n else None
            if suggestion is not None:
                status="suggestion_available"
            label={"req_ops":"required operations","rob_tot":"operations in the robotic scope","grasp_tot":"components requiring handling"}[key]
            evidence=f"The current final sequence contains {seq_n} component-removal operations. The default preliminary suggestion is {seq_n} {label}; the assessor may narrow the assessment scope."
            source_ids={"final_steps":[int(x) for x in seq.final_step.tolist()]} if not seq.empty and "final_step" in seq.columns else {}

        elif key in {"tool_ops","rob_acc","unobs"}:
            if zero_blockers is None:
                evidence="No final sequence blocker data is available."
            else:
                candidate=zero_blockers
                evidence=f"{zero_blockers} of {seq_n} sequence rows currently have no blocker_group_ids. This is a geometry/sequence proxy only; it does not establish real tool or robot access."

        elif key in {"clear_ratio","bear_clear"}:
            evidence=clear_summary

        elif key in {"joint","mat_joint","cool_disc"}:
            evidence=f"Current relationship/interface evidence: {rel_summary}. Generic interface candidates do not establish adhesive, weld, thread-lock or material joint condition."

        elif key in {"no_reorient"}:
            evidence=f"Current final sequence uses {seq['final_direction'].nunique() if not seq.empty and 'final_direction' in seq.columns else 0} extraction-direction labels and changes direction {direction_changes} time(s). Whole-product reorientation is not directly modelled."

        elif key in {"grasp_n","grasp"}:
            candidate=len(handling_groups)
            evidence=f"Handling-related feature classes occur on {len(handling_groups)} component group(s): {handling_groups[:20]}{'…' if len(handling_groups)>20 else ''}. These features indicate geometric handling candidates, not verified stable grasps."
            source_ids={"group_ids":handling_groups}

        elif key in {"sequence","seq_judgement"}:
            seq_band, transition_events=_sequence_simplicity(seq)
            if key=="sequence" and seq_band is not None:
                suggestion=seq_band; candidate=transition_events; status="suggestion_available"
            evidence=f"Sequence length={seq_n}; tool assignments={tool_counts}; direction changes={direction_changes}; combined tool/orientation transition events={transition_events}; rows with zero blocker_group_ids={zero_blockers}." + (f" Preliminary sequence band: `{seq_band}`." if seq_band else "")

        elif key in {"cool_inspect"}:
            selected_cooling = target_selections.get("cooling_target")
            if selected_cooling not in (None, "", 0, "0") and not seq.empty and "group_id" in seq.columns:
                try:
                    gid = int(selected_cooling)
                except Exception:
                    gid = None
                cool = seq[pd.to_numeric(seq.group_id, errors="coerce") == gid] if gid is not None else pd.DataFrame()
            else:
                cool=seq[seq.component.astype(str).str.contains("cool",case=False,na=False)] if not seq.empty and "component" in seq.columns else pd.DataFrame()
            if len(cool)==1:
                st=int(cool.iloc[0].final_step); preceding=max(0,st-1)
                suggestion=_cooling_inspection_band(preceding); candidate=preceding; status="suggestion_available"
                evidence=f"Cooling-labelled component G{int(cool.iloc[0].group_id)} appears at final sequence step {st}, with {preceding} preceding removals. This gives preliminary inspection-access band `{suggestion}`. Human confirmation is required because sequence access does not prove actual testability."
                source_ids={"group_id":int(cool.iloc[0].group_id),"final_step":st}
            elif len(cool)>1:
                vals=[int(x) for x in cool.final_step.tolist()]
                evidence=f"Multiple cooling-labelled components appear at steps {vals}; select/confirm the relevant cooling target before using a direct suggestion."
            else:
                evidence="No cooling-labelled component appears in the current final sequence."

        elif key in {"bear_access","extract_feature","puller","robot_grasp","extract_dir","no_obstruction"}:
            bearing_groups=[]
            selected_bearing = target_selections.get("bearing_target")
            if selected_bearing not in (None, "", 0, "0"):
                try:
                    bearing_groups=[int(selected_bearing)]
                except Exception:
                    bearing_groups=[]
            elif not g.empty and "final_component" in g.columns:
                bearing_groups=g[g.final_component.astype(str).str.contains("bearing",case=False,na=False)].group_id.astype(int).tolist()
            if len(bearing_groups)==1:
                gid=bearing_groups[0]; ss=seq[pd.to_numeric(seq.get("group_id"),errors="coerce")==gid] if not seq.empty and "group_id" in seq.columns else pd.DataFrame()
                source_ids={"group_id":gid}
                if len(ss)==1 and key=="bear_access":
                    st=int(float(ss.iloc[0].final_step)); preceding=max(0,st-1)
                    suggestion=_bearing_access_band(preceding); candidate=preceding; status="suggestion_available"
                    source_ids["final_step"]=st
                    evidence=f"Bearing-labelled G{gid} appears at final sequence step {st}, with {preceding} preceding removals. Preliminary access band: `{suggestion}`."
                elif len(ss)==1 and key=="extract_dir":
                    d=str(ss.iloc[0].get("final_direction") or "")
                    if d and d!="nan": suggestion="Yes"; status="suggestion_available"
                    evidence=f"Bearing-labelled G{gid} has final sequence extraction direction `{d}`. This is a geometry-derived preliminary direction, not physical validation of the extraction process."
                elif len(ss)==1 and key=="no_obstruction":
                    blockers=_safe_list(ss.iloc[0].get("blocker_group_ids")); suggestion="Yes" if len(blockers)==0 else "No"; status="suggestion_available"
                    source_ids["blocker_group_ids"]=blockers
                    evidence=f"Bearing-labelled G{gid} has blocker_group_ids={blockers}. Preliminary no-obstruction answer: `{suggestion}`. Near-interface evidence should still be reviewed."
                else:
                    evidence=f"Bearing-labelled G{gid} is identified, but this input still requires feature/tool interpretation beyond the direct sequence fields."
            elif len(bearing_groups)>1:
                evidence=f"Multiple bearing-labelled groups are present: {bearing_groups}. Select/confirm the bearing target before a direct suggestion can be generated."
                source_ids={"group_ids":bearing_groups}
            else:
                evidence="No bearing-labelled component group is identified in the current component table, so the platform cannot produce bearing-specific evidence automatically."

        elif key in {"fa_acc","fa_tot"}:
            if not f.empty:
                ft=f["feature_type"].astype(str).value_counts().to_dict() if "feature_type" in f.columns else {}
                evidence=f"Extracted fastening-related geometry candidates include hole/bore and slot candidates: {ft}. These are geometric feature candidates, not a verified fastener inventory."
            else:
                evidence="No component feature table is available."

        elif key in {"access_depth","insp_dis"}:
            sel=target_selections.get(key)
            if sel not in (None,"",0,"0") and not seq.empty:
                try: gid=int(sel)
                except Exception: gid=None
                ss=seq[pd.to_numeric(seq.get("group_id"),errors="coerce")==gid] if gid is not None and "group_id" in seq.columns else pd.DataFrame()
                if len(ss)==1:
                    st=int(float(ss.iloc[0].final_step)); preceding=max(0,st-1)
                    suggestion=_access_depth_band(preceding) if key=="access_depth" else _inspection_band(preceding)
                    candidate=preceding; status="suggestion_available"
                    source_ids={"group_id":gid,"final_step":st}
                    evidence=f"Selected target G{gid} appears at final sequence step {st}, with {preceding} preceding removal(s). Preliminary evaluator suggestion: `{suggestion}`."
                else:
                    evidence="The selected target does not map uniquely to the final sequence."
            else:
                evidence="Select the assessment target component to generate a direct sequence-derived access suggestion."

        elif key in {"targets","insp_acc","insp_tot"}:
            evidence="This input depends on a human-defined target/critical-component set. The current platform can provide sequence evidence after those targets are selected."

        elif key in {"m_sum","m_n","w_ind","w_tot"}:
            evidence="The platform has component groups and sequence positions, but the module/service-component assessment boundary is not defined by CAD alone. Human target selection is required before access-depth evidence can be aggregated."

        elif cls=="C":
            evidence=f"Current Steps 1–6 do not reliably provide this information. Required source: {m.get('Current source from platform') or 'engineering/BOM/PMI/PLM/service data'}."
            status="human_required"
            source_type="human/external information"

        else:
            evidence=f"Available upstream source specified by the integration map: {m.get('Current source from platform')}. {m.get('Suggested mapping logic')}"

        rows.append({
            "category":m.get("Category"),"input_key":key,"question":m.get("Step 7 input/question"),
            "class":cls,"integration_mode":m.get("Integration mode"),"source_type":source_type,"source_confidence":source_confidence,
            "source_specification":m.get("Current source from platform"),"evidence":evidence,
            "candidate_value":candidate,"suggested_value":suggestion,"source_ids":source_ids,
            "status":status,"human_role":m.get("Human role"),"limitation":m.get("Limitation / caution"),
            "direction":m.get("Direction")
        })
    return pd.DataFrame(rows)


def adapter_summary(adapter: pd.DataFrame) -> Dict[str, Any]:
    if adapter is None or adapter.empty:
        return {"inputs":0}
    return {
        "inputs":len(adapter),
        "classes":adapter["class"].value_counts().to_dict(),
        "suggestions":int((adapter["status"]=="suggestion_available").sum()),
        "evidence_available":int((adapter["status"]=="evidence_available").sum()),
        "human_required":int((adapter["status"]=="human_required").sum()),
    }


def adapter_fingerprint(adapter: pd.DataFrame) -> str:
    if adapter is None or adapter.empty:
        return ""
    cols=["input_key","class","status","suggested_value","evidence","source_ids"]
    records=[]
    for _,r in adapter[cols].iterrows():
        records.append({c:(r[c] if c!="source_ids" else r[c]) for c in cols})
    payload=json.dumps(records,sort_keys=True,ensure_ascii=False,default=str,separators=(",",":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
