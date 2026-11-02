"""Analysis of an imported model: gravity, Standard 2800 seismic, wind, P-Delta, modal, response spectrum,
story drifts and preliminary member design. Every number is produced by ``engine.FrameEngine``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from app.application import iran2800 as s2800
from app.application.model_import.engine import G_ACC, EngineError, FrameEngine, cqc
from app.application.model_import.slabs import distribute_model

DEFAULT_CONCRETE = {"type": "Concrete", "E": 2.35e7, "nu": 0.2, "unit_weight": 25.0}
MAX_CASE_MEMBERS = 1500


def _kind(ptype: str, name: str) -> str:
    t = (ptype or "").lower()
    if t.startswith(("dead", "super")):
        return "D"
    if "live" in t:
        return "L"
    if t in ("seismic", "quake", "earthquake") or t.startswith("seism"):
        return "E"
    if t.startswith("wind"):
        return "W"
    n = name.lower()
    if n.startswith(("dead", "sdead", "super")):
        return "D"
    if n.startswith("live"):
        return "L"
    return "O"


def _dir(name: str) -> str:
    n = name.upper().replace("(", " ")
    return "Y" if ("Y" in n.split()[0][1:] or n.startswith(("EY", "QY", "WY", "SY")) or n.endswith("Y")) else "X"


def _f(v: float) -> float:
    return float(f"{v:.9g}")


def _levels(z: np.ndarray, tol: float = 0.05) -> list[float]:
    out: list[float] = []
    for v in sorted(z):
        if not out or v - out[-1] > tol:
            out.append(float(v))
    return out


def analyze_imported_model(model: dict[str, Any]) -> dict[str, Any]:
    from app.application.model_import.analyze import review_summary

    summary = review_summary(model)
    if not summary["can_analyze"]:
        raise ValueError("Resolve the blocking review items before analysis.")
    opts = model.get("analysis") or {}
    notes: list[str] = []
    assumptions = list(model.get("assumptions", []))

    def assume(en: str, fa: str) -> None:
        assumptions.append({"en": en, "fa": fa})

    used = sorted({m["i"] for m in model["members"]} | {m["j"] for m in model["members"]})
    nodes = [(n, model["nodes"][n]["x"], model["nodes"][n]["y"], model["nodes"][n]["z"]) for n in used]
    nidx = {n: k for k, n in enumerate(used)}
    xyz = np.array([[x, y, z] for _, x, y, z in nodes])

    # ---- elements --------------------------------------------------------------------------
    els, selfw, mtype = [], {}, {}
    for mem in model["members"]:
        sec = model["sections"][mem["section"]]
        mat = model["materials"].get(sec.get("material")) or DEFAULT_CONCRETE
        mod = sec.get("modifiers") or {}
        p = {k: (sec.get(k) or 0.0) * (mod.get(k) or 1.0) for k in ("A", "I33", "I22", "J")}
        if p["I33"] <= 0 or p["I22"] <= 0:
            raise ValueError(f"Section {mem['section']} needs positive I33 and I22.")
        if p["J"] <= 0:
            p["J"] = 1e-3 * min(p["I33"], p["I22"])
            notes.append(f"Section {mem['section']}: J missing, a small torsion constant was used.")
        els.append({"id": mem["id"], "i": mem["i"], "j": mem["j"], "E": mat["E"], "nu": mat.get("nu") or 0.2, **p,
                    "rel_i": mem.get("rel_i"), "rel_j": mem.get("rel_j")})
        selfw[mem["id"]] = (sec.get("A") or 0.0) * (mat.get("unit_weight") or 0.0)
        mtype[mem["id"]] = str(mat.get("type") or "").lower()
    lengths = {m["id"]: float(np.linalg.norm(xyz[nidx[m["j"]]] - xyz[nidx[m["i"]]])) for m in model["members"]}

    pats = dict(model["load_patterns"])
    kinds = {p: _kind(v.get("type", ""), p) for p, v in pats.items()}

    # ---- gravity loads per pattern (members, slabs, nodes) ------------------------------------------
    slab_segs, slab_nodal, slab_report = distribute_model(model, list(pats))
    if slab_report:
        ow = sum(1 for r in slab_report if r["one_way"])
        notes.append(f"{len(slab_report)} slabs distributed to beams ({ow} one-way, {len(slab_report) - ow} two-way).")
        tn = [r["area"] for r in slab_report if r["to_nodes"]]
        if tn:
            notes.append(f"{len(tn)} slabs had no supporting beams in their plane - their load went to the slab corner nodes.")

    def segs_of(pat: str) -> tuple[dict[str, list], list[dict[str, Any]]]:
        segs: dict[str, list] = {}
        sw = pats.get(pat, {}).get("self_weight") or 0.0
        if sw:
            for mid, w in selfw.items():
                if w:
                    segs.setdefault(mid, []).append((0.0, lengths[mid], [0.0, 0.0, -sw * w]))
        for ld in model["member_loads"]:
            if ld["pattern"] == pat and ld["member"] in lengths:
                L = lengths[ld["member"]]
                a, b = ld.get("ra", 0.0) * L, ld.get("rb", 1.0) * L
                if "a" in ld:
                    a, b = ld["a"], ld["b"]
                segs.setdefault(ld["member"], []).append((a, b, [ld.get("wx", 0.0), ld.get("wy", 0.0), ld.get("wz", 0.0)]))
        for mid, ss in slab_segs.get(pat, {}).items():
            segs.setdefault(mid, []).extend(ss)
        nl = [ld for ld in model["nodal_loads"] if ld["pattern"] == pat and ld["node"] in nidx] + slab_nodal.get(pat, [])
        return segs, nl

    loads = {p: segs_of(p) for p in pats}

    # ---- seismic weight (D + 0.2 L) lumped to nodes -------------------------------------------------
    weight = np.zeros(len(used))
    memi = _mem_index(model)
    for p, (segs, nl) in loads.items():
        f = 1.0 if kinds[p] == "D" else 0.2 if kinds[p] == "L" else 0.0
        if not f:
            continue
        for mid, ss in segs.items():
            mem = memi[mid]
            L = lengths[mid]
            for a, b, w in ss:
                W = -w[2] * (b - a) * f
                c = (a + b) / 2 / L if L else 0.5
                weight[nidx[mem["i"]]] += W * (1 - c)
                weight[nidx[mem["j"]]] += W * c
        for ld in nl:
            weight[nidx[ld["node"]]] += -ld.get("fz", 0.0) * f
    sup_nodes = {n for n, fl in model["supports"].items() if any(fl) and n in nidx}
    for n in sup_nodes:
        weight[nidx[n]] = 0.0
    weight = np.maximum(weight, 0.0)
    W_total = float(weight.sum())
    mass = {used[k]: weight[k] / G_ACC for k in range(len(used)) if weight[k] > 0}

    # ---- diaphragms ------------------------------------------------------------------------------
    diaph = [{"name": k, "nodes": [n for n in v if n in nidx]} for k, v in (model.get("diaphragms") or {}).items()]
    zbase = float(xyz[:, 2].min()) if len(xyz) else 0.0
    massive = [k for k in range(len(used)) if weight[k] > 0]
    lev = _levels(xyz[massive, 2]) if massive else []
    lev = [z for z in lev if z > zbase + 0.05]
    lev_nodes = {z: [k for k in massive if abs(xyz[k, 2] - z) <= 0.05] for z in lev}
    if not diaph and opts.get("auto_diaphragm"):
        for z in lev:
            ids = [used[k] for k in range(len(used)) if abs(xyz[k, 2] - z) <= 0.05 and used[k] not in sup_nodes]
            if len(ids) >= 2:
                diaph.append({"name": f"D@{z:.2f}", "nodes": ids})
        if diaph:
            assume(f"Rigid diaphragms were applied at {len(diaph)} floor levels (engineer choice in review).",
                   f"دیافراگم صلب در {len(diaph)} تراز کف اعمال شد (انتخاب مهندس در بازبینی).")
    diaph_of_node = {n: d["name"] for d in diaph for n in d["nodes"]}

    try:
        eng = FrameEngine(nodes, els, {n: fl for n, fl in model["supports"].items() if n in nidx}, diaph, mass)
    except EngineError as exc:
        raise ValueError(str(exc)) from exc

    def vec_of(pat: str, extra_nodal: list[dict[str, Any]] | None = None) -> tuple[np.ndarray, dict]:
        segs, nl = loads.get(pat, ({}, []))
        F, eql = eng.element_loads({k: [(a, b, np.asarray(w, float)) for a, b, w in v] for k, v in segs.items()})
        for ld in list(nl) + list(extra_nodal or []):
            k = 6 * nidx[ld["node"]]
            for o, key in enumerate(("fx", "fy", "fz", "mx", "my", "mz")):
                F[k + o] += ld.get(key, 0.0) or 0.0
        return F, eql

    # ---- Standard 2800 parameters -------------------------------------------------------------
    H = float(max(lev) - zbase) if lev else 0.0
    n_st = len(lev)
    steel_cols = sum(1 for m in model["members"] if m["type"] == "column" and "steel" in mtype[m["id"]])
    cols = sum(1 for m in model["members"] if m["type"] == "column") or 1
    seis_in = model.get("seismic") or {}
    zone = str(seis_in.get("zone") or "HIGH").upper()
    soil = str(seis_in.get("soil") or "II").upper()
    imp = float(seis_in.get("importance") or 1.0)
    system = str(seis_in.get("system") or ("STEEL_IMF" if steel_cols > cols / 2 else "RC_IMF")).upper()
    if zone not in s2800.ZONE_A:
        zone = "HIGH"
    if system not in s2800.SYSTEMS:
        system = "RC_IMF"
    seismic: dict[str, Any] | None = None
    lateral_gen: dict[str, list[dict[str, Any]]] = {}
    file_lat = {p for p in pats if kinds[p] in ("E", "W") and (loads[p][0] or loads[p][1])}
    if H > 0 and W_total > 0:
        es = s2800.equivalent_static(zone=zone, soil=soil, importance=imp, system=system, height_m=H, storeys=max(n_st, 1))
        V = es["C"] * W_total
        Wl = np.array([weight[lev_nodes[z]].sum() for z in lev])
        hl = np.array(lev) - zbase
        sh = Wl * hl ** es["k"]
        Fl = V * sh / sh.sum()
        seismic = {**{k: es[k] for k in ("zone", "soil", "system", "system_label", "A", "R", "Cd", "I", "T_empirical_s", "B", "C", "k", "drift_limit")},
                   "H_m": _f(H), "storeys": n_st, "W_kN": _f(W_total), "V_kN": _f(V),
                   "levels": [{"z": _f(z), "W_kN": _f(w), "F_kN": _f(f)} for z, w, f in zip(lev, Wl, Fl)],
                   "from_file": not seis_in, "generated": []}
        if not seis_in:
            assume(f"Standard 2800 parameters not in the file: zone {zone} (A={es['A']}), soil {soil}, I={imp:g}, system {es['system_label']} (R={es['R']}, Cd={es['Cd']}), T = empirical {es['T_empirical_s']:.2f} s. Change them in the review.",
                   f"پارامترهای استاندارد ۲۸۰۰ در فایل نبود: پهنه {zone} (A={es['A']})، خاک {soil}، I={imp:g}، سیستم {es['system_label']} (R={es['R']}، Cd={es['Cd']})، T تجربی {es['T_empirical_s']:.2f} ثانیه. در بازبینی قابل تغییر است.")

        def lateral(direction: str, Fs: np.ndarray, ecc: float) -> list[dict[str, Any]]:
            out = []
            ax = 0 if direction == "X" else 1
            for z, F in zip(lev, Fs):
                ids = lev_nodes[z]
                w = weight[ids]
                for k, wk in zip(ids, w):
                    out.append({"node": used[k], "fx": F * wk / w.sum() if ax == 0 else 0.0, "fy": F * wk / w.sum() if ax == 1 else 0.0})
                dn = next((used[k] for k in ids if used[k] in diaph_of_node), None)
                if dn and ecc:
                    span = float(np.ptp(xyz[ids, 1 - ax])) if len(ids) > 1 else 0.0
                    out.append({"node": dn, "mz": ecc * 0.05 * span * F * (1 if ax == 0 else -1)})
            return out

        e_pats = [p for p in pats if kinds[p] == "E"]
        if not any(p in file_lat for p in e_pats):
            targets = [p for p in e_pats] or []
            dirs = {_dir(p) for p in targets}
            for d in ("X", "Y"):
                if d not in dirs:
                    targets.append(f"E{d} (2800)")
            for p in targets:
                d = _dir(p)
                lateral_gen[p] = lateral(d, Fl, 1.0 if diaph else 0.0)
                pats.setdefault(p, {"type": "Seismic", "self_weight": 0.0})
                kinds[p] = "E"
                loads.setdefault(p, ({}, []))
                seismic["generated"].append({"pattern": p, "dir": d})
            assume("Seismic loads were generated by SAIA (Standard 2800 equivalent static, V = C*W, W = D + 0.2L, F_i proportional to W_i*h_i^k" + (", +5% accidental eccentricity at rigid diaphragms" if diaph else ", no accidental torsion because the floors have no rigid diaphragm") + ").",
                   "بار زلزله توسط SAIA تولید شد (استاتیکی معادل ۲۸۰۰، V = C·W، W = D + 0.2L، توزیع F_i متناسب با W_i·h_i^k" + ("، با برون‌مرکزی اتفاقی ۵٪ در دیافراگم‌های صلب" if diaph else "، بدون پیچش اتفاقی چون کف‌ها دیافراگم صلب ندارند") + ").")
        # ---- wind (Mabhas 6, simplified) ----------------------------------------------------------
        w_in = model.get("wind") or {}
        w_pats = [p for p in pats if kinds[p] == "W"]
        if w_in.get("enabled", True) is not False and not any(p in file_lat for p in w_pats):
            Vw = float(w_in.get("V_kmh") or 100.0)
            q = 0.5 * 1.25 * (Vw / 3.6) ** 2 / 1000.0
            cq = 1.3
            targets = list(w_pats)
            dirs = {_dir(p) for p in targets}
            for d in ("X", "Y"):
                if d not in dirs:
                    targets.append(f"W{d} (Mabhas 6)")
            for p in targets:
                d = _dir(p)
                ax = 0 if d == "X" else 1
                out = []
                for n, z in enumerate(lev):
                    top = lev[n + 1] if n + 1 < len(lev) else z
                    bot = lev[n - 1] if n > 0 else zbase
                    trib = (top - z) / 2 + (z - bot) / 2
                    ids = lev_nodes[z]
                    width = float(np.ptp(xyz[ids, 1 - ax])) if len(ids) > 1 else 1.0
                    ce = max(0.9, ((z - zbase) / 10.0) ** 0.2) if z > zbase else 0.9
                    F = q * ce * cq * width * trib
                    w = weight[ids]
                    for k, wk in zip(ids, w):
                        out.append({"node": used[k], "fx": F * wk / w.sum() if ax == 0 else 0.0, "fy": F * wk / w.sum() if ax == 1 else 0.0})
                lateral_gen[p] = out
                pats.setdefault(p, {"type": "Wind", "self_weight": 0.0})
                kinds[p] = "W"
                loads.setdefault(p, ({}, []))
            assume(f"Wind loads were generated by SAIA (simplified Mabhas 6: V = {Vw:g} km/h, q = {q:.3f} kPa, Ce = (z/10)^0.2 >= 0.9, Cq = 1.3 windward+leeward, on the plan width of each floor).",
                   f"بار باد توسط SAIA تولید شد (مبحث ۶ ساده‌شده: V = {Vw:g} km/h، q = {q:.3f} kPa، Ce = (z/10)^0.2 ≥ 0.9، Cq = 1.3 رو و پشت به باد، روی عرض پلان هر طبقه).")
    elif any(kinds[p] in ("E", "W") for p in pats):
        notes.append("No seismic weight or height - lateral loads could not be generated.")

    # ---- combinations ----------------------------------------------------------------------------
    combos = {k: dict(v) for k, v in model["combos"].items() if "(assumed)" not in k}
    D = [p for p in pats if kinds[p] == "D"]
    Lp = [p for p in pats if kinds[p] == "L"]
    E = [p for p in pats if kinds[p] == "E"]
    Wp = [p for p in pats if kinds[p] == "W"]
    gen_e = [p for p in E if p in lateral_gen]
    if not combos:
        combos["1.4D (assumed)"] = {p: 1.4 for p in D}
        combos["1.2D+1.6L (assumed)"] = {p: 1.2 for p in D} | {p: 1.6 for p in Lp}
        assume("No load combinations in the file: Mabhas 6 / ASCE 7 strength combinations assumed (1.4D; 1.2D+1.6L; 1.2D+1.0L±E; 0.9D±E; 1.2D+1.0L±1.0W; 0.9D±1.0W).",
               "ترکیب بار در فایل نبود؛ ترکیب‌های مقاومت مبحث ۶ / ASCE 7 فرض شد (1.4D؛ 1.2D+1.6L؛ 1.2D+1.0L±E؛ 0.9D±E؛ 1.2D+1.0L±1.0W؛ 0.9D±1.0W).")
        lat_e, lat_w = E, Wp
    else:
        lat_e, lat_w = gen_e, [p for p in Wp if p in lateral_gen]
    for e in lat_e:
        for s in (1, -1):
            sg = "+" if s > 0 else "-"
            combos[f"1.2D+L{sg}{e} (assumed)"] = {p: 1.2 for p in D} | {p: 1.0 for p in Lp} | {e: float(s)}
            combos[f"0.9D{sg}{e} (assumed)"] = {p: 0.9 for p in D} | {e: float(s)}
    for w in lat_w:
        for s in (1, -1):
            sg = "+" if s > 0 else "-"
            combos[f"1.2D+L{sg}{w} (assumed)"] = {p: 1.2 for p in D} | {p: 1.0 for p in Lp} | {w: float(s)}
            combos[f"0.9D{sg}{w} (assumed)"] = {p: 0.9 for p in D} | {w: float(s)}

    # ---- P-Delta --------------------------------------------------------------------------------
    vecs: dict[str, tuple[np.ndarray, dict]] = {}

    def build_vecs() -> None:
        for p in pats:
            vecs[p] = vec_of(p, [{**x} for x in lateral_gen.get(p, [])])

    build_vecs()
    pdelta = {"applied": False}
    first_order_disp: dict[str, float] = {}
    lat_cases = [p for p in pats if kinds[p] in ("E", "W")]
    for p in lat_cases:
        first_order_disp[p] = float(np.abs(eng.solve(vecs[p][0])).reshape(-1, 6)[:, :2].max())
    if opts.get("pdelta", True) and D:
        grav = {p: 1.2 for p in D} | {p: 1.0 for p in Lp}
        axial = None
        try:
            for it in range(4):
                F = sum(sf * vecs[p][0] for p, sf in grav.items())
                eql = _combine_eql(vecs, grav)
                U = eng.solve(F)
                ends = eng.end_forces(U, eql)
                new = (ends[:, 6] - ends[:, 0]) / 2
                if axial is not None and np.abs(new - axial).max() <= 0.01 * max(1.0, np.abs(new).max()):
                    axial = new
                    break
                axial = new
                eng.set_pdelta(axial)
                build_vecs()
            amp = {}
            for p in lat_cases:
                d2 = float(np.abs(eng.solve(vecs[p][0])).reshape(-1, 6)[:, :2].max())
                amp[p] = _f(d2 / first_order_disp[p]) if first_order_disp[p] > 0 else 1.0
            pdelta = {"applied": True, "gravity_case": "1.2D + 1.0L", "iterations": it + 1, "amplification": amp}
            if amp and max(amp.values()) > 1.5:
                notes.append("P-Delta amplification above 1.5 - the structure is close to elastic instability (2800 stability coefficient check).")
        except (EngineError, RuntimeError) as exc:
            raise ValueError(f"P-Delta: the structure is unstable under 1.2D+1.0L ({exc}). Check sections or disable P-Delta in the review.") from exc
        assume("P-Delta: geometric stiffness from the 1.2D + 1.0L axial forces (iterated) is used for every load case; results are second order.",
               "پی-دلتا: سختی هندسی ناشی از نیروی محوری 1.2D + 1.0L (تکراری) برای همه‌ی حالت‌های بار به کار رفت؛ نتایج مرتبه دوم است.")

    # ---- solve patterns ------------------------------------------------------------------------
    pat_st: dict[str, np.ndarray] = {}
    pat_U: dict[str, np.ndarray] = {}
    pat_R: dict[str, np.ndarray] = {}
    equil: dict[str, float] = {}
    for p in pats:
        F, eql = vecs[p]
        U = eng.solve(F)
        ends = eng.end_forces(U, eql)
        pat_st[p] = eng.stations(ends, eql)
        pat_U[p] = U
        R = eng.reactions(U, F)
        pat_R[p] = R
        applied = F.reshape(-1, 6)[:, :3].sum(0)
        scale = max(1.0, float(np.abs(applied).max()))
        equil[p] = _f(float(np.abs(applied + _support_sum(R, eng)).max()) / scale)

    # ---- modal + response spectrum ---------------------------------------------------------------
    modal = None
    rs = None
    rs_st: dict[str, np.ndarray] = {}
    if mass and seismic:
        try:
            md = eng.modal(n_modes=int(opts.get("modes") or 12))
            modes = md["modes"]
            modal = {"modes": [{k: _f(v) if isinstance(v, float) else v for k, v in m.items()} for m in modes],
                     "total_mass_t": _f(md["total_mass_t"])}
            om = np.array([m["omega"] for m in modes])
            rs = {"zeta": 0.05, "scale": {}, "base_shear_kN": {}, "static_base_shear_kN": seismic["V_kN"]}
            for d, gk in (("X", "gamma_x"), ("Y", "gamma_y")):
                sts, vb, disp = [], [], []
                for n, m in enumerate(modes):
                    sa = seismic["A"] * s2800.spectral_b(m["T"], soil, zone) * imp / seismic["R"] * G_ACC
                    Un = eng.mode_full(n) * m[gk] * sa / m["omega"] ** 2
                    ends = eng.end_forces(Un, {})
                    sts.append(eng.stations(ends, {}))
                    disp.append(Un)
                    vb.append(_support_sum(eng.reactions(Un, np.zeros_like(Un)), eng)[0 if d == "X" else 1])
                vb_c = float(cqc(np.array(vb)[:, None], om)[0])
                Vs = seismic["V_kN"]
                sc = max(1.0, 0.85 * Vs / vb_c) if vb_c > 0 else 1.0
                rs["scale"][d] = _f(sc)
                rs["base_shear_kN"][d] = _f(vb_c * sc)
                rs_st[f"RS{d}"] = cqc(np.array(sts), om) * sc
                pat_U[f"RS{d}"] = cqc(np.array(disp), om) * sc
            assume("Response spectrum: Standard 2800 design spectrum Sa = A*B*I/R*g, 5% damping, CQC modal combination, scaled up to 85% of the static base shear when lower. X and Y are reported separately (no 100%+30% directional combination).",
                   "طیف پاسخ: طیف طرح ۲۸۰۰ با Sa = A·B·I/R·g، میرایی ۵٪، ترکیب مودها CQC، در صورت کمتر بودن تا ۸۵٪ برش پایه‌ی استاتیکی بزرگ‌نمایی شد. X و Y جداگانه گزارش شده‌اند (بدون ترکیب ۱۰۰٪+۳۰٪).")
            cx, cy = (modes[-1]["cum_x"], modes[-1]["cum_y"]) if modes else (0, 0)
            if min(cx, cy) < 0.9:
                notes.append(f"Modal mass participation {cx:.0%} (X), {cy:.0%} (Y) is below the 90% required by Standard 2800 - increase the number of modes.")
        except (EngineError, RuntimeError, np.linalg.LinAlgError) as exc:
            notes.append(f"Modal analysis failed: {exc}")

    # ---- cases ----------------------------------------------------------------------------------
    nel = len(eng.elements)
    ids = [el.id for el in eng.elements]
    cases_st: dict[str, np.ndarray] = {}
    cases_meta: dict[str, dict[str, Any]] = {}
    for p in pats:
        cases_st[f"pattern:{p}"] = pat_st[p]
        cases_meta[f"pattern:{p}"] = {"factors": {p: 1.0}, "U": pat_U[p], "R": pat_R[p]}
    for c, fac in combos.items():
        st = np.zeros((nel, pat_st[next(iter(pat_st))].shape[1], 6)) if pat_st else np.zeros((0, 9, 6))
        U = np.zeros(eng.ndof)
        R = np.zeros(eng.ndof)
        for p, sf in fac.items():
            if p in pat_st:
                st = st + sf * pat_st[p]
                U = U + sf * pat_U[p]
                R = R + sf * pat_R[p]
        cases_st[f"combo:{c}"] = st
        cases_meta[f"combo:{c}"] = {"factors": fac, "U": U, "R": R}
    for d, st in rs_st.items():
        cases_st[f"spectrum:{d}"] = st
        cases_meta[f"spectrum:{d}"] = {"factors": {d: 1.0}, "U": pat_U[d], "R": None, "unsigned": True}
        grav = {p: 1.2 for p in D} | {p: 1.0 for p in Lp}
        g = sum(sf * pat_st[p] for p, sf in grav.items()) if grav else 0 * st
        cases_st[f"envelope:1.2D+L±{d}"] = np.abs(g) + st
        cases_meta[f"envelope:1.2D+L±{d}"] = {"factors": grav | {d: 1.0}, "U": None, "R": None, "unsigned": True}

    results: dict[str, Any] = {}
    env = {mid: {"N": 0.0, "V": 0.0, "M": 0.0, "T": 0.0} for mid in ids}
    for cname, st in cases_st.items():
        meta = cases_meta[cname]
        mN = np.abs(st[:, :, 0]).max(1) if nel else np.zeros(0)
        mV = np.sqrt(st[:, :, 1] ** 2 + st[:, :, 2] ** 2).max(1) if nel else np.zeros(0)
        mM = np.sqrt(st[:, :, 4] ** 2 + st[:, :, 5] ** 2).max(1) if nel else np.zeros(0)
        mT = np.abs(st[:, :, 3]).max(1) if nel else np.zeros(0)
        U = meta["U"]
        disp = np.linalg.norm(U.reshape(-1, 6)[:, :3], axis=1) if U is not None else np.zeros(1)
        k = int(np.argmax(disp)) if disp.size else 0
        rec = {"factors": meta["factors"],
               "base_reaction_kN": [_f(v) for v in (_support_sum(meta["R"], eng) if meta["R"] is not None else (0, 0, 0))],
               "max_displacement_m": _f(float(disp.max()) if disp.size else 0.0),
               "max_displacement_node": used[k] if used else None}
        if meta.get("unsigned"):
            rec["unsigned"] = True
        if nel <= MAX_CASE_MEMBERS:
            rec["members"] = {mid: {"N": _f(mN[n]), "V": _f(mV[n]), "M": _f(mM[n]), "T": _f(mT[n])} for n, mid in enumerate(ids)}
        results[cname] = rec
        if not cname.startswith("pattern:") or not combos:
            for n, mid in enumerate(ids):
                e = env[mid]
                e["N"] = max(e["N"], float(mN[n])); e["V"] = max(e["V"], float(mV[n]))
                e["M"] = max(e["M"], float(mM[n])); e["T"] = max(e["T"], float(mT[n]))
    env = {k: {kk: _f(vv) for kk, vv in v.items()} for k, v in env.items()}
    if nel > MAX_CASE_MEMBERS:
        notes.append(f"{nel} members: per-case member tables are omitted from the response; the envelope covers every member.")

    # ---- drifts --------------------------------------------------------------------------------
    drifts = []
    if seismic and lev:
        cd = seismic["Cd"]
        lim = seismic["drift_limit"]
        for p in [p for p in pats if kinds[p] == "E"] + list(rs_st):
            U = pat_U[p].reshape(-1, 6)
            ax = 0 if _dir(p.replace("RS", "E")) == "X" else 1
            prev = 0.0
            zprev = zbase
            rows = []
            for z in lev:
                ids_l = lev_nodes[z]
                u = float(np.abs(U[[nidx[used[k]] for k in ids_l], ax]).max())
                h = z - zprev
                ratio = cd * abs(u - prev) / imp / h if h > 0 else 0.0
                rows.append({"z": _f(z), "u_m": _f(u), "drift": _f(ratio), "ok": ratio <= lim})
                prev, zprev = u, z
            drifts.append({"case": p, "limit": lim, "factor": f"Cd/I = {cd:g}/{imp:g}", "levels": rows,
                           "max": _f(max((r["drift"] for r in rows), default=0.0)), "ok": all(r["ok"] for r in rows)})

    # ---- preliminary design ------------------------------------------------------------------------
    from app.application.model_import.design import design_members
    design = design_members(model, eng, {k: v for k, v in cases_st.items() if k.startswith(("combo:", "envelope:"))} or cases_st, lengths)

    governing = sorted(env.items(), key=lambda kv: -kv[1]["M"])[:15]
    return {
        "engine": "SAIA sparse 3D frame engine (scipy.sparse; releases, rigid diaphragms, P-Delta, modal, response spectrum)",
        "units": {"force": "kN", "length": "m", "moment": "kN.m", "mass": "t"},
        "counts": model.get("counts", {}) | {"dof": int(eng.ndof), "free_dof": int(eng.free.size), "diaphragms": len(diaph), "slabs": len(slab_report)},
        "cases": results,
        "envelope": env,
        "governing_members": [{"member": k, **v} for k, v in governing],
        "assumptions": assumptions,
        "seismic": seismic,
        "pdelta": pdelta,
        "modal": modal,
        "response_spectrum": rs,
        "drifts": drifts,
        "equilibrium": equil,
        "slabs": {"count": len(slab_report), "one_way": sum(1 for r in slab_report if r["one_way"]),
                  "to_nodes": sum(1 for r in slab_report if r["to_nodes"])},
        "design": design,
        "notes": notes + eng.notes + [
            "Member results are max |N|, resultant |V| and |M| along each member (9 stations) in kN and kN.m.",
            "Response-spectrum and '±RS' envelope cases are unsigned (absolute values).",
        ],
    }


_MEM_CACHE: dict[int, dict[str, dict[str, Any]]] = {}


def _mem_index(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    key = id(model)
    if key not in _MEM_CACHE:
        _MEM_CACHE.clear()
        _MEM_CACHE[key] = {m["id"]: m for m in model["members"]}
    return _MEM_CACHE[key]


def _combine_eql(vecs: dict[str, tuple[np.ndarray, dict]], factors: dict[str, float]) -> dict:
    out: dict[int, tuple[np.ndarray, list]] = {}
    for p, sf in factors.items():
        for n, (f, segs) in vecs[p][1].items():
            if n in out:
                out[n] = (out[n][0] + sf * f, out[n][1] + [(a, b, sf * w) for a, b, w in segs])
            else:
                out[n] = (sf * f, [(a, b, sf * w) for a, b, w in segs])
    return out


def _support_sum(R: np.ndarray, eng: FrameEngine) -> np.ndarray:
    tot = np.zeros(3)
    for i, fl in eng.supports.items():
        for k in range(3):
            if fl[k]:
                tot[k] += R[6 * i + k]
    return tot
