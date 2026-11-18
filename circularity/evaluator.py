from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict
import pandas as pd
import streamlit as st

from .scoring import CONFIG, CATEGORIES, evaluate_snapshot
from .integration import build_evidence_adapter, adapter_summary, adapter_fingerprint
from .evidence import render_question_context, render_evidence_library, render_redesign_guidance, evidence_counts

_DATA=Path(__file__).resolve().parent/"data"
EXAMPLE=json.loads((_DATA/"example_state.json").read_text(encoding="utf-8"))
CRITICAL=CONFIG["critical"]


def _blank_snapshot():
    return {
        "version":"prototype-4-integrated",
        "meta":{"project":"","assessor":"","revision":"","notes":""},
        "values":{},"crit":{},"caps":{},"unavailable":[],"collapsed":[],
        "redesign":{"focus":[],"selections":{},"notes":""},
        "provenance":{},"assessment_targets":{},"adapter_version":"2.0"
    }


def _ensure_snapshot():
    snap=st.session_state.get("circularity_evaluation")
    if not isinstance(snap,dict):
        snap=_blank_snapshot()
    snap.setdefault("version","prototype-4-integrated")
    snap.setdefault("meta",{})
    snap.setdefault("values",{})
    snap.setdefault("crit",{})
    snap.setdefault("caps",{})
    snap.setdefault("unavailable",[])
    snap.setdefault("collapsed",[])
    snap.setdefault("redesign",{"focus":[],"selections":{},"notes":""})
    snap.setdefault("provenance",{})
    snap.setdefault("assessment_targets",{})
    snap.setdefault("adapter_version","2.0")
    st.session_state.circularity_evaluation=snap
    return snap


def _sync_widget_state(snapshot):
    unavailable=set(snapshot.get("unavailable",[]))
    for cat in CATEGORIES:
        for q in cat.get("qs",[]):
            k=q["k"]; wk=f"circ_input_{k}"
            if wk not in st.session_state:
                raw="" if k in unavailable else snapshot.get("values",{}).get(k,"")
                st.session_state[wk]="" if raw in (None,"") else str(raw)
    for cat in CATEGORIES:
        ck=f"circ_crit_{cat['id']}"; capk=f"circ_cap_{cat['id']}"
        if ck not in st.session_state: st.session_state[ck]=str(snapshot.get("crit",{}).get(cat["id"],""))
        if capk not in st.session_state:
            try: st.session_state[capk]=float(snapshot.get("caps",{}).get(cat["id"],100))
            except Exception: st.session_state[capk]=100.0


def _clear_widget_state():
    for k in list(st.session_state.keys()):
        if str(k).startswith("circ_input_") or str(k).startswith("circ_crit_") or str(k).startswith("circ_cap_") or str(k).startswith("circ_unavail_") or str(k).startswith("circ_meta_") or str(k).startswith("circ_target_"):
            del st.session_state[k]


def _class_label(cls):
    return {"A":"A · direct suggestion when evidence allows","B":"B · evidence-assisted judgement","C":"C · human/design information"}.get(cls,str(cls))


def _format_ids(v):
    if not v: return ""
    return json.dumps(v,ensure_ascii=False)


def render_assessment(project, groups, features, relationships, sequence, assessment=None):
    st.subheader("Circularity Assessment")
    st.caption("Steps 1–6 provide evidence or preliminary suggestions. The assessor confirms the value; the existing deterministic model calculates the score in the next step.")

    snapshot=_ensure_snapshot()
    if snapshot.get("demo_mode"):
        st.warning("Demonstration mode active: the assessment values are illustrative and are not derived from the uploaded motor.")
    snapshot.setdefault("assessment_targets",{})
    for tk in ("access_depth","insp_dis","bearing_target","cooling_target"):
        wk=f"circ_target_{tk}"
        if wk not in st.session_state:
            st.session_state[wk]=int(snapshot["assessment_targets"].get(tk) or 0)
    target_selections={tk:st.session_state.get(f"circ_target_{tk}") for tk in ("access_depth","insp_dis","bearing_target","cooling_target")}
    snapshot["assessment_targets"].update({k:(None if v in (None,0,"0","") else int(v)) for k,v in target_selections.items()})
    adapter=build_evidence_adapter(groups,features,relationships,sequence,assessment,target_selections=target_selections)
    st.session_state.circularity_adapter=adapter
    summ=adapter_summary(adapter)
    current_fp=adapter_fingerprint(adapter)
    previous_fp=snapshot.get("adapter_fingerprint")
    if previous_fp and previous_fp!=current_fp and snapshot.get("values"):
        st.warning("Upstream evidence has changed since this circularity assessment was last reviewed. Confirmed values have been retained rather than overwritten. Review the affected evidence before relying on the assessment.")
        if st.button("Acknowledge current upstream evidence",key="ack_circ_evidence"):
            snapshot["adapter_fingerprint"]=current_fp
            st.session_state.circularity_evaluation=snapshot
            st.rerun()
    elif not previous_fp:
        snapshot["adapter_fingerprint"]=current_fp

    c1,c2,c3,c4=st.columns(4)
    c1.metric("Mapped inputs",summ.get("inputs",0)); c2.metric("Class A",summ.get("classes",{}).get("A",0)); c3.metric("Class B",summ.get("classes",{}).get("B",0)); c4.metric("Class C",summ.get("classes",{}).get("C",0))
    st.info("A = the platform can propose a specific answer when its prerequisite evidence is present; the assessor still confirms it. B = supporting evidence only. C = human/external design information. Missing information remains unavailable rather than becoming zero.")
    ec=evidence_counts()
    st.caption(f"The preserved evidence base is available inside each question and in Step 8: {ec['evidence_register']} evidence entries, {ec['crosswalk']} crosswalk rows, {ec['references']} references and {ec['figures']} literature figures.")

    a,b=st.columns(2)
    if a.button("Load demonstration assessment",use_container_width=True):
        ex=json.loads(json.dumps(EXAMPLE))
        ex.setdefault("provenance",{})
        ex.setdefault("assessment_targets",{})
        ex["version"]="prototype-4-integrated"
        ex["adapter_version"]="2.0"
        ex["demo_mode"]=True
        ex.setdefault("meta",{})
        ex["meta"]["notes"]=(str(ex["meta"].get("notes","")).strip()+" Demonstration mode: these values are illustrative and are not derived from the uploaded STEP model.").strip()
        st.session_state.circularity_evaluation=ex
        _clear_widget_state(); st.rerun()
    if b.button("Reset circularity assessment",use_container_width=True):
        st.session_state.circularity_evaluation=_blank_snapshot(); _clear_widget_state(); st.rerun()
    st.caption("Demonstration assessment loads the preserved illustrative example so the complete workflow can be shown without entering all 80 values. It is not an assessment of the uploaded motor.")

    with st.expander("Advanced / validation tools", expanded=False):
        st.markdown("**80-input evidence adapter**")
        view=adapter[["category","input_key","question","class","status","source_type","source_confidence","candidate_value","suggested_value","evidence","source_ids","limitation"]].copy()
        view["source_ids"]=view["source_ids"].apply(_format_ids)
        st.dataframe(view,use_container_width=True,hide_index=True)
        st.download_button("Download adapter inspection CSV",view.to_csv(index=False).encode(),"circularity_evidence_adapter.csv","text/csv",key="dl_circ_adapter")
        st.markdown("**Import legacy evaluator JSON**")
        up=st.file_uploader("Evaluator JSON",type=["json"],key="native_circ_import")
        if up is not None and st.button("Import snapshot",key="native_circ_import_btn"):
            try:
                imp=json.loads(up.getvalue().decode("utf-8"))
                if not isinstance(imp.get("values"),dict) or not isinstance(imp.get("crit"),dict):
                    raise ValueError("Expected values and crit objects.")
                imp.setdefault("provenance",{})
                imp.setdefault("assessment_targets",{})
                st.session_state.circularity_evaluation=imp
                _clear_widget_state(); st.rerun()
            except Exception as exc:
                st.error(f"Cannot import snapshot: {exc}")
        original=(Path(__file__).resolve().parent.parent/"circularity_evaluator.html")
        if original.exists():
            st.download_button("Download protected original evaluator",original.read_bytes(),"circularity_evaluator_reference.html","text/html",use_container_width=True)
        else:
            st.caption("Protected original evaluator is retained in the full archival package and is not required for this web deployment.")

    with st.expander("Assessment metadata",expanded=False):
        meta=snapshot["meta"]
        meta["project"]=st.text_input("Project",value=str(meta.get("project","")),key="circ_meta_project")
        meta["assessor"]=st.text_input("Assessor",value=str(meta.get("assessor","")),key="circ_meta_assessor")
        meta["revision"]=st.text_input("Revision",value=str(meta.get("revision","")),key="circ_meta_revision")
        meta["notes"]=st.text_area("Notes",value=str(meta.get("notes","")),key="circ_meta_notes")


    _sync_widget_state(snapshot)
    amap=adapter.set_index("input_key").to_dict("index")
    unavailable=set(snapshot.get("unavailable",[]))
    gdf=groups.copy() if isinstance(groups,pd.DataFrame) else pd.DataFrame(groups or [])
    target_opts=[0]
    target_labels={0:"Select target…"}
    if not gdf.empty and "group_id" in gdf.columns:
        for _,gr in gdf.sort_values("group_id").iterrows():
            gid=int(gr.get("group_id")); comp=str(gr.get("final_component") or "unknown")
            target_opts.append(gid); target_labels[gid]=f"G{gid} · {comp}"

    for idx,cat in enumerate(CATEGORIES,1):
        with st.expander(f"{idx}. {cat['name']} · weight {int(round(cat['weight']*100))}%",expanded=(idx==1)):
            st.caption(cat.get("formula",""))
            if cat.get("id") == "bearing":
                st.selectbox("Bearing component for this assessment", target_opts, key="circ_target_bearing_target", format_func=lambda x:target_labels.get(x,str(x)), help="Select the relevant bearing if it is not already identified automatically. This enables sequence-derived preliminary suggestions without returning to Step 2.")
                snapshot.setdefault("assessment_targets",{})["bearing_target"] = None if st.session_state.get("circ_target_bearing_target") in (None,0) else int(st.session_state.get("circ_target_bearing_target"))
            elif cat.get("id") == "cooling":
                st.selectbox("Cooling component for this assessment", target_opts, key="circ_target_cooling_target", format_func=lambda x:target_labels.get(x,str(x)), help="Select the relevant cooling component if it is not already identified automatically. This enables a preliminary inspection-access suggestion.")
                snapshot.setdefault("assessment_targets",{})["cooling_target"] = None if st.session_state.get("circ_target_cooling_target") in (None,0) else int(st.session_state.get("circ_target_cooling_target"))
            for q in cat.get("qs",[]):
                k=q["k"]; row=amap.get(k,{})
                cls=row.get("class","C")
                st.markdown(f"**{q.get('c','')} · {q['l']}**  \n`{_class_label(cls)}`")
                if k in {"access_depth","insp_dis"}:
                    st.selectbox("Assessment target",target_opts,key=f"circ_target_{k}",format_func=lambda x:target_labels.get(x,str(x)))
                    snapshot.setdefault("assessment_targets",{})[k]=None if st.session_state.get(f"circ_target_{k}") in (None,0) else int(st.session_state.get(f"circ_target_{k}"))
                if cls=="A" and row.get("suggested_value") not in (None,""):
                    st.success(f"Suggested from platform: **{row['suggested_value']}**. {row.get('evidence','')}")
                    col1,col2=st.columns([1,3])
                    if col1.button("Accept suggestion",key=f"accept_{k}"):
                        st.session_state[f"circ_input_{k}"]=str(row["suggested_value"])
                        snapshot["values"][k]=str(row["suggested_value"])
                        snapshot["provenance"][k]={"human_state":"accepted_suggestion","class":cls,"suggested_value":row.get("suggested_value"),"source_type":row.get("source_type"),"source_ids":row.get("source_ids"),"evidence":row.get("evidence")}
                        if k in unavailable: unavailable.remove(k)
                        snapshot["unavailable"]=sorted(unavailable)
                        st.session_state.circularity_evaluation=snapshot
                        st.rerun()
                elif cls=="A":
                    st.info("Automatic suggestion unavailable for this motor. The required prerequisite evidence is not currently identified; you can still complete the assessment manually.")
                    if row.get("evidence"):
                        st.caption(row.get("evidence"))
                elif cls=="B":
                    st.info(row.get("evidence") or "Relevant upstream evidence is available; human interpretation is required.")
                else:
                    st.warning(row.get("evidence") or "Human or external design information is required.")

                # Keep the assessment rule visible at the point of decision.
                if q.get("t") == "select" and q.get("o"):
                    guide = "  •  ".join(f"{o.get('label')} = {o.get('score')}" for o in q.get("o", []))
                    st.caption(f"Scoring guide: {guide}")
                elif q.get("h"):
                    st.caption(f"Assessment guidance: {q.get('h')}")

                render_question_context(cat, q, row)

                unkey=f"circ_unavail_{k}"
                if unkey not in st.session_state: st.session_state[unkey]=k in unavailable
                is_un=st.checkbox("Information not yet available",key=unkey)
                if is_un:
                    unavailable.add(k)
                    snapshot["values"].pop(k,None)
                    snapshot["provenance"][k]={"human_state":"unavailable","class":cls,"source_type":row.get("source_type"),"source_ids":row.get("source_ids"),"evidence":row.get("evidence")}
                    st.session_state[f"circ_input_{k}"]=""
                    st.caption("Information gap recorded; this input is incomplete and is not scored as zero.")
                else:
                    unavailable.discard(k)
                    wk=f"circ_input_{k}"
                    old=snapshot["values"].get(k,"")
                    if q.get("t")=="select":
                        opts=[""]+[str(o["label"]) for o in q.get("o",[])]
                        if st.session_state.get(wk) not in opts: st.session_state[wk]=""
                        val=st.selectbox("Assessment value",opts,key=wk,format_func=lambda x:"Select…" if x=="" else x)
                    else:
                        val=st.text_input("Assessment value",key=wk,placeholder="Enter numeric value")
                    if val not in (None,""):
                        snapshot["values"][k]=str(val)
                        prov=snapshot["provenance"].get(k,{})
                        if prov.get("human_state")!="accepted_suggestion" or str(val)!=str(row.get("suggested_value")):
                            state="edited_suggestion" if cls=="A" and row.get("suggested_value") not in (None,"") else "manual"
                            snapshot["provenance"][k]={"human_state":state,"class":cls,"suggested_value":row.get("suggested_value"),"source_type":row.get("source_type"),"source_ids":row.get("source_ids"),"evidence":row.get("evidence")}
                    else:
                        snapshot["values"].pop(k,None)
                st.divider()

            st.caption("Critical Failure Check: confirm whether a severe condition applies that should limit the maximum category score.")
            crit_opts=[("","Select…"),("none","No critical failure confirmed")]
            for j,x in enumerate(CRITICAL.get(cat["name"],[])):
                crit_opts.append((str(j),x[0]))
            ck=f"circ_crit_{cat['id']}"
            capk=f"circ_cap_{cat['id']}"
            keys=[x[0] for x in crit_opts]; labels={x[0]:x[1] for x in crit_opts}
            if st.session_state.get(ck) not in keys: st.session_state[ck]=""
            old_cv=str(snapshot.get("crit",{}).get(cat["id"],""))
            cv=st.selectbox("Critical failure condition",keys,key=ck,format_func=lambda x:labels[x])
            if cv != old_cv:
                suggested_cap=100.0
                if cv not in ("","none"):
                    rule=CRITICAL[cat["name"]][int(cv)]
                    m=re.search(r"(\d+(?:\.\d+)?)", str(rule[2]))
                    if m: suggested_cap=float(m.group(1))
                st.session_state[capk]=suggested_cap
            snapshot["crit"][cat["id"]]=cv
            if cv not in ("","none"):
                x=CRITICAL[cat["name"]][int(cv)]
                m=re.search(r"(\d+(?:\.\d+)?)", str(x[2]))
                suggested=m.group(1) if m else str(x[2])
                st.error(f"{x[1]} condition confirmed. Suggested maximum category score: {suggested}%.")
            cap=st.number_input("Confirmed maximum category score (%)",min_value=0.0,max_value=100.0,step=1.0,key=capk)
            snapshot["caps"][cat["id"]]=float(cap)

    snapshot["unavailable"]=sorted(unavailable)
    snapshot["meta"]=snapshot.get("meta",{})
    st.session_state.circularity_evaluation=snapshot
    st.success(f"Assessment state is linked directly to this project: {len(snapshot['values'])}/80 values entered; {len(snapshot['unavailable'])} information gaps recorded.")
    st.download_button("Download circularity assessment JSON",json.dumps(snapshot,ensure_ascii=False,indent=2).encode(),"circularity_evaluation.json","application/json",key="native_circ_download")


def render_results():
    st.subheader("Circularity Results & Diagnosis")
    snapshot=_ensure_snapshot()
    if snapshot.get("demo_mode"):
        st.warning("Demonstration mode active: these circularity results are illustrative and are not derived from the uploaded motor.")
    result=evaluate_snapshot(snapshot)
    if not snapshot.get("values"):
        st.info("Complete or load a Circularity Assessment first. The evidence library remains available below.")
        render_evidence_library(key_prefix="results_evidence_empty")
        return

    def fmt(x): return "—" if x is None else f"{x:.1f}"

    def score_bar(label: str, score: Any, key: str, compact: bool = False) -> None:
        if score is None:
            st.markdown(f"<div style='margin:.2rem 0 .65rem 0'><div style='font-weight:600'>{label}<span style='float:right'>—</span></div><div style='height:12px;background:#e9eff4;border-radius:999px'></div></div>", unsafe_allow_html=True)
            return
        value=max(0.0,min(100.0,float(score)))
        height="10px" if compact else "14px"
        margin=".15rem 0 .55rem 0" if compact else ".25rem 0 .8rem 0"
        st.markdown(
            f"""
            <div style="margin:{margin}">
              <div style="font-weight:600;margin-bottom:5px">{label}<span style="float:right">{value:.1f}</span></div>
              <div style="height:{height};background:#e9eff4;border-radius:999px;overflow:hidden">
                <div style="height:100%;width:{value:.2f}%;border-radius:999px;background:linear-gradient(90deg,#5aa0d6 0%,#62b37a 100%)"></div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### Summary scores")
    c1,c2,c3,c4=st.columns(4)
    with c1: score_bar("Overall",result["overall"],"overall",compact=True)
    with c2: score_bar("DfD",result["dfd"],"dfd",compact=True)
    with c3: score_bar("Circularity",result["circularity"],"circularity",compact=True)
    with c4: score_bar("Robotic",result["robotic"],"robotic",compact=True)

    st.markdown("#### Category scores")
    for r in result["categories"]:
        label=r["name"]
        if r["final"] is not None and r["cap"] < 100:
            label=f"{label} · cap {r['cap']:.0f}%"
        score_bar(label,r["final"],r["id"])

    with st.expander("View score table", expanded=False):
        rows=[]
        for r in result["categories"]:
            rows.append({"Category":r["name"],"Weight %":int(round(r["weight"]*100)),"Base score":None if r["base"] is None else round(r["base"],2),"Cap":r["cap"],"Final score":None if r["final"] is None else round(r["final"],2),"Critical selection":r["critical"]})
        rdf=pd.DataFrame(rows)
        st.dataframe(rdf,use_container_width=True,hide_index=True)

    flags=[]
    for r in result["categories"]:
        cv=r["critical"]
        if cv not in (None,"","none"):
            x=CRITICAL[r["name"]][int(cv)]
            flags.append((r["name"],x))
    if flags:
        st.markdown("#### Confirmed critical conditions")
        for name,x in flags: st.error(f"**{name}:** {x[0]} · {x[1]} · {x[2]}")

    completed=[r for r in result["categories"] if r["final"] is not None]
    if completed:
        st.markdown("#### Diagnosis")
        low=sorted(completed,key=lambda x:x["final"])[:3]
        for i,r in enumerate(low,1): st.write(f"{i}. **{r['name']}** · final score {r['final']:.1f}")
        st.caption("These are relative weaknesses within the completed assessment. A low score is prioritisation context, not proof of a specific geometric defect.")

    unavailable=snapshot.get("unavailable",[])
    if unavailable:
        st.markdown("#### Information gaps")
        st.write(", ".join(f"`{x}`" for x in unavailable))
        st.caption("These gaps can later support data-acquisition recommendations. They are not scored as zero.")

    prov=snapshot.get("provenance",{})
    counts={}
    for p in prov.values(): counts[p.get("human_state","unknown")]=counts.get(p.get("human_state","unknown"),0)+1
    if counts:
        st.markdown("#### Assessment provenance")
        st.write(counts)

    # Full evidence/audit access remains available in the merged native workflow.
    default_cat=None
    if completed:
        default_cat=sorted(completed,key=lambda x:x["final"])[0].get("id")
    render_evidence_library(default_category=default_cat, key_prefix="results_evidence")

    with st.expander("Protected original evaluator reference",expanded=False):
        st.caption("The original HTML remains unchanged as the regression and content-preservation baseline. The native workflow should only replace it after scoring and content parity are demonstrated.")
        original=Path(__file__).resolve().parent.parent/"circularity_evaluator.html"
        if original.exists():
            st.download_button("Download original HTML evaluator",original.read_bytes(),"circularity_evaluator_reference.html","text/html",key="results_original_html")
        else:
            st.caption("The original HTML remains preserved in the full archival package; this web deployment uses the extracted native evidence resources.")


def render_recommendation_context():
    snapshot=st.session_state.get("circularity_evaluation")
    result=None
    if isinstance(snapshot,dict) and snapshot.get("values"):
        result=evaluate_snapshot(snapshot)
        completed=[r for r in result["categories"] if r["final"] is not None]
        if completed or snapshot.get("unavailable"):
            with st.expander("Confirmed circularity context available to this stage",expanded=True):
                if completed:
                    low=sorted(completed,key=lambda x:x["final"])[:4]
                    st.write("**Lowest confirmed category scores:** "+"; ".join(f"{r['name']} {r['final']:.1f}" for r in low))
                flags=[]
                for r in result["categories"]:
                    if r["critical"] not in (None,"","none"):
                        x=CRITICAL[r["name"]][int(r["critical"])]
                        flags.append(f"{r['name']}: {x[0]}")
                if flags: st.write("**Confirmed critical conditions:** "+"; ".join(flags))
                if snapshot.get("unavailable"): st.write("**Information gaps:** "+", ".join(snapshot["unavailable"]))
                st.caption("This confirmed assessment context supports prioritisation. A specific physical recommendation still requires design-specific evidence or explicit human-confirmed design information.")
    render_redesign_guidance(result, snapshot if isinstance(snapshot,dict) else None, key_prefix="recommendation_guidance")
