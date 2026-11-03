"""SAP2000 .s2k and SAFE .f2k (CSI database text tables) -> SAIA neutral model (kN, m).

Both programs write ``TABLE:  "NAME"`` blocks of ``Key=Value`` rows (`` _`` continues a row). One
reader serves both; SAFE-specific table names (OBJECT GEOMETRY ..., SLAB PROPERTIES ...) are mapped
to the same model. SAFE plate bending is not analysed: slab loads go to beams by tributary area and
the columns under the slab become supports (see issues).
"""

from __future__ import annotations

from typing import Any

from app.application.model_import.common import (
    FORCE_TO_KN, LEN_TO_M, assume, box_props, eqpairs, i_props, issue, new_model, num, pipe_props, rect_props,
)
from app.application.model_import.e2k_import import REL_NAMES


def read_tables(text: str) -> dict[str, list[dict[str, str]]]:
    tables: dict[str, list[dict[str, str]]] = {}
    cur: str | None = None
    buf = ""
    for raw in text.splitlines():
        line = raw.rstrip()
        if buf:
            line = buf + " " + line.strip()
            buf = ""
        if line.endswith(" _"):
            buf = line[:-2]
            continue
        s = line.strip()
        if not s or s.startswith(("$", ";")):
            continue
        if s.upper().startswith("TABLE:"):
            cur = s.split(":", 1)[1].strip().strip('"').upper()
            tables.setdefault(cur, [])
            continue
        if s.upper().startswith("END TABLE DATA"):
            break
        if cur is not None:
            row = eqpairs(s)
            if row:
                tables[cur].append({k.upper(): v for k, v in row.items()})
    return tables


def _t(tables: dict[str, list[dict[str, str]]], *names: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for n in names:
        for k, rows in tables.items():
            if k == n or k.startswith(n):
                out.extend(rows)
    return out


def _g(row: dict[str, str], *keys: str) -> str | None:
    for k in keys:
        if k in row and row[k] not in ("", "N.A."):
            return row[k]
    return None


def _yes(v: str | None) -> bool:
    return str(v or "").strip().lower() in ("yes", "true", "1", "y")


def parse_csi_tables(filename: str, text: str, fmt: str) -> dict[str, Any]:
    m = new_model(fmt, filename)
    tb = read_tables(text)
    if not tb:
        issue(m, "blocking", "no_tables", "model", "No CSI 'TABLE:' blocks were found - is this a SAP2000/SAFE text export?",
              "هیچ بلوک «TABLE:» پیدا نشد؛ آیا این فایل خروجی متنی SAP2000/SAFE است؟")
        return m
    fu, lu = "KN", "M"
    for r in _t(tb, "PROGRAM CONTROL"):
        cu = _g(r, "CURRUNITS")
        if cu:
            parts = [p.strip().upper() for p in cu.split(",")]
            if len(parts) >= 2:
                fu, lu = parts[0], parts[1]
    if fu not in FORCE_TO_KN or lu not in LEN_TO_M:
        issue(m, "approximated", "units", f"{fu} {lu}", f"Unknown units {fu}/{lu} - kN and m assumed.", f"واحد ناشناخته {fu}/{lu}؛ کیلونیوتن و متر فرض شد.")
        fu, lu = "KN", "M"
    F, L = FORCE_TO_KN[fu], LEN_TO_M[lu]
    m["units"]["source"] = f"{fu}, {lu}"
    if (fu, lu) != ("KN", "M"):
        assume(m, f"File units {fu}, {lu} were converted to kN, m.", f"واحدهای فایل ({fu}، {lu}) به کیلونیوتن و متر تبدیل شدند.")

    # materials
    for r in _t(tb, "MATERIAL PROPERTIES 01"):
        name = _g(r, "MATERIAL")
        if name:
            m["materials"].setdefault(name, {"type": _g(r, "TYPE") or "Concrete", "E": None, "nu": 0.2, "unit_weight": 0.0})
    for r in _t(tb, "MATERIAL PROPERTIES 02", "MATERIAL PROPERTIES 03"):
        name = _g(r, "MATERIAL")
        if not name:
            continue
        mat = m["materials"].setdefault(name, {"type": "Concrete", "E": None, "nu": 0.2, "unit_weight": 0.0})
        e = num(_g(r, "E1", "E"))
        if e:
            mat["E"] = e * F / L**2
        u = num(_g(r, "U12", "U"))
        if u is not None:
            mat["nu"] = u
        w = num(_g(r, "UNITWEIGHT"))
        if w is not None:
            mat["unit_weight"] = w * F / L**3
        fy = num(_g(r, "FY"))
        if fy:
            mat["Fy"] = fy * F / L**2
        fc = num(_g(r, "FC"))
        if fc:
            mat["Fc"] = fc * F / L**2
    for name, mat in m["materials"].items():
        if not mat["E"]:
            steel = str(mat["type"]).lower().startswith("steel")
            mat["E"] = 2.0e8 if steel else 2.35e7
            issue(m, "approximated", "material_E", name, f"Material {name}: E not found - default assumed.", f"مصالح {name}: E پیدا نشد؛ مقدار پیش‌فرض فرض شد.")

    # frame sections
    for r in _t(tb, "FRAME SECTION PROPERTIES 01", "BEAM PROPERTIES", "COLUMN PROPERTIES 01"):
        name = _g(r, "SECTIONNAME", "BEAM", "COLUMN", "NAME")
        if not name:
            continue
        sec = m["sections"].setdefault(name, {"shape": None, "material": None, "modifiers": {}})
        sec["material"] = _g(r, "MATERIAL", "MATPROP") or sec["material"]
        shape = (_g(r, "SHAPE", "TYPE") or "").lower()
        sec["shape"] = _g(r, "SHAPE", "TYPE")
        t3, t2 = (num(_g(r, "T3", "DEPTH", "SECDIM2"), 0) or 0) * L, (num(_g(r, "T2", "WIDTH", "SECDIM3"), 0) or 0) * L
        tf, tw = (num(_g(r, "TF"), 0) or 0) * L, (num(_g(r, "TW"), 0) or 0) * L
        props = None
        a = num(_g(r, "AREA"))
        if a:
            props = {"A": a * L**2, "I33": (num(_g(r, "I33"), 0) or 0) * L**4, "I22": (num(_g(r, "I22"), 0) or 0) * L**4,
                     "J": (num(_g(r, "TORSCONST", "J"), 0) or 0) * L**4}
            if not props["I33"]:
                props = None
        if props is None:
            if "rect" in shape and t3 and t2:
                props = rect_props(t2, t3)
            elif ("i/wide" in shape or "i-section" in shape) and t3 and t2 and tf and tw:
                props = i_props(t3, t2, tf, tw)
            elif ("box" in shape or "tube" in shape) and t3 and t2 and tf:
                props = box_props(t3, t2, tf, tw or tf)
            elif "pipe" in shape and t3 and tw:
                props = pipe_props(t3, tw)
            elif "circ" in shape and t3:
                import math
                props = {"A": math.pi * t3**2 / 4, "I33": math.pi * t3**4 / 64, "I22": math.pi * t3**4 / 64, "J": math.pi * t3**4 / 32}
        if "rect" in shape and t3 and t2:
            sec["b"], sec["h"] = t2, t3
        if props:
            sec.update(props)
        for key, mk in (("AMOD", "A"), ("I2MOD", "I22"), ("I3MOD", "I33"), ("JMOD", "J")):
            v = num(_g(r, key))
            if v is not None and v != 1:
                sec["modifiers"][mk] = v

    # joints
    for r in _t(tb, "JOINT COORDINATES", "OBJECT GEOMETRY - POINT COORDINATES", "POINT COORDINATES"):
        jid = _g(r, "JOINT", "POINT")
        x = num(_g(r, "GLOBALX", "XORR", "X"))
        y = num(_g(r, "GLOBALY", "Y"))
        z = num(_g(r, "GLOBALZ", "Z"), 0.0)
        if jid is None or x is None or y is None:
            continue
        m["nodes"][jid] = {"x": round(x * L, 6), "y": round(y * L, 6), "z": round((z or 0.0) * L, 6)}

    # frames
    conn = _t(tb, "CONNECTIVITY - FRAME", "OBJECT GEOMETRY - LINES 01", "OBJECT GEOMETRY - BEAMS", "OBJECT GEOMETRY - COLUMNS")
    for r in conn:
        fid = _g(r, "FRAME", "LINE", "BEAM", "COLUMN")
        a, b = _g(r, "JOINTI", "POINTI", "POINT1"), _g(r, "JOINTJ", "POINTJ", "POINT2")
        if not fid or a not in m["nodes"] or b not in m["nodes"] or a == b:
            if fid:
                issue(m, "ignored", "bad_line", fid, f"Frame {fid}: end joints not found - ignored.", f"عضو {fid}: گره‌های انتهایی پیدا نشد؛ نادیده گرفته شد.")
            continue
        na, nb = m["nodes"][a], m["nodes"][b]
        dz = abs(na["z"] - nb["z"])
        dh = ((na["x"] - nb["x"]) ** 2 + (na["y"] - nb["y"]) ** 2) ** 0.5
        lt = (_g(r, "LINETYPE") or "").lower()
        typ = "column" if (lt.startswith("col") or (dh < 1e-6 and dz > 0)) else "beam" if (lt.startswith("beam") or dz < 1e-6) else "brace"
        if typ == "column" and na["z"] > nb["z"]:
            a, b = b, a
        m["members"].append({"id": fid, "i": a, "j": b, "type": typ, "section": None, "label": fid})
    mem_by = {x["id"]: x for x in m["members"]}
    for r in _t(tb, "FRAME SECTION ASSIGNMENTS", "LINE ASSIGNMENTS - SECTION", "BEAM PROPERTY ASSIGNMENTS", "COLUMN PROPERTY ASSIGNMENTS"):
        fid = _g(r, "FRAME", "LINE", "BEAM", "COLUMN")
        sec = _g(r, "ANALSECT", "SECTION", "BEAMPROP", "COLPROP", "DESIGNSECT")
        if fid in mem_by and sec:
            mem_by[fid]["section"] = sec
    for mem in m["members"]:
        if not mem["section"]:
            mem["section"] = "(none)"
            issue(m, "blocking", "member_no_section", mem["id"], f"Member {mem['id']} has no section assigned.", f"به عضو {mem['id']} مقطعی تخصیص داده نشده است.")
    nrel = 0
    for r in _t(tb, "FRAME RELEASE ASSIGNMENTS 1", "LINE ASSIGNMENTS - RELEASES", "FRAME RELEASES"):
        fid = _g(r, "FRAME", "LINE", "BEAM")
        if fid in mem_by:
            ri = [_yes(_g(r, f"{n}I")) for n in REL_NAMES]
            rj = [_yes(_g(r, f"{n}J")) for n in REL_NAMES]
            if any(ri) or any(rj):
                mem_by[fid]["rel_i"], mem_by[fid]["rel_j"] = ri, rj
                nrel += 1
    if nrel:
        assume(m, f"{nrel} member end releases were applied by static condensation.", f"{nrel} آزادسازی انتهای عضو با تراکم استاتیکی اعمال شد.")

    # supports
    for r in _t(tb, "JOINT RESTRAINT ASSIGNMENTS", "POINT RESTRAINT ASSIGNMENTS", "SUPPORT ASSIGNMENTS - POINT RESTRAINTS"):
        jid = _g(r, "JOINT", "POINT")
        if jid in m["nodes"]:
            m["supports"][jid] = [_yes(_g(r, k)) for k in ("U1", "U2", "U3", "R1", "R2", "R3")]
    if _t(tb, "JOINT SPRING ASSIGNMENTS", "POINT SPRING ASSIGNMENTS", "SOIL"):
        issue(m, "ignored", "spring", "model", "Springs / soil supports were ignored.", "فنرها / تکیه‌گاه خاک نادیده گرفته شدند.")

    # areas
    for r in _t(tb, "AREA SECTION PROPERTIES", "SLAB PROPERTIES 02", "SLAB PROPERTIES 01"):
        name = _g(r, "SECTION", "SLAB")
        if not name:
            continue
        sec = m["area_sections"].setdefault(name, {"material": None, "thickness": None, "type": "Slab"})
        sec["material"] = _g(r, "MATERIAL", "MATPROP") or sec["material"]
        th = num(_g(r, "THICKNESS", "THICK"))
        if th:
            sec["thickness"] = th * L
        if "one" in (_g(r, "TYPE", "SLABTYPE") or "").lower():
            sec["one_way"] = True
    area_sec = {(_g(r, "AREA")): _g(r, "SECTION", "SLABPROP") for r in _t(tb, "AREA SECTION ASSIGNMENTS", "SLAB PROPERTY ASSIGNMENTS")}
    walls = 0
    for r in _t(tb, "CONNECTIVITY - AREA", "OBJECT GEOMETRY - AREAS 01", "OBJECT GEOMETRY - SLABS"):
        aid = _g(r, "AREA", "SLAB")
        nj = int(num(_g(r, "NUMJOINTS", "NUMPOINTS"), 0) or 0)
        pts = [_g(r, f"JOINT{k}", f"POINT{k}") for k in range(1, (nj or 12) + 1)]
        pts = [p for p in pts if p in m["nodes"]]
        if not aid or len(pts) < 3:
            continue
        zs = [m["nodes"][p]["z"] for p in pts]
        if max(zs) - min(zs) > 1e-3:
            walls += 1
            continue
        sec = area_sec.get(aid)
        m["areas"].append({"id": aid, "nodes": pts, "kind": "floor", "section": sec, "story": f"z={zs[0]:g}",
                           "one_way": True if m["area_sections"].get(sec or "", {}).get("one_way") else None})
    area_ids = {a["id"] for a in m["areas"]}

    # loads
    for r in _t(tb, "LOAD PATTERN DEFINITIONS", "LOAD PATTERNS"):
        name = _g(r, "LOADPAT", "NAME")
        if name:
            m["load_patterns"][name] = {"type": _g(r, "DESIGNTYPE", "TYPE") or "Other", "self_weight": num(_g(r, "SELFWTMULT"), 0.0) or 0.0}
    for r in _t(tb, "FRAME LOADS - DISTRIBUTED", "LINE LOADS - DISTRIBUTED", "FRAME LOAD ASSIGNMENTS - DISTRIBUTED"):
        fid, lc = _g(r, "FRAME", "LINE", "BEAM"), _g(r, "LOADPAT") or ""
        if fid not in mem_by:
            continue
        d = (_g(r, "DIR") or "Gravity").upper()
        unit = {"GRAVITY": (0, 0, -1), "Z": (0, 0, 1), "X": (1, 0, 0), "Y": (0, 1, 0)}.get(d)
        if unit is None or (_g(r, "TYPE") or "Force").lower() != "force":
            issue(m, "ignored", "lineload_dir", d, f"Frame load ({d}, local axis or moment) ignored.", f"بار عضو ({d}، محور محلی یا لنگر) نادیده گرفته شد.")
            continue
        wa, wb = num(_g(r, "FOVERLA"), 0) or 0, num(_g(r, "FOVERLB"), 0) or 0
        ra, rb = num(_g(r, "RELDISTA"), 0.0) or 0.0, num(_g(r, "RELDISTB"), 1.0) or 1.0
        for k in range(8 if wa != wb else 1):
            n = 8 if wa != wb else 1
            w = (wa + (wb - wa) * (k + 0.5) / n) * F / L
            ld = {"member": fid, "pattern": lc, "wx": unit[0] * w, "wy": unit[1] * w, "wz": unit[2] * w}
            a, b = ra + (rb - ra) * k / n, ra + (rb - ra) * (k + 1) / n
            if (a, b) != (0.0, 1.0):
                ld["ra"], ld["rb"] = a, b
            m["member_loads"].append(ld)
        m["load_patterns"].setdefault(lc, {"type": "Other", "self_weight": 0.0})
    for r in _t(tb, "JOINT LOADS - FORCE", "POINT LOADS", "LOAD ASSIGNMENTS - POINT LOADS"):
        jid, lc = _g(r, "JOINT", "POINT"), _g(r, "LOADPAT") or ""
        if jid not in m["nodes"]:
            continue
        ld = {"node": jid, "pattern": lc}
        for k, key in (("F1", "fx"), ("F2", "fy"), ("F3", "fz")):
            ld[key] = (num(_g(r, k, key.upper()), 0) or 0) * F
        for k, key in (("M1", "mx"), ("M2", "my"), ("M3", "mz")):
            ld[key] = (num(_g(r, k, key.upper()), 0) or 0) * F * L
        if fmt == "f2k" and not any(ld[k] for k in ("fx", "fy", "fz")) and num(_g(r, "FGRAV"), 0):
            ld["fz"] = -(num(_g(r, "FGRAV"), 0) or 0) * F
        m["nodal_loads"].append(ld)
        m["load_patterns"].setdefault(lc, {"type": "Other", "self_weight": 0.0})
    bad = 0
    for r in _t(tb, "AREA LOADS - UNIFORM", "LOAD ASSIGNMENTS - SURFACE LOADS", "AREA LOAD ASSIGNMENTS - UNIFORM"):
        aid, lc = _g(r, "AREA", "SLAB"), _g(r, "LOADPAT") or ""
        d = (_g(r, "DIR") or "Gravity").upper()
        q = num(_g(r, "UNIFLOAD", "LOAD", "FORCE"))
        if aid not in area_ids or q is None or d not in ("GRAVITY", "Z"):
            bad += 1
            continue
        q = q * F / L**2 * (-1 if d == "Z" else 1)
        m["area_loads"].append({"area": aid, "pattern": lc, "q": q})
        m["load_patterns"].setdefault(lc, {"type": "Other", "self_weight": 0.0})
    if bad:
        issue(m, "ignored", "area_loads_other", str(bad), f"{bad} area loads (non-gravity or on walls) ignored.", f"{bad} بار سطحی (غیرثقلی یا روی دیوار) نادیده گرفته شد.")

    # diaphragm constraints
    for r in _t(tb, "JOINT CONSTRAINT ASSIGNMENTS"):
        jid = _g(r, "JOINT")
        if jid in m["nodes"] and "diaph" in (_g(r, "TYPE") or "").lower():
            m["diaphragms"].setdefault(_g(r, "CONSTRAINT") or "D", []).append(jid)
    if m["diaphragms"]:
        assume(m, f"{len(m['diaphragms'])} diaphragm constraints were applied as rigid floors.", f"{len(m['diaphragms'])} قید دیافراگم به‌صورت کف صلب اعمال شد.")

    # combinations
    for r in _t(tb, "COMBINATION DEFINITIONS", "LOAD COMBINATIONS"):
        name, case = _g(r, "COMBONAME", "COMBO"), _g(r, "CASENAME", "LOAD")
        if not name or not case:
            continue
        ct = (_g(r, "COMBOTYPE") or "Linear Add").lower()
        if ct and "linear" not in ct:
            issue(m, "approximated", "combo_type", name, f"Combination {name} ({ct}) treated as linear add.", f"ترکیب {name} ({ct}) به‌صورت جمع خطی در نظر گرفته شد.")
        m["combos"].setdefault(name, {})[case] = num(_g(r, "SCALEFACTOR", "SF"), 1.0) or 0.0
    for name, combo in list(m["combos"].items()):
        flat: dict[str, float] = {}
        for case, sf in combo.items():
            if case in m["combos"] and case != name:
                for c2, sf2 in m["combos"][case].items():
                    flat[c2] = flat.get(c2, 0) + sf * sf2
            else:
                flat[case] = flat.get(case, 0) + sf
        for c in [c for c in flat if c not in m["load_patterns"]]:
            issue(m, "approximated", "combo_case", f"{name}:{c}", f"Combination {name}: case {c} is not a load pattern (modal/spectrum/nonlinear) and was dropped.",
                  f"ترکیب {name}: حالت {c} الگوی بار نیست (مودال/طیفی/غیرخطی) و حذف شد.")
            flat.pop(c)
        m["combos"][name] = flat

    if m["areas"]:
        assume(m, f"{len(m['areas'])} floor areas imported: loads go to supporting beams by tributary area (two-way 45 degree, one-way when aspect >= 2). Plate bending is not modelled.",
               f"{len(m['areas'])} سطح کف وارد شد: بارها به روش سطح بارگیر به تیرها می‌رسد (دوطرفه ۴۵ درجه، یک‌طرفه برای نسبت ابعاد ≥ ۲). خمش ورق مدل نمی‌شود.")
    if walls:
        issue(m, "ignored", "walls", str(walls), f"{walls} vertical shell areas (walls) were not analysed - their stiffness is missing.",
              f"{walls} سطح قائم (دیوار) تحلیل نشد؛ سختی آن‌ها لحاظ نشده است.")
    if fmt == "f2k":
        cols_below = _t(tb, "OBJECT GEOMETRY - COLUMNS", "COLUMN ASSIGNMENTS", "POINT ASSIGNMENTS - COLUMN")
        if not m["supports"] and m["nodes"]:
            issue(m, "approximated", "safe_supports", "model",
                  "SAFE model: no restraints read - lowest points/column locations were made pinned supports; plate bending of the slab is not analysed (frame engine).",
                  "مدل SAFE: قیدی خوانده نشد؛ محل ستون‌ها/پایین‌ترین نقاط تکیه‌گاه مفصلی شدند؛ خمش ورق دال تحلیل نمی‌شود (موتور قاب).")
            for r in cols_below:
                p = _g(r, "POINT", "JOINT")
                if p in m["nodes"]:
                    m["supports"][p] = [True, True, True, False, False, False]
    for key, en, fa in (("FUNCTION - RESPONSE SPECTRUM", "Response spectrum functions (SAIA uses the Standard 2800 spectrum)", "توابع طیف پاسخ (SAIA طیف ۲۸۰۰ را به کار می‌برد)"),
                        ("LINK PROPERTY", "Link elements", "المان‌های لینک"), ("TENDON", "Tendons", "تاندون‌ها"),
                        ("SOLID", "Solid elements", "المان‌های حجمی"), ("CABLE", "Cables", "کابل‌ها")):
        if any(k.startswith(key) or key in k for k in tb):
            issue(m, "ignored", key.lower().replace(" ", "_")[:24], "model", f"{en} were not imported.", f"{fa} وارد نشد.")
    return m
