from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, Optional

_DATA = Path(__file__).resolve().parent / "data" / "evaluator_config.json"
CONFIG = json.loads(_DATA.read_text(encoding="utf-8"))
CATEGORIES = CONFIG["categories"]
CATEGORY_BY_ID = {c["id"]: c for c in CATEGORIES}


def _num(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _clamp(n, lo=0.0, hi=100.0):
    return max(lo, min(hi, float(n)))


def _pct(a, b):
    if a in (None, "") or b in (None, ""):
        return None
    try:
        b = float(b)
        if b == 0:
            return None
        return _clamp(float(a) / b * 100.0)
    except (TypeError, ValueError):
        return None


def _clear_score(v):
    x = _num(v)
    if x is None:
        return None
    if x >= 1.5:
        return 100.0
    if x >= 1.25:
        return 90.0
    if x >= 1.0:
        return 75.0
    if x >= 0.75:
        return 50.0
    if x >= 0.5:
        return 25.0
    return 0.0


def _sel_score(key: str, values: Dict[str, Any]):
    val = values.get(key)
    if val in (None, ""):
        return None
    for c in CATEGORIES:
        for q in c.get("qs", []):
            if q.get("k") == key:
                for opt in q.get("o", []):
                    if opt.get("label") == val and isinstance(opt.get("score"), (int, float)):
                        return float(opt["score"])
    return None


def score_category(cat_id: str, values: Dict[str, Any]):
    if cat_id == "modular":
        # Module access inputs are already sums of 0–100 scores. The category
        # subscore is therefore their arithmetic mean, not a percentage ratio.
        m_sum = _num(values.get("m_sum"))
        m_n = _num(values.get("m_n"))
        M = None if m_sum is None or m_n in (None, 0) else _clamp(m_sum / m_n)
        W = _pct(values.get("w_ind"), values.get("w_tot"))
        E = _sel_score("electronics", values)
        S = _pct(values.get("s_std"), values.get("s_tot"))
        parts = [M, W, E, S]
        base = None if any(x is None for x in parts) else .35*M + .25*W + .25*E + .15*S
        return base, {"M": M, "W": W, "E": E, "S": S}

    if cat_id == "fastener":
        A = _pct(values.get("fa_acc"), values.get("fa_tot"))
        R = _sel_score("joint", values)
        dfr = _pct(values.get("dominant"), values.get("std_tot"))
        fds = _sel_score("families", values)
        T = _sel_score("tools", values)
        D = _pct(values.get("req_fast"), values.get("act_fast"))
        S = None if dfr is None or fds is None else .6*dfr + .4*fds
        parts = [A, R, S, T, D]
        base = None if any(x is None for x in parts) else .25*A + .20*R + .20*S + .20*T + .15*D
        return base, {"A": A, "R": R, "S": S, "T": T, "D": D}

    if cat_id == "access":
        T = _pct(values.get("tool_ops"), values.get("req_ops"))
        C = _clear_score(values.get("clear_ratio"))
        D = _sel_score("access_depth", values)
        O = _pct(values.get("unobs"), values.get("targets"))
        R = _sel_score("reorient", values)
        parts = [T, C, D, O, R]
        base = None if any(x is None for x in parts) else .25*T + .20*C + .20*D + .20*O + .15*R
        return base, {"T": T, "C": C, "D": D, "O": O, "R": R}

    if cat_id == "electrical":
        D = _pct(values.get("iso"), values.get("hv_tot"))
        A = _sel_score("auto_iso", values)
        I = _pct(values.get("hv_id"), values.get("hv_comp"))
        P = _pct(values.get("errproof"), values.get("misconn"))
        Vraw = _num(values.get("voltage_pts"))
        V = None if Vraw is None else _clamp(Vraw)
        parts = [D, A, I, P, V]
        base = None if any(x is None for x in parts) else .25*D + .20*A + .15*I + .15*P + .25*V
        return base, {"D": D, "A": A, "I": I, "P": P, "V": V}

    if cat_id == "rotor":
        R = _sel_score("rotor_access", values)
        M = _sel_score("mag_ops", values)
        if values.get("rotor_destructive") == "Yes":
            R = 0.0
        if values.get("mag_destructive") == "Yes":
            M = 0.0
        Ni = _sel_score("ni", values)
        Pi = _sel_score("pi", values)
        Ti = _sel_score("ti", values)
        Ui = _sel_score("ui", values)
        J = None if any(x is None for x in [Ni,Pi,Ti,Ui]) else .40*Ni + .25*Pi + .20*Ti + .15*Ui
        G = _sel_score("grasp", values)
        T = _sel_score("trace_mag", values)
        S = _sel_score("seg", values)
        H = None if any(x is None for x in [G,T,S]) else .40*G + .30*T + .30*S
        parts = [R, M, J, H]
        base = None if any(x is None for x in parts) else .40*R + .25*M + .20*J + .15*H
        return base, {"R":R,"M":M,"J":J,"H":H,"Ni":Ni,"Pi":Pi,"Ti":Ti,"Ui":Ui,"G":G,"T":T,"S":S}

    if cat_id == "bearing":
        I = _sel_score("bear_access", values)
        if values.get("bear_destructive") == "Yes":
            I = 0.0
        keys = ["extract_feature","puller","robot_grasp","extract_dir","no_obstruction"]
        vals = [values.get(k) for k in keys]
        A = None if any(not x for x in vals) else (
            (30 if values.get("extract_feature") == "Yes" else 0) +
            (25 if values.get("puller") == "Yes" else 0) +
            (20 if values.get("robot_grasp") == "Yes" else 0) +
            (15 if values.get("extract_dir") == "Yes" else 0) +
            (10 if values.get("no_obstruction") == "Yes" else 0)
        )
        S = _sel_score("bearing_std", values)
        C = _clear_score(values.get("bear_clear"))
        parts=[I,A,S,C]
        base=None if any(x is None for x in parts) else .30*I + .30*A + .20*S + .20*C
        return base, {"I":I,"A":A,"S":S,"C":C}

    if cat_id == "cooling":
        D = _sel_score("cool_disc", values)
        ks=["selfseal","drain","lowvol","spill","no_reorient"]
        L = None if any(not values.get(k) for k in ks) else (
            (30 if values.get("selfseal") == "Yes" else 0) +
            (20 if values.get("drain") == "Yes" else 0) +
            (20 if values.get("lowvol") == "Yes" else 0) +
            (20 if values.get("spill") == "Yes" else 0) +
            (10 if values.get("no_reorient") == "Yes" else 0)
        )
        S = _sel_score("seal", values)
        I = _sel_score("cool_inspect", values)
        parts=[D,L,S,I]
        base=None if any(x is None for x in parts) else .30*D + .30*L + .20*S + .20*I
        return base, {"D":D,"L":L,"S":S,"I":I}

    if cat_id == "robotic":
        A = _pct(values.get("rob_acc"), values.get("rob_tot"))
        G = _pct(values.get("grasp_n"), values.get("grasp_tot"))
        S = _sel_score("sequence", values)
        if values.get("sequence") == "Highly complex/manual intervention required":
            j = _num(values.get("seq_judgement"))
            S = None if j is None else _clamp(j,0,20)
        V = _pct(values.get("visible"), values.get("detect_tot"))
        parts=[A,G,S,V]
        base=None if any(x is None for x in parts) else .30*A + .25*G + .25*S + .20*V
        return base, {"A":A,"G":G,"S":S,"V":V}

    if cat_id == "material":
        S = _pct(values.get("sep_mass"), values.get("target_mass"))
        J = _sel_score("mat_joint", values)
        I = _pct(values.get("id_mass"), values.get("id_tot_mass"))
        parts=[S,J,I]
        base=None if any(x is None for x in parts) else .40*S + .35*J + .25*I
        return base, {"S":S,"J":J,"I":I}

    if cat_id == "inspection":
        A = _pct(values.get("insp_acc"), values.get("insp_tot"))
        D = _sel_score("insp_dis", values)
        T = _sel_score("insp_prov", values)
        parts=[A,D,T]
        base=None if any(x is None for x in parts) else .40*A + .35*D + .25*T
        return base, {"A":A,"D":D,"T":T}

    if cat_id == "trace":
        I = _pct(values.get("comp_id"), values.get("comp_tot"))
        M = _pct(values.get("mat_id"), values.get("mat_tot"))
        parts=[I,M]
        base=None if any(x is None for x in parts) else .55*I + .45*M
        return base, {"I":I,"M":M}

    raise KeyError(cat_id)


def evaluate_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    values = snapshot.get("values") or {}
    caps = snapshot.get("caps") or {}
    crit = snapshot.get("crit") or {}
    unavailable = set(snapshot.get("unavailable") or [])
    rows=[]
    for cat in CATEGORIES:
        base, subs = score_category(cat["id"], values)
        try:
            cap = _clamp(float(caps.get(cat["id"], 100)))
        except (TypeError, ValueError):
            cap = 100.0
        final = None if base is None else min(base, cap)
        rows.append({
            "id":cat["id"],"name":cat["name"],"weight":float(cat["weight"]),
            "base":base,"cap":cap,"final":final,"subs":subs,
            "critical":crit.get(cat["id"], ""),
            "questions_complete": all((q["k"] in unavailable) or (values.get(q["k"]) not in (None,"")) for q in cat.get("qs",[])),
        })
    by={r["id"]:r for r in rows}
    def grouped(ids,totalw):
        if any(by[i]["final"] is None for i in ids): return None
        return sum(by[i]["final"]*by[i]["weight"] for i in ids)/totalw
    dfd=grouped(["modular","fastener","access","electrical"],.38)
    circ=grouped(["rotor","bearing","cooling","material","inspection","trace"],.47)
    robot=by["robotic"]["final"]
    overall=None if any(r["final"] is None for r in rows) else sum(r["final"]*r["weight"] for r in rows)
    return {"categories":rows,"dfd":dfd,"circularity":circ,"robotic":robot,"overall":overall}
