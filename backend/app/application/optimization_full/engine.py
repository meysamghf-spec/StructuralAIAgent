"""Section optimizer on the SAIA sparse 3D engine (``model_import.solve``).

* Variables: one gene per member group.  Default groups = (type, storey band, plan position, beam direction); member
  types defined in chat («ستون‌های گوشه طبقات ۱ تا ۳: ...») override the default grouping and candidate list.
* Candidates: rectangular RC sections (b ≠ h allowed) or steel catalog sections (IPE / HEA / HEB / 2UNP / BOX / PIPE).
* Every evaluation = full analysis (gravity + Standard 2800 static seismic + P-Delta) and real design:
  Mabhas 9 beam flexure/shear (bars + stirrups) and P-M column design (bars + ties) with the user's bar diameters;
  steel members AISC 360 H1-1.  Drift (Standard 2800 limit), beam depth (L/h) and column continuity are constraints.
* Search: fully-stressed design → greedy down-sizing → stochastic local search, within a configurable budget,
  with progress callbacks and cancel.
"""

from __future__ import annotations

import math
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from app.application import mabhas9_rc_design as m9
from app.application.model_import.design import design_members
from app.application.model_import.solve import analyze_imported_model

from .builder import ensure_section, tag_members, with_sections
from .sections import DEFAULT_REBAR_MM, DEFAULT_RC_BEAMS, DEFAULT_RC_COLUMNS, DEFAULT_STEEL

STEEL_DENSITY = 7850.0
DEFAULT_PRICES = {"concrete_per_m3": 4_500_000, "rebar_per_kg": 45_000, "formwork_per_m2": 600_000, "steel_per_kg": 60_000,
                  "currency": "تومان"}
_M9_LOCK = threading.Lock()


@dataclass
class Options:
    time_budget_s: float = 120.0
    max_evals: int = 400
    storey_band: int = 2          # storeys per default group
    group_by_position: bool = True
    group_beams_by_direction: bool = True
    deflection_ratio: float = 21.0  # h ≥ L / ratio (Mabhas 9 table, both ends continuous)
    check_deflection: bool = True
    drift_check: bool = True
    seed: int = 1
    prices: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_PRICES))
    ductility: str = "intermediate"

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> "Options":
        d = dict(d or {})
        o = cls()
        for k in ("time_budget_s", "deflection_ratio"):
            if k in d and d[k] is not None:
                setattr(o, k, float(d[k]))
        for k in ("max_evals", "storey_band", "seed"):
            if k in d and d[k] is not None:
                setattr(o, k, int(d[k]))
        for k in ("group_by_position", "group_beams_by_direction", "check_deflection", "drift_check"):
            if k in d and d[k] is not None:
                setattr(o, k, bool(d[k]))
        if d.get("ductility") in ("ordinary", "intermediate", "special"):
            o.ductility = d["ductility"]
        if isinstance(d.get("prices"), dict):
            o.prices.update({k: float(v) for k, v in d["prices"].items() if k != "currency" and v is not None})
        o.time_budget_s = min(max(o.time_budget_s, 5.0), 1800.0)
        o.max_evals = min(max(o.max_evals, 5), 5000)
        o.storey_band = max(1, o.storey_band)
        return o


class Cancelled(Exception):
    pass


# ------------------------------------------------------------------ input checks
OPT_TYPES = ("column", "beam", "brace")
TYPE_ALIASES = {"girder": "beam", "joist": "beam", "lintel": "beam", "post": "column", "pier": "column",
                "bracing": "brace", "diagonal": "brace", "strut": "brace"}


class OptimizationInputError(ValueError):
    """Input problem with a clear Persian message (shown to the user as-is)."""


def prepare_model(model: dict[str, Any]) -> dict[str, Any]:
    """Validates / normalises an (imported or chat) model for the optimizer; raises OptimizationInputError (Persian)."""
    if not isinstance(model, dict):
        raise OptimizationInputError("مدل سازه نامعتبر است؛ مدل را دوباره وارد کنید.")
    model.setdefault("sections", {}); model.setdefault("materials", {})
    nodes = model.get("nodes") or {}
    members = model.get("members") or []
    if not nodes or not members:
        raise OptimizationInputError("مدل هیچ عضو یا گره‌ای ندارد؛ ابتدا مدل را در چت بسازید یا فایل ETABS/SAP را وارد کنید.")
    bad_nodes, no_section = [], []
    for mem in members:
        t = str(mem.get("type") or "").strip().lower()
        mem["type"] = TYPE_ALIASES.get(t, t)
        if mem.get("i") not in nodes or mem.get("j") not in nodes:
            bad_nodes.append(str(mem.get("id")))
        elif mem["type"] in OPT_TYPES and not mem.get("section"):
            no_section.append(str(mem.get("id")))
    if bad_nodes:
        raise OptimizationInputError("این اعضا به گره‌ای وصل‌اند که در مدل وجود ندارد: " + "، ".join(bad_nodes[:10])
                                     + "؛ مدل را در مرحله بازبینی ایمپورت اصلاح کنید.")
    if no_section:
        raise OptimizationInputError("این اعضا مقطع ندارند: " + "، ".join(no_section[:10])
                                     + "؛ در بازبینی مدل برایشان مقطع تعیین کنید.")
    if not any(m["type"] in OPT_TYPES for m in members):
        raise OptimizationInputError("مدل هیچ تیر، ستون یا مهاربندی برای بهینه‌سازی ندارد.")
    return model


def friendly_error(exc: BaseException) -> str:
    """Persian message for any optimizer failure (no raw exception text)."""
    if isinstance(exc, OptimizationInputError):
        return str(exc)
    msg = str(exc)
    if "blocking review" in msg:
        return "مدل واردشده هنوز موارد مسدودکننده در بازبینی دارد؛ ابتدا آن‌ها را در صفحه ایمپورت مدل برطرف و تأیید کنید."
    if isinstance(exc, (KeyError, IndexError, TypeError)):
        return ("بهینه‌سازی به‌دلیل ناقص بودن اطلاعات مدل متوقف شد (مقطع، مصالح یا گره‌ی ناقص). "
                "مدل را در صفحه ایمپورت بازبینی کنید یا با پشتیبانی تماس بگیرید.")
    if "singular" in msg.lower() or "unstable" in msg.lower():
        return "سازه ناپایدار است (تکیه‌گاه یا اتصال کافی ندارد)؛ تکیه‌گاه‌ها و اتصال اعضا را در مدل کنترل کنید."
    return "بهینه‌سازی با خطای داخلی متوقف شد؛ دوباره تلاش کنید و اگر تکرار شد، مدل را بازبینی کنید."


# ------------------------------------------------------------------ groups
def _is_steel(model: dict[str, Any], mem: dict[str, Any]) -> bool:
    sec = model["sections"].get(mem["section"]) or {}
    mat = model["materials"].get(sec.get("material")) or {}
    return bool(sec.get("catalog")) or "steel" in str(mat.get("type", "")).lower()


def _rule_matches(rule: dict[str, Any], mem: dict[str, Any]) -> bool:
    if rule.get("type") and rule["type"] != mem["type"]:
        return False
    if rule.get("positions") and mem.get("position") not in rule["positions"]:
        return False
    if rule.get("storeys"):
        st = rule["storeys"]
        if mem.get("storey") not in st:
            return False
    if rule.get("direction") and mem.get("direction") != rule["direction"]:
        return False
    return True


def build_groups(model: dict[str, Any], lists: dict[str, Any], opt: Options) -> list[dict[str, Any]]:
    top = max((m.get("storey", 1) for m in model["members"] if m.get("type") in OPT_TYPES), default=1)
    rules = []
    for r in lists.get("member_types") or []:
        r = dict(r)
        if r.get("storeys"):
            r["storeys"] = [top if s == "roof" else s for s in r["storeys"]]
        rules.append(r)
    groups: dict[tuple, dict[str, Any]] = {}
    for mem in model["members"]:
        if mem["type"] not in OPT_TYPES:
            continue  # walls / links / unknown types stay as modelled
        steel = _is_steel(model, mem)
        rule = next((r for r in rules if _rule_matches(r, mem)), None)
        if rule is not None:
            key = ("rule", rule["name"], steel)
            label = rule["name"]
            cands = rule.get("candidates") or []
        else:
            st = mem.get("storey", 1)
            band = (st - 1) // opt.storey_band
            s0, s1 = band * opt.storey_band + 1, min(top, (band + 1) * opt.storey_band)
            pos = mem.get("position", "all") if opt.group_by_position else "all"
            dirn = mem.get("direction", "") if mem["type"] == "beam" and opt.group_beams_by_direction else ""
            key = (mem["type"], s0, pos, dirn, steel)
            fa = {"column": "ستون", "beam": "تیر", "brace": "مهاربند"}.get(mem["type"], mem["type"]) + (" فولادی" if steel else "")
            pfa = {"corner": "گوشه", "edge": "کناری", "interior": "میانی", "all": ""}.get(pos, pos)
            label = " ".join(x for x in (fa, pfa, f"جهت {dirn}" if dirn else "", f"طبقه {s0}" if s0 == s1 else f"طبقات {s0}-{s1}") if x)
            cands = []
        g = groups.setdefault(key, {"key": "|".join(map(str, key)), "label": label, "type": mem["type"], "steel": steel,
                                    "members": [], "cands": cands, "storeys": set()})
        g["members"].append(mem["id"])
        g["storeys"].add(mem.get("storey", 1))
    out = []
    for g in groups.values():
        kind = g["type"]
        pool = g["cands"] or lists.get({"column": "columns", "beam": "beams", "brace": "braces"}.get(kind, "beams")) or []
        pool = [c for c in pool if isinstance(c, str) == g["steel"]]
        if not pool:
            pool = (list(DEFAULT_STEEL.get(kind) or DEFAULT_STEEL["beam"]) if g["steel"]
                    else DEFAULT_RC_COLUMNS if kind == "column" else DEFAULT_RC_BEAMS)
        g["cands"] = pool
        g["storeys"] = sorted(g["storeys"])
        out.append(g)
    out.sort(key=lambda g: (g["type"], g["storeys"][0], g["key"]))
    return out


# ------------------------------------------------------------------ evaluation
class Evaluator:
    def __init__(self, model: dict[str, Any], groups: list[dict[str, Any]], lists: dict[str, Any], opt: Options):
        self.model, self.groups, self.opt = model, groups, opt
        mat = lists.get("materials") or {}
        self.fc = float(mat.get("fc_mpa") or 30.0)
        self.fy = float(mat.get("fy_mpa") or 400.0)
        self.fy_steel = float(mat.get("steel_fy_mpa") or 240.0)
        bars = sorted({int(d) for d in (lists.get("rebar_mm") or DEFAULT_REBAR_MM)})
        self.beam_bars = tuple(d for d in bars if 12 <= d <= 28) or m9.BEAM_BARS
        self.col_bars = tuple(d for d in bars if 14 <= d <= 32) or m9.COLUMN_BARS
        self.names: list[list[str]] = []
        for g in groups:
            names = [ensure_section(model, g["type"], c, self.fc, self.fy_steel) for c in g["cands"]]
            uniq = list(dict.fromkeys(names))
            uniq.sort(key=lambda n: model["sections"][n].get("A", 0.0))
            self.names.append(uniq)
        if "CONC (optimizer)" in model["materials"]:
            model["materials"]["CONC (optimizer)"].update({"E": 4700 * math.sqrt(self.fc) * 1000, "Fc": self.fc * 1e3})
        self.cache: dict[tuple, dict[str, Any]] = {}
        self.evals = 0

    def initial_genes(self) -> list[int]:
        genes = []
        mems = {m["id"]: m for m in self.model["members"]}
        for g, names in zip(self.groups, self.names):
            cur = mems[g["members"][0]]["section"]
            a_cur = self.model["sections"].get(cur, {}).get("A", 0.0)
            genes.append(min(range(len(names)), key=lambda i: abs(self.model["sections"][names[i]].get("A", 0.0) - a_cur)))
        return genes

    def assignment(self, genes: list[int]) -> dict[str, str]:
        return {mid: self.names[k][gi] for k, gi in enumerate(genes) for mid in self.groups[k]["members"]}

    def evaluate(self, genes: list[int]) -> dict[str, Any]:
        key = tuple(genes)
        if key in self.cache:
            return self.cache[key]
        self.evals += 1
        assign = self.assignment(genes)
        model = with_sections(self.model, assign)
        captured: dict[str, Any] = {}

        def hook(mdl, eng, cases, lengths):
            captured["eng"], captured["cases"], captured["lengths"] = eng, cases, lengths

        res = analyze_imported_model(model, station_hook=hook, fast=True)
        out = self._design(model, genes, res, captured)
        self.cache[key] = out
        return out

    # -- design of every group
    def _design(self, model, genes, res, cap) -> dict[str, Any]:
        eng, cases, lengths = cap.get("eng"), cap.get("cases") or {}, cap.get("lengths") or {}
        idx = {el.id: n for n, el in enumerate(eng.elements)} if eng is not None else {}
        cnames = list(cases)
        stack = np.array([cases[c] for c in cnames]) if cnames else None  # (cases, members, stations, 6)
        seismic_case = np.array(["E" in c.split(":", 1)[-1] or "RS" in c for c in cnames]) if cnames else None
        steel_rows = {}
        if any(g["steel"] for g in self.groups) and eng is not None:
            d = design_members(model, eng, cases, lengths, limit=10**7)
            steel_rows = {r["member"]: r for r in d["members"] if r.get("kind") == "steel"}
        prices = self.opt.prices
        groups_out, total, viol = [], {"concrete_m3": 0.0, "rebar_kg": 0.0, "formwork_m2": 0.0, "steel_kg": 0.0}, 0.0
        with _M9_LOCK:
            old = (m9.BEAM_BARS, m9.COLUMN_BARS)
            m9.BEAM_BARS, m9.COLUMN_BARS = self.beam_bars, self.col_bars
            try:
                for k, g in enumerate(self.groups):
                    name = self.names[k][genes[k]]
                    sec = model["sections"][name]
                    rows = [idx[mid] for mid in g["members"] if mid in idx]
                    Ls = [lengths.get(mid, 0.0) for mid in g["members"]]
                    info: dict[str, Any] = {"group": g["key"], "label": g["label"], "type": g["type"], "section": name,
                                            "members": len(g["members"]), "index": genes[k], "options": len(self.names[k])}
                    if g["steel"]:
                        dc = max((steel_rows[m]["ratio"] for m in g["members"] if m in steel_rows), default=0.0)
                        kg = sum(sec.get("A", 0.0) * L * STEEL_DENSITY for L in Ls)
                        total["steel_kg"] += kg
                        info.update({"DC": dc, "steel_kg": kg, "design": "AISC 360 H1-1"})
                    elif stack is None or not rows:
                        info.update({"DC": 0.0})
                    else:
                        b, h = sec["b"], sec["h"]
                        st = stack[:, rows]  # (cases, members, stations, 6)
                        vol = sum(b * h * L for L in Ls)
                        total["concrete_m3"] += vol
                        if g["type"] == "beam":
                            info.update(self._beam(st, b, h, Ls, seismic_case))
                            total["formwork_m2"] += sum((b + 2 * h) * L for L in Ls)
                            if self.opt.check_deflection and Ls:
                                need = max(Ls) / self.opt.deflection_ratio
                                info["h_min_m"] = need
                                if h + 1e-6 < need:
                                    viol += (need - h) / need
                                    info["deflection_ok"] = False
                        else:
                            info.update(self._column(st, b, h, g["members"], Ls, cnames, seismic_case))
                            total["formwork_m2"] += sum(2 * (b + h) * L for L in Ls)
                        total["rebar_kg"] += info.get("rebar_kg", 0.0)
                    dcv = info.get("DC", 0.0)
                    if not math.isfinite(dcv):
                        dcv = 9.99
                        info["DC"] = 9.99
                    if dcv > 1.0:
                        viol += dcv - 1.0
                    groups_out.append(info)
            finally:
                m9.BEAM_BARS, m9.COLUMN_BARS = old
        # drift
        drift_ratio, drift_rows = 0.0, []
        if self.opt.drift_check:
            for d in res.get("drifts") or []:
                lim = d.get("limit") or 0.02
                r = (d.get("max") or 0.0) / lim
                drift_ratio = max(drift_ratio, r)
                drift_rows.append({"case": d["case"], "max": d.get("max"), "limit": lim, "ok": d.get("ok", True)})
            if drift_ratio > 1.0:
                viol += 2.0 * (drift_ratio - 1.0)
        # column continuity (upper ≤ lower, per position)
        cont = 0
        cols = [(g, groups_out[k]) for k, g in enumerate(self.groups) if g["type"] == "column" and not g["steel"]]
        mems = {m["id"]: m for m in model["members"]}
        below: dict[str, tuple[float, float, int]] = {}
        for g, info in sorted(cols, key=lambda t: t[0]["storeys"][0]):
            sec = model["sections"][info["section"]]
            for mid in g["members"]:
                plan = (round(model["nodes"][mems[mid]["i"]]["x"], 2), round(model["nodes"][mems[mid]["i"]]["y"], 2))
                st = mems[mid].get("storey", 1)
                prev = below.get(str(plan))
                if prev and prev[2] < st and (sec["b"] > prev[0] + 1e-6 or sec["h"] > prev[1] + 1e-6):
                    cont += 1
                below[str(plan)] = (sec["b"], sec["h"], st)
        if cont:
            viol += 0.05 * cont
        cost = (total["concrete_m3"] * prices["concrete_per_m3"] + total["rebar_kg"] * prices["rebar_per_kg"]
                + total["formwork_m2"] * prices["formwork_per_m2"] + total["steel_kg"] * prices["steel_per_kg"])
        return {"genes": list(genes), "cost": cost, "violation": viol, "feasible": viol <= 1e-9, "quantities": total,
                "groups": groups_out, "drift_ratio": drift_ratio, "drifts": drift_rows, "continuity_violations": cont,
                "base_shear_kN": (res.get("seismic") or {}).get("V_kN"), "period_s": ((res.get("modal") or {}).get("modes") or [{}])[0].get("T") if isinstance(res.get("modal"), dict) else None}

    def _beam(self, st, b, h, Ls, seis) -> dict[str, Any]:
        M3, V2 = st[..., 5], st[..., 1]
        ends = np.concatenate([M3[:, :, :1], M3[:, :, -1:]], axis=2)
        m_neg = float(max(0.0, -ends.min())); m_pos_end = float(max(0.0, ends.max()))
        mid = M3[:, :, 1:-1] if M3.shape[2] > 2 else M3
        m_pos_mid = float(max(0.0, mid.max()))
        vu = float(np.abs(V2).max())
        r = m9.design_beam(m_neg_end=m_neg, m_pos_end=m_pos_end, m_pos_mid=m_pos_mid, vu=vu, b=b * 1000, h=h * 1000,
                           fc=self.fc, fy=self.fy, ductility=self.opt.ductility)
        dc = max(r.get("DC_flexure") or 0.0, r.get("DC_shear") or 0.0) if r.get("DC_shear") is not None else r.get("DC_flexure", 9.99)
        if r.get("status") == "FAIL" and dc <= 1.0:
            dc = 1.01  # detailing note (ρ > 2.5 %, c/d, Vs > 4Vc)
        L = sum(Ls)
        kg = 0.0
        if "As_top_mm2" in r:
            kg += (r["As_top_mm2"] + r["As_bot_mm2"]) * 1e-6 * L * STEEL_DENSITY * 1.1  # + laps/anchorage
            sh = r.get("shear") or {}
            s = max(50.0, float(sh.get("s_mid_mm") or sh.get("s_mm") or 150.0)) / 1000
            per = 2 * ((b - 0.08) + (h - 0.08)) + 0.2
            kg += (L / s) * per * m9.bar_area(m9.STIRRUP_DB) * 1e-6 * STEEL_DENSITY
        sh = r.get("shear") or {}
        return {"DC": float(dc), "rebar_kg": kg, "design": "Mabhas 9 beam", "top_bars": r.get("top_bars"),
                "bottom_bars": r.get("bottom_bars"), "stirrups": sh.get("text") or sh.get("summary"),
                "Mu_neg_kNm": m_neg, "Mu_pos_kNm": max(m_pos_end, m_pos_mid), "Vu_kN": vu, "notes": r.get("notes", [])}

    def _column(self, st, b, h, mids, Ls, cnames, seis) -> dict[str, Any]:
        recs: dict[str, list[dict]] = {}
        nc = st.shape[0]
        # keep the governing cases only (speed): max axial and max moment per member
        for j, mid in enumerate(mids[: st.shape[1]]):
            s = st[:, j]  # (cases, stations, 6)
            P = -s[:, :, 0].min(axis=1)
            M = np.abs(s[:, [0, -1], 5]).max(axis=1) / (h * 1000) + np.abs(s[:, [0, -1], 4]).max(axis=1) / (b * 1000)
            pick = sorted(set([int(np.argmax(P)), int(np.argmax(M)), int(np.argmin(P))]))
            recs[mid] = [{"combo": cnames[c], "seismic": bool(seis[c]) if seis is not None else False, "P": float(max(P[c], 0.0)),
                          "ends": [(float(abs(s[c, e, 5])), float(abs(s[c, e, 4]))) for e in (0, -1)]} for c in pick if c < nc]
        clear = max(Ls) * 1000 if Ls else 3000.0
        r = m9.design_column_group(recs, b * 1000, h * 1000, self.fc, self.fy, clear)
        kg = 0.0
        if r.get("As_mm2"):
            L = sum(Ls)
            kg += r["As_mm2"] * 1e-6 * L * STEEL_DENSITY * 1.15
            t = r.get("ties") or {}
            s = max(50.0, float(t.get("s_mm") or 150)) / 1000
            per = 2 * ((b - 0.08) + (h - 0.08)) + 0.2
            kg += (L / s) * per * m9.bar_area(m9.STIRRUP_DB) * 1e-6 * STEEL_DENSITY * 1.3
        dc = r.get("DC", 9.99)
        if r.get("status") == "FAIL" and dc <= 1.0:
            dc = 1.01
        return {"DC": float(dc), "rebar_kg": kg, "design": "Mabhas 9 column P-M", "bars": r.get("bars"), "rho": r.get("rho"),
                "ties": (r.get("ties") or {}).get("text"), "notes": r.get("notes", [])}


# ------------------------------------------------------------------ search
def _better(a: dict[str, Any], b: dict[str, Any] | None) -> bool:
    if b is None:
        return True
    if a["feasible"] != b["feasible"]:
        return a["feasible"]
    if not a["feasible"]:
        return a["violation"] < b["violation"] - 1e-9 or (abs(a["violation"] - b["violation"]) < 1e-9 and a["cost"] < b["cost"])
    return a["cost"] < b["cost"]


def optimize_model(model: dict[str, Any], lists: dict[str, Any] | None = None, options: dict[str, Any] | None = None, *,
                   progress: Callable[[dict[str, Any]], None] | None = None,
                   cancelled: Callable[[], bool] | None = None) -> dict[str, Any]:
    t0 = time.time()
    opt = Options.from_dict(options)
    lists = dict(lists or {})
    model = tag_members(prepare_model(model))
    groups = build_groups(model, lists, opt)
    ev = Evaluator(model, groups, lists, opt)
    rng = random.Random(opt.seed)
    best: dict[str, Any] | None = None
    history: list[dict[str, Any]] = []
    phase = "fsd"

    def out_of_budget() -> bool:
        return time.time() - t0 > opt.time_budget_s or ev.evals >= opt.max_evals

    def run(genes: list[int]) -> dict[str, Any]:
        nonlocal best
        if cancelled and cancelled():
            raise Cancelled()
        r = ev.evaluate(genes)
        if _better(r, best):
            best = r
        history.append({"eval": ev.evals, "cost": r["cost"], "feasible": r["feasible"], "best": best["cost"]})
        if progress:
            frac = min(0.99, max((time.time() - t0) / opt.time_budget_s, ev.evals / opt.max_evals))
            progress({"fraction": frac, "phase": phase, "evals": ev.evals, "best_cost": best["cost"],
                      "best_feasible": best["feasible"], "elapsed_s": round(time.time() - t0, 1)})
        return r

    status = "done"
    initial = None
    try:
        genes = ev.initial_genes()
        initial = run(genes)
        # 1) fully stressed design
        for _ in range(25):
            if out_of_budget():
                break
            cur = ev.evaluate(genes)
            new = list(genes)
            drift_bad = cur["drift_ratio"] > 1.0
            for k, info in enumerate(cur["groups"]):
                n = len(ev.names[k])
                dc = info.get("DC", 0.0)
                if dc > 1.0 or info.get("deflection_ok") is False:
                    new[k] = min(n - 1, genes[k] + (2 if dc > 1.5 else 1))
                elif drift_bad and groups[k]["type"] in ("column", "beam"):
                    new[k] = min(n - 1, genes[k] + 1)
                elif not drift_bad and dc < 0.55 and cur["drift_ratio"] < 0.85:
                    new[k] = max(0, genes[k] - 1)
            if new == genes:
                break
            genes = new
            run(genes)
        # 2) greedy down-sizing from the best feasible
        phase = "greedy"
        improved = True
        while improved and not out_of_budget() and best is not None:
            improved = False
            base = list(best["genes"])
            order = sorted(range(len(groups)), key=lambda k: -best["groups"][k].get("rebar_kg", 0) - best["groups"][k].get("steel_kg", 0))
            for k in order:
                if out_of_budget() or base[k] == 0:
                    continue
                trial = list(base); trial[k] -= 1
                before = best
                run(trial)
                if best is not before and best["feasible"]:
                    base = list(best["genes"]); improved = True
        # 3) stochastic local search (if infeasible: also up-sizing moves)
        phase = "search"
        while not out_of_budget() and best is not None:
            trial = list(best["genes"])
            for _ in range(rng.choice((1, 1, 2, 3))):
                k = rng.randrange(len(groups))
                step = rng.choice((-1, -1, 1)) if best["feasible"] else rng.choice((1, 1, -1))
                trial[k] = min(len(ev.names[k]) - 1, max(0, trial[k] + step))
            if tuple(trial) in ev.cache:
                if len(ev.cache) > 50 and rng.random() < 0.05:
                    break
                continue
            run(trial)
    except Cancelled:
        status = "cancelled"
    assert best is not None or status == "cancelled"
    res = best or {}
    assign = ev.assignment(res["genes"]) if res else {}
    return {"status": status, "feasible": bool(res.get("feasible")), "cost": res.get("cost"), "currency": opt.prices.get("currency", "تومان"),
            "initial_cost": initial["cost"] if initial else None, "initial_feasible": initial["feasible"] if initial else None,
            "evaluations": ev.evals, "elapsed_s": round(time.time() - t0, 1), "quantities": res.get("quantities"),
            "groups": res.get("groups", []), "drift_ratio": res.get("drift_ratio"), "drifts": res.get("drifts", []),
            "continuity_violations": res.get("continuity_violations"), "base_shear_kN": res.get("base_shear_kN"),
            "assignment": assign, "history": history[-200:],
            "settings": {"time_budget_s": opt.time_budget_s, "max_evals": opt.max_evals, "storey_band": opt.storey_band,
                         "fc_mpa": ev.fc, "fy_mpa": ev.fy, "steel_fy_mpa": ev.fy_steel, "rebar_mm": sorted(set(ev.beam_bars) | set(ev.col_bars)),
                         "prices": opt.prices, "ductility": opt.ductility, "groups": len(groups)},
            "assumptions": _assumptions(lists, opt)}


def _assumptions(lists: dict[str, Any], opt: Options) -> list[str]:
    a = []
    if not lists.get("columns"):
        a.append("فهرست مقاطع ستون داده نشد: مقاطع مستطیلی ۳۰ تا ۸۰ سانتی‌متر (و پروفیل‌های HEB برای فولادی) فرض شد.")
    if not lists.get("beams"):
        a.append("فهرست مقاطع تیر داده نشد: مقاطع مستطیلی پیش‌فرض (و IPE برای فولادی) فرض شد.")
    if not lists.get("rebar_mm"):
        a.append("قطر میلگردها داده نشد: Φ12 تا Φ32 فرض شد؛ خاموت/تنگ Φ10.")
    mat = lists.get("materials") or {}
    if not mat.get("fc_mpa"):
        a.append("مقاومت بتن داده نشد: fc = 30 MPa فرض شد.")
    if not mat.get("fy_mpa"):
        a.append("رده میلگرد داده نشد: fy = 400 MPa (AIII) فرض شد.")
    a.append(f"گروه‌بندی پیش‌فرض: هر {opt.storey_band} طبقه، بر اساس موقعیت (گوشه/کناری/میانی) و جهت تیر؛ تیپ‌های تعریف‌شده در گفتگو اولویت دارند.")
    a.append("قیود: طراحی مبحث ۹ (خمش/برش تیر، P-M ستون)، دریفت استاندارد ۲۸۰۰، ارتفاع تیر ≥ L/21، ستون بالایی بزرگ‌تر از پایینی نباشد.")
    a.append("هزینه = بتن + میلگرد (با ۱۰–۱۵٪ وصله) + قالب + فولاد؛ قیمت‌ها قابل تغییرند.")
    return a
