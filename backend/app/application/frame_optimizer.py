"""Section optimization engine for the in-house 3D RC frame (analysis -> design -> re-analysis).

Stage 1 - fully-stressed design (FSD): per-storey beam/column groups are resized from a discrete catalogue,
          the whole 3D frame is re-analysed after every resize (stiffness and self-weight change the forces and
          drift), and the loop repeats until no group changes (or a cycle / iteration cap is hit).
Stage 2 - discrete genetic algorithm (GA) seeded with the FSD result: minimises cost (concrete + rebar +
          formwork, configurable toman prices) or weight, subject to Mabhas 9 strength (beams + columns),
          Standard 2800 drift and a span/depth deflection rule; constructability (column above <= column
          below, beam width <= column width) is enforced by repair. Deterministic seed, evaluation + time budget.

Every evaluated design is a full re-analysis with frame3d_chat_analysis.run_frame3d + design_mabhas9.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import asdict, replace
from typing import Any

from app.application import frame3d_chat_analysis as f3

DEFAULT_PRICES_TOMAN = {"concrete_m3": 4_500_000, "rebar_kg": 45_000, "formwork_m2": 900_000}
STEEL_DENSITY = 7850.0
CONCRETE_DENSITY = 2400.0
STIRRUP_FACTOR = 1.15  # +15 % for stirrups / ties / laps on top of longitudinal steel
COLUMN_SIZES = [round(0.30 + 0.05 * i, 2) for i in range(11)]  # 30..80 cm square
BEAM_SIZES = [(b, h) for b in (0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)
              for h in (0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75) if b <= h <= 2.5 * b]
BEAM_SIZES.sort(key=lambda s: (s[0] * s[1], s[1]))
PENALTY = 3.0  # cost multiplier per unit of total constraint violation


# ----------------------------------------------------------------------------- helpers
def _snap_col(b: float) -> int:
    return min(range(len(COLUMN_SIZES)), key=lambda i: (abs(COLUMN_SIZES[i] - b), -i))


def _snap_beam(b: float, h: float) -> int:
    return min(range(len(BEAM_SIZES)), key=lambda i: (abs(BEAM_SIZES[i][0] - b) + abs(BEAM_SIZES[i][1] - h), i))


class _Problem:
    def __init__(self, inp: f3.Frame3dInputs, opts: dict[str, Any]):
        self.inp = inp
        self.ns = int(inp.storeys)
        self.group_n = max(1, int(opts.get("group_storeys") or (2 if self.ns >= 6 else 1)))
        self.ngroups = math.ceil(self.ns / self.group_n)
        self.objective = "weight" if str(opts.get("objective", "cost")).lower().startswith("w") else "cost"
        self.prices = {**DEFAULT_PRICES_TOMAN, **{k: float(v) for k, v in (opts.get("prices") or {}).items() if k in DEFAULT_PRICES_TOMAN}}
        self.col_rho_max = float(opts.get("max_column_rho", 0.04))
        self.beam_rho_max = float(opts.get("max_beam_rho", 0.025))
        self.cache: dict[tuple, dict[str, Any]] = {}
        self.evaluations = 0

    # genes: (col_idx_g0, ..., col_idx_gN, beam_idx_g0, ..., beam_idx_gN); group g covers storeys g*n+1 .. (g+1)*n
    def storeys_of(self, g: int) -> range:
        return range(g * self.group_n + 1, min((g + 1) * self.group_n, self.ns) + 1)

    def group_label(self, kind: str, g: int) -> str:
        s = list(self.storeys_of(g))
        return f"{kind}-S{s[0]}" if len(s) == 1 else f"{kind}-S{s[0]}-{s[-1]}"

    def sections(self, genes: tuple) -> dict[str, list[float]]:
        out = {}
        for g in range(self.ngroups):
            c = COLUMN_SIZES[genes[g]]; b = BEAM_SIZES[genes[self.ngroups + g]]
            for k in self.storeys_of(g):
                out[f"C{k}"] = [c, c]; out[f"B{k}"] = [b[0], b[1]]
        return out

    def repair(self, genes: list[int]) -> tuple:
        """Constructability: column above <= column below; beam width <= column width (raise the column)."""
        n = self.ngroups
        genes = list(genes)
        for g in range(n):
            bw = BEAM_SIZES[genes[n + g]][0]
            while COLUMN_SIZES[genes[g]] + 1e-9 < bw and genes[g] < len(COLUMN_SIZES) - 1:
                genes[g] += 1
        for g in range(n - 2, -1, -1):
            genes[g] = max(genes[g], genes[g + 1])
        return tuple(genes)

    # ------------------------------------------------------------------ evaluation (= full re-analysis)
    def evaluate(self, genes: tuple) -> dict[str, Any]:
        genes = tuple(genes)
        if genes in self.cache:
            return self.cache[genes]
        self.evaluations += 1
        inp = replace(self.inp, group_sections=self.sections(genes), parsed=list(self.inp.parsed))
        raw = f3.run_frame3d(inp, with_modal=False, with_foundation=False)
        design = f3.design_mabhas9(inp, raw)
        ev = self._score(genes, inp, raw, design)
        self.cache[genes] = ev
        return ev

    def _score(self, genes, inp, raw, design) -> dict[str, Any]:
        n, ns = self.ngroups, self.ns
        H = inp.storey_height_m
        g_of = {k: (k - 1) // self.group_n for k in range(1, ns + 1)}
        util: dict[str, dict[str, float]] = {self.group_label(t, g): {} for t in ("C", "B") for g in range(n)}

        def put(label, key, val):
            val = 9.99 if not math.isfinite(val) else val
            util[label][key] = max(util[label].get(key, 0.0), val)

        steel_kg = 0.0
        concrete = form = 0.0
        for row in design.get("beams") or []:
            k = row["storey"]; lab = self.group_label("B", g_of[k])
            b, h = f3.beam_dims(inp, k)
            d = h - 0.06
            L = inp.bay_x_m if row["direction"] == "X" else inp.bay_y_m
            rho = (row.get("As_top_req_mm2") or 0) / (b * d * 1e6) if b * d > 0 else 9.99
            put(lab, "strength (Mabhas 9 flexure)", rho / self.beam_rho_max)
            put(lab, "shear (Mabhas 9)", row.get("DC_shear") or 0.0)
            if row["status"] != "PASS":
                put(lab, "strength (Mabhas 9 flexure)", 1.05 if row.get("DC_flexure") is not None and math.isfinite(row["DC_flexure"]) else 9.99)
            # deflection: Mabhas 9 minimum depth without deflection calculation (one end continuous L/18.5, both L/21)
            hmin = L / (18.5 if row["position"] == "edge" else 21.0) * (0.4 + inp.fy_mpa / 700.0)
            put(lab, "deflection (span/depth)", hmin / h)
            As = (row.get("As_top_req_mm2") or 0) + (row.get("As_bot_req_mm2") or 0)
            steel_kg += As * 1e-6 * L * STEEL_DENSITY * STIRRUP_FACTOR * row["members"]
            concrete += b * max(h - inp.slab_t_m, 0.0) * L * row["members"]
            form += (b + 2 * max(h - inp.slab_t_m, 0.0)) * L * row["members"]
        for row in design.get("columns") or []:
            k = row["storey"]; lab = self.group_label("C", g_of[k])
            b, h = f3.column_dims(inp, k)
            rho = (row.get("rho_pct") or 0) / 100.0
            put(lab, "strength (Mabhas 9 P-M)", rho / self.col_rho_max)
            if row["status"] != "PASS":
                put(lab, "strength (Mabhas 9 P-M)", 9.99)
            Ag = b * h
            steel_kg += max(rho, 0.01) * Ag * H * STEEL_DENSITY * STIRRUP_FACTOR * row["members"]
            concrete += Ag * H * row["members"]
            form += 2 * (b + h) * H * row["members"]
        limit = (raw.get("seismic") or {}).get("drift_limit") or 0.025
        for dr in raw.get("drift") or []:
            g = g_of[dr["storey"]]
            r = dr["ratio_amplified"] / limit
            put(self.group_label("C", g), "drift (Standard 2800)", r)
            put(self.group_label("B", g), "drift (Standard 2800)", r)
        if design.get("ductility") == "special":
            for j in design.get("scwb") or []:
                put(self.group_label("C", g_of[j["level"]]), "strong column/weak beam", 1.2 / max(j["min_ratio"], 1e-6))
        governing = {lab: (max(u.items(), key=lambda kv: kv[1]) if u else ("-", 0.0)) for lab, u in util.items()}
        violation = sum(max(0.0, v - 1.0) for u in util.values() for v in u.values())
        cost = concrete * self.prices["concrete_m3"] + steel_kg * self.prices["rebar_kg"] + form * self.prices["formwork_m2"]
        weight = concrete * CONCRETE_DENSITY + steel_kg
        obj = cost if self.objective == "cost" else weight
        return {"genes": genes, "feasible": violation <= 1e-9, "violation": violation, "objective": obj,
                "fitness": obj * (1.0 + PENALTY * violation) + (obj * 0.5 if violation > 0 else 0.0),
                "cost_toman": cost, "weight_kg": weight, "concrete_m3": concrete, "rebar_kg": steel_kg, "formwork_m2": form,
                "utilization": util, "governing": governing,
                "max_drift_ratio": max((d["ratio_amplified"] for d in raw.get("drift") or []), default=0.0), "drift_limit": limit}


# ----------------------------------------------------------------------------- stage 1: FSD loop
def _fsd(p: _Problem, start: tuple, max_iter: int, deadline: float) -> tuple[tuple, list[dict[str, Any]]]:
    n = p.ngroups
    genes = p.repair(start)
    history, seen = [], set()
    best = None
    for it in range(1, max_iter + 1):
        ev = p.evaluate(genes)
        history.append({"iteration": it, "objective": ev["objective"], "feasible": ev["feasible"], "violation": round(ev["violation"], 4)})
        if ev["feasible"] and (best is None or ev["objective"] < best["objective"]):
            best = ev
        seen.add(genes)
        new = list(genes)
        for g in range(n):
            for t, idx in (("C", g), ("B", n + g)):
                u = max(ev["utilization"][p.group_label(t, g)].values(), default=0.0)
                size = len(COLUMN_SIZES) if t == "C" else len(BEAM_SIZES)
                if u > 1.0:
                    step = 1 if u < 1.15 else 2 if u < 1.5 else 3
                    new[idx] = min(size - 1, new[idx] + step)
                elif u < 0.70:
                    new[idx] = max(0, new[idx] - 1)
        new_t = p.repair(new)
        if new_t == genes or new_t in seen or time.monotonic() > deadline:
            break
        genes = new_t
    return (best or p.evaluate(genes))["genes"], history


# ----------------------------------------------------------------------------- stage 2: GA
def _ga(p: _Problem, seed_genes: tuple, rng: random.Random, max_evals: int, deadline: float, pop_size: int = 16,
        generations: int = 40) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    n2 = 2 * p.ngroups
    sizes = [len(COLUMN_SIZES)] * p.ngroups + [len(BEAM_SIZES)] * p.ngroups

    def mutate(g, rate):
        g = list(g)
        for i in range(n2):
            if rng.random() < rate:
                g[i] = min(sizes[i] - 1, max(0, g[i] + rng.choice((-2, -1, -1, 1, 1, 2))))
        return p.repair(g)

    pop = [p.repair(seed_genes)] + [mutate(seed_genes, 0.5) for _ in range(pop_size - 1)]
    best = min((p.evaluate(x) for x in pop), key=lambda e: e["fitness"])
    curve = [{"generation": 0, "best_objective": best["objective"], "feasible": best["feasible"], "evaluations": p.evaluations}]
    stall = 0
    for gen in range(1, generations + 1):
        if p.evaluations >= max_evals or time.monotonic() > deadline:
            break
        scored = sorted((p.evaluate(x) for x in pop), key=lambda e: e["fitness"])
        elite = [e["genes"] for e in scored[:2]]

        def pick():
            a, b = rng.sample(scored, 2)
            return (a if a["fitness"] <= b["fitness"] else b)["genes"]

        nxt = list(elite)
        while len(nxt) < pop_size:
            pa, pb = pick(), pick()
            child = [pa[i] if rng.random() < 0.5 else pb[i] for i in range(n2)]
            nxt.append(mutate(child, 1.5 / n2))
        pop = nxt
        gb = min((p.evaluate(x) for x in pop), key=lambda e: e["fitness"])
        if gb["fitness"] < best["fitness"] - 1e-9:
            best, stall = gb, 0
        else:
            stall += 1
        curve.append({"generation": gen, "best_objective": best["objective"], "feasible": best["feasible"], "evaluations": p.evaluations})
        if stall >= 10:
            break
    return best, curve


# ----------------------------------------------------------------------------- public API
def optimize_frame(inp: f3.Frame3dInputs, options: dict[str, Any] | None = None) -> dict[str, Any]:
    opts = dict(options or {})
    t0 = time.monotonic()
    deadline = t0 + float(opts.get("time_budget_s", 40))
    max_evals = int(opts.get("max_evaluations", 300))
    rng = random.Random(int(opts.get("seed", 2026)))
    inp = replace(inp, design_code="MABHAS9", group_sections=None, parsed=list(inp.parsed))
    p = _Problem(inp, opts)
    n = p.ngroups
    initial_genes = tuple([_snap_col(max(inp.column_b_m, inp.column_h_m))] * n + [_snap_beam(inp.beam_b_m, inp.beam_h_m)] * n)
    initial = p.evaluate(initial_genes)
    fsd_genes, fsd_hist = _fsd(p, initial_genes, int(opts.get("fsd_max_iterations", 12)), deadline)
    fsd = p.evaluate(fsd_genes)
    if opts.get("ga", True):
        ga_best, ga_curve = _ga(p, fsd_genes, rng, max_evals, deadline)
    else:
        ga_best, ga_curve = fsd, []
    best = min((e for e in (ga_best, fsd) if e["feasible"]), key=lambda e: e["objective"], default=min((ga_best, fsd), key=lambda e: e["fitness"]))
    unit = "toman" if p.objective == "cost" else "kg"

    def sec_table(ev):
        rows = []
        for g in range(n):
            c = COLUMN_SIZES[ev["genes"][g]]; b = BEAM_SIZES[ev["genes"][n + g]]
            for t, txt in (("C", f"{c*100:g}x{c*100:g}"), ("B", f"{b[0]*100:g}x{b[1]*100:g}")):
                lab = p.group_label(t, g); gk, gv = ev["governing"][lab]
                if t == "C" and gv < 0.6 and g < n - 1 and ev["genes"][g] == ev["genes"][g + 1]:
                    gk = "constructability (column above ≤ column below)"
                if t == "C" and gv < 0.6 and ev["genes"][g] == 0:
                    gk = "minimum catalogue section"
                if t == "B" and gv < 0.6 and ev["genes"][n + g] == 0:
                    gk = "minimum catalogue section"
                elif t == "C" and gv < 0.6 and COLUMN_SIZES[ev["genes"][g]] <= BEAM_SIZES[ev["genes"][n + g]][0] + 1e-9:
                    gk = "constructability (beam width ≤ column width)"
                rows.append({"group": lab, "type": "column" if t == "C" else "beam", "storeys": list(p.storeys_of(g)),
                             "section_cm": txt, "governing_constraint": gk, "utilization": round(gv, 3)})
        return rows

    init_rows = {r["group"]: r["section_cm"] for r in sec_table(initial)}
    groups = [{**r, "initial_section_cm": init_rows[r["group"]]} for r in sec_table(best)]
    ref = initial if initial["feasible"] else fsd
    savings = (ref["objective"] - best["objective"]) / ref["objective"] * 100 if ref["objective"] else 0.0

    def summ(ev):
        return {"objective": round(ev["objective"]), "cost_toman": round(ev["cost_toman"]), "weight_kg": round(ev["weight_kg"]),
                "concrete_m3": round(ev["concrete_m3"], 2), "rebar_kg": round(ev["rebar_kg"]), "formwork_m2": round(ev["formwork_m2"], 1),
                "feasible": ev["feasible"], "violation": round(ev["violation"], 3), "max_drift_ratio": round(ev["max_drift_ratio"], 5)}

    return {
        "kind": "frame_optimization", "status": "completed" if best["feasible"] else "NO_FEASIBLE_DESIGN",
        "method": {"stage1": "Fully-stressed design loop: resize groups -> full 3D re-analysis -> Mabhas 9 design, until no change",
                   "stage2": "Discrete genetic algorithm (tournament, uniform crossover, ±step mutation, elitism) seeded with the stage-1 result",
                   "objective": p.objective, "seed": int(opts.get("seed", 2026)), "group_storeys": p.group_n,
                   "constraints": ["Mabhas 9 beam flexure/shear (ρ ≤ %.3f)" % p.beam_rho_max, "Mabhas 9 column P-M (ρ ≤ %.2f)" % p.col_rho_max,
                                   "Standard 2800 drift ≤ %.4f" % initial["drift_limit"], "Deflection: Mabhas 9 min depth L/18.5 (edge), L/21 (interior)"],
                   "constructability": ["column above ≤ column below", "beam width ≤ column width"],
                   "prices_toman": p.prices, "catalogue": {"columns_cm": [round(c * 100) for c in COLUMN_SIZES],
                                                         "beams_cm": [f"{b*100:g}x{h*100:g}" for b, h in BEAM_SIZES]}},
        "objective_unit": unit, "initial": summ(initial), "fsd": summ(fsd), "optimal": summ(best),
        "savings_pct": round(savings, 1), "drift_limit": initial["drift_limit"], "savings_reference": "initial" if ref is initial else "fsd",
        "groups": groups, "group_sections": p.sections(best["genes"]),
        "convergence": {"fsd": fsd_hist, "ga": ga_curve},
        "evaluations": p.evaluations, "elapsed_s": round(time.monotonic() - t0, 1),
        "frame": {k: v for k, v in asdict(inp).items() if k in ("storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m", "storey_height_m", "fc_mpa", "fy_mpa", "seismic_code", "zone", "soil", "system")},
        "limits": ["Square columns and one beam section per storey group (all beams of a storey share a section)",
                   "Rebar quantity from required steel areas + 15 % for stirrups/laps (not a bar-by-bar take-off)",
                   "Drift from the equivalent static 2800 loads (modal check not repeated inside the loop)",
                   "Unit prices are editable defaults, not a quotation", "Engineer review required before use"],
    }


# ----------------------------------------------------------------------------- chat
import re  # noqa: E402

_OPT_RE = re.compile(r"optimi[sz]|بهینه|cheapest|most economical|اقتصادی ?ترین|کمترین هزینه", re.I)


def text_lang(text: str) -> str:
    """fa/en of a message; the Arabic semicolon the follow-up merger inserts does not count as Persian."""
    t = (text or "").replace("\u061b", " ")
    return "fa" if any("\u0600" <= ch <= "\u06ff" for ch in t) else "en"


def is_optimize_request(text: str) -> bool:
    return bool(_OPT_RE.search(text or ""))


def options_from_text(text: str) -> dict[str, Any]:
    t = f3._norm(text).lower()
    opts: dict[str, Any] = {}
    if re.search(r"weight|وزن", t):
        opts["objective"] = "weight"
    for key, pat in (("concrete_m3", r"(?:concrete|بتن)[^\d]{0,25}(\d[\d,]*)"), ("rebar_kg", r"(?:rebar|steel|میلگرد|آرماتور)[^\d]{0,25}(\d[\d,]*)"),
                     ("formwork_m2", r"(?:formwork|قالب)[^\d]{0,25}(\d[\d,]*)")):
        m = re.search(pat, t)
        if m and re.search(r"price|قیمت|toman|تومان", t):
            opts.setdefault("prices", {})[key] = float(m.group(1).replace(",", ""))
    return opts


def _fmt(v: float) -> str:
    return f"{v:,.0f}"


def optimization_markdown(res: dict[str, Any], lang: str = "en") -> str:
    fa = lang == "fa"
    unit = ("تومان" if fa else "toman") if res["objective_unit"] == "toman" else "kg"
    i, o = res["initial"], res["optimal"]
    if fa:
        lines = ["### بهینه‌سازی قاب (تحلیل ← طراحی ← تحلیل مجدد + الگوریتم ژنتیک)",
                 f"- هدف: {'هزینه' if res['method']['objective']=='cost' else 'وزن'} | ارزیابی‌ها: {res['evaluations']} تحلیل کامل | زمان: {res['elapsed_s']} ثانیه",
                 f"- طرح اولیه: **{_fmt(i['objective'])} {unit}** ({'قابل قبول' if i['feasible'] else 'ناموفق در کنترل‌ها'})",
                 f"- طرح بهینه: **{_fmt(o['objective'])} {unit}** — صرفه‌جویی **{res['savings_pct']}%**",
                 f"- دریفت حداکثر: {o['max_drift_ratio']:.4f} | بتن {o['concrete_m3']} m³ | میلگرد {_fmt(o['rebar_kg'])} kg | قالب {o['formwork_m2']} m²",
                 "", "| گروه | اولیه (cm) | بهینه (cm) | کنترل حاکم | نسبت |", "|---|---|---|---|---|"]
    else:
        lines = ["### Frame optimization (analysis → design → re-analysis + genetic algorithm)",
                 f"- Objective: {res['method']['objective']} | evaluations: {res['evaluations']} full re-analyses | time: {res['elapsed_s']} s",
                 f"- Initial design: **{_fmt(i['objective'])} {unit}** ({'feasible' if i['feasible'] else 'fails checks'})",
                 f"- Optimal design: **{_fmt(o['objective'])} {unit}** — savings **{res['savings_pct']}%**",
                 f"- Max drift: {o['max_drift_ratio']:.4f} (limit {res['drift_limit']:.4f}) | concrete {o['concrete_m3']} m³ | rebar {_fmt(o['rebar_kg'])} kg | formwork {o['formwork_m2']} m²",
                 "", "| Group | Initial (cm) | Optimal (cm) | Governing | Ratio |", "|---|---|---|---|---|"]
    for g in res["groups"]:
        lines.append(f"| {g['group']} | {g['initial_section_cm']} | {g['section_cm']} | {g['governing_constraint']} | {g['utilization']} |")
    if res.get("assumed_defaults"):
        used = ", ".join(f"{k}={v}" for k, v in (res.get("inputs_used") or {}).items())
        lines.append("")
        lines.append((f"فرض‌های پیش‌فرض (چون ورودی ناقص بود): {used}. هر مقدار را می‌توانید در چت تغییر دهید." if fa
                      else f"Assumed defaults (inputs were missing): {used}. Change any value in chat and I will re-run."))
    if res["status"] != "completed":
        lines.append("⚠️ " + ("هیچ طرح قابل قبولی در کاتالوگ پیدا نشد؛ ابعاد یا سیستم را بازبینی کنید." if fa else "No feasible design was found in the catalogue; review the system or dimensions."))
    lines.append("")
    lines.append(("نمودار همگرایی و گزارش کامل در صفحه‌ی Optimization است. نتایج نیاز به بازبینی مهندس دارد." if fa else
                  "Convergence chart and full report are on the Optimization page. Engineer review required."))
    return "\n".join(lines)


def build_optimization_from_chat(text: str, prior_spec: dict[str, Any] | None, options: dict[str, Any] | None = None,
                                 assume_defaults: bool = False) -> dict[str, Any] | None:
    """Optimize the described / last frame. With ``assume_defaults`` (or an «assume defaults» wording in the text)
    missing geometry is filled with the documented defaults and listed in ``assumed_defaults``."""
    from app.application import frame3d_followup as fu

    assume = assume_defaults or fu.is_assume_reply(text)
    assumed: list[str] = []
    if f3.is_frame3d_request(text):
        inp = f3.parse_frame3d_request(text)
    elif prior_spec:
        inp = f3.inputs_from_dict(prior_spec)
    elif assume:
        inp = f3.parse_frame3d_request(text)
    else:
        return None
    if f3.missing_inputs(inp):
        if not assume:
            return None
        assumed = fu.apply_defaults(inp)
        if f3.missing_inputs(inp):
            return None
    if inp.storeys > f3.MAX_STOREYS or max(inp.bays_x, inp.bays_y) > f3.MAX_BAYS:
        return None
    inp.lang = text_lang(text)
    res = optimize_frame(inp, {**options_from_text(text), **(options or {})})
    if assumed:
        res["assumed_defaults"] = assumed
        res["inputs_used"] = {k: getattr(inp, k) for k in assumed if hasattr(inp, k)}
    return res


def pending_optimize_text(text: str, previous_user_texts: list[str]) -> str | None:
    """The text to optimize: the message itself, or (for «assume defaults» replies to the checklist)
    the previous optimize request merged with the reply. None when this is not an optimization turn."""
    from app.application import frame3d_followup as fu

    if is_optimize_request(text):
        return text
    if fu.is_assume_reply(text):
        for prev in (previous_user_texts or [])[:2]:
            if prev and prev.strip() != (text or "").strip():
                if is_optimize_request(prev):
                    return f"{prev} ; {text}"
                break
    return None


def missing_frame_checklist(text: str) -> str:
    """Replaces the vague 'describe the frame first': a per-step checklist with the exact fix for each step."""
    from app.application import optimization_checklist as oc

    fa = text_lang(text) == "fa"
    partial: list[str] = []
    if f3.is_frame3d_request(text):
        partial = f3.missing_inputs(f3.parse_frame3d_request(text))
    return oc.checklist_markdown(oc.checklist_for_chat(has_frame=False, partial_missing=partial), "fa" if fa else "en")


def prior_spec_from_texts(texts: list[str]) -> dict[str, Any] | None:
    """Latest frame described in earlier chat messages (newest first) as a re-parseable spec."""
    import json
    for t in texts:
        if t and f3.is_frame3d_request(t):
            inp = f3.parse_frame3d_request(t)
            if not f3.missing_inputs(inp):
                return json.loads(f3.frame3d_spec(inp)[len(f3.SPEC_TAG):])
    return None


def missing_frame_message(text: str) -> str:
    if any("\u0600" <= ch <= "\u06ff" for ch in text or ""):
        return ("برای بهینه‌سازی، اول قاب را توصیف کنید یا در همین پیام بنویسید، مثلاً: "
                "«قاب ۳ طبقه با ۲x۲ دهانه ۵ متر، پهنه خطر زیاد، خاک II را بهینه کن». "
                "می‌توانید هدف (هزینه یا وزن) و قیمت بتن/میلگرد/قالب را هم بدهید.")
    return ("To optimize, describe the frame first or in the same message, e.g. "
            "`optimize a 3-storey frame, 2x2 bays of 5 m, zone high, soil II`. "
            "You can set the objective (cost or weight) and concrete/rebar/formwork prices.")
