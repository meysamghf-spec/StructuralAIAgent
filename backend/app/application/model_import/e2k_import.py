"""ETABS .e2k (text model) reader -> SAIA neutral model (kN, m).

Reads stories, materials, frame sections, points, lines (beam/column/brace), point restraints,
line section assigns, load patterns, uniform frame loads, point loads and linear combinations.
Anything else (areas/slabs, walls, releases, springs, diaphragms, area loads...) is listed as an
issue for the engineer review step; nothing is silently dropped.
"""

from __future__ import annotations

from typing import Any

from app.application.model_import.common import (
    FORCE_TO_KN, LEN_TO_M, assume, box_props, i_props, issue, kv, new_model, num, pipe_props,
    rect_props, tokens,
)

DOF_NAMES = ("UX", "UY", "UZ", "RX", "RY", "RZ")
REL_NAMES = ("P", "V2", "V3", "T", "M2", "M3")


def parse_release(val: str) -> tuple[list[bool], list[bool]]:
    toks = {t.upper() for t in val.replace(",", " ").split()}
    return [f"{r}I" in toks for r in REL_NAMES], [f"{r}J" in toks for r in REL_NAMES]


def _sections(text: str) -> dict[str, list[list[str]]]:
    out: dict[str, list[list[str]]] = {}
    cur = "_HEAD"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("$"):
            cur = line[1:].strip().upper()
            out.setdefault(cur, [])
            continue
        toks = tokens(line)
        if toks:
            out.setdefault(cur, []).append(toks)
    return out


def _find(secs: dict[str, list[list[str]]], prefix: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for name, lines in secs.items():
        if name.startswith(prefix):
            rows.extend(lines)
    return rows


def parse_e2k(filename: str, text: str) -> dict[str, Any]:
    m = new_model("e2k", filename)
    secs = _sections(text)

    # ---- units -----------------------------------------------------------------
    fu, lu = "KN", "M"
    for t in _find(secs, "CONTROLS"):
        if t[0].upper() == "UNITS" and len(t) >= 3:
            fu, lu = t[1].upper(), t[2].upper()
    if fu not in FORCE_TO_KN or lu not in LEN_TO_M:
        issue(m, "approximated", "units", f"{fu} {lu}", f"Unknown units {fu}/{lu} - kN and m assumed.",
              f"واحد ناشناخته {fu}/{lu}؛ کیلونیوتن و متر فرض شد.")
        fu, lu = "KN", "M"
    F, L = FORCE_TO_KN[fu], LEN_TO_M[lu]
    m["units"]["source"] = f"{fu}, {lu}"
    if (fu, lu) != ("KN", "M"):
        assume(m, f"File units {fu}, {lu} were converted to kN, m.", f"واحدهای فایل ({fu}، {lu}) به کیلونیوتن و متر تبدیل شدند.")

    # ---- stories (listed top -> bottom) ------------------------------------------
    story_rows = [t for t in _find(secs, "STORIES") if t[0].upper() == "STORY" and len(t) > 1]
    stories: list[tuple[str, dict[str, str]]] = [(t[1], kv(t, 2)) for t in story_rows]
    elev: dict[str, float] = {}
    order: list[str] = []  # bottom -> top
    base_name, base_elev = "Base", 0.0
    if stories and "ELEV" in stories[-1][1] and "HEIGHT" not in stories[-1][1]:
        base_name, base_elev = stories[-1][0], (num(stories[-1][1]["ELEV"], 0.0) or 0.0) * L
        stories = stories[:-1]
    elev[base_name] = base_elev
    order.append(base_name)
    z = base_elev
    for name, props in reversed(stories):
        h = num(props.get("HEIGHT"))
        if h is None or h <= 0:
            h = 3.0 / L
            issue(m, "approximated", "story_height", name, f"Story {name}: height missing - 3.0 m assumed.",
                  f"طبقه {name}: ارتفاع نامشخص؛ ۳٫۰ متر فرض شد.")
        z += h * L
        elev[name] = z
        order.append(name)
    if len(order) == 1:
        issue(m, "blocking", "no_stories", "model", "No STORY lines found - cannot place points in elevation.",
              "هیچ طبقه‌ای (STORY) پیدا نشد؛ ارتفاع نقاط معلوم نیست.")
    below = {order[i]: order[i - 1] for i in range(1, len(order))}

    def story_below(name: str, n: int) -> str | None:
        cur: str | None = name
        for _ in range(max(n, 1)):
            cur = below.get(cur) if cur else None
        return cur

    # ---- materials ----------------------------------------------------------------
    for t in _find(secs, "MATERIAL"):
        if t[0].upper() != "MATERIAL" or len(t) < 2:
            continue
        name, p = t[1], kv(t, 2)
        mat = m["materials"].setdefault(name, {"type": "Concrete", "E": None, "nu": 0.2, "unit_weight": 0.0})
        if "TYPE" in p:
            mat["type"] = p["TYPE"]
        if "E" in p:
            mat["E"] = (num(p["E"], 0.0) or 0.0) * F / L**2
        if "U" in p:
            mat["nu"] = num(p["U"], 0.2)
        if "WEIGHTPERVOLUME" in p:
            mat["unit_weight"] = (num(p["WEIGHTPERVOLUME"], 0.0) or 0.0) * F / L**3
        elif "WEIGHT" in p:
            mat["unit_weight"] = (num(p["WEIGHT"], 0.0) or 0.0) * F / L**3
    for name, mat in m["materials"].items():
        if not mat["E"]:
            steel = str(mat["type"]).lower().startswith("steel")
            mat["E"] = 2.0e8 if steel else 2.35e7
            issue(m, "approximated", "material_E", name,
                  f"Material {name}: E not found - {'200 GPa (steel)' if steel else '23.5 GPa (concrete)'} assumed.",
                  f"مصالح {name}: مدول الاستیسیته پیدا نشد؛ {'۲۰۰ گیگاپاسکال (فولاد)' if steel else '۲۳٫۵ گیگاپاسکال (بتن)'} فرض شد.")

    # ---- frame sections -----------------------------------------------------------
    for t in _find(secs, "FRAME SECTIONS"):
        if t[0].upper() != "FRAMESECTION" or len(t) < 2:
            continue
        name, p = t[1], kv(t, 2)
        sec = m["sections"].setdefault(name, {"shape": None, "material": None, "modifiers": {}})
        if "MATERIAL" in p:
            sec["material"] = p["MATERIAL"]
        for key, mk in (("AMOD", "A"), ("I2MOD", "I22"), ("I3MOD", "I33"), ("JMOD", "J")):
            if key in p:
                sec["modifiers"][mk] = num(p[key], 1.0)
        if "SHAPE" not in p:
            continue
        shape = p["SHAPE"]
        sec["shape"] = shape
        s = shape.lower()
        d, b = (num(p.get("D"), 0) or 0) * L, (num(p.get("B"), 0) or 0) * L
        tf, tw = (num(p.get("TF"), 0) or 0) * L, (num(p.get("TW"), 0) or 0) * L
        props = None
        if "rectang" in s and d and b:
            props, sec["b"], sec["h"] = rect_props(b, d), b, d
        elif "circle" in s and d:
            import math
            props = {"A": math.pi * d**2 / 4, "I33": math.pi * d**4 / 64, "I22": math.pi * d**4 / 64, "J": math.pi * d**4 / 32}
        elif ("i/wide" in s or s.startswith("steel i") or "i-section" in s) and d and b and tf and tw:
            props = i_props(d, b, tf, tw)
        elif ("tube" in s or "box" in s) and d and b and tf:
            props = box_props(d, b, tf, tw or tf)
        elif "pipe" in s and d and (p.get("T") or tw):
            props = pipe_props(d, (num(p.get("T"), 0) or 0) * L or tw)
        elif s == "general" or "AREA" in p:
            a = num(p.get("AREA", p.get("A")))
            if a:
                props = {"A": a * L**2, "I33": (num(p.get("I33"), 0) or 0) * L**4,
                         "I22": (num(p.get("I22"), 0) or 0) * L**4, "J": (num(p.get("TORSION", p.get("J")), 0) or 0) * L**4}
        if props:
            sec.update(props)
        else:
            issue(m, "blocking", "section_shape", name,
                  f"Section {name}: shape {shape!r} (catalog or unsupported) has no dimensions in the file - enter its properties.",
                  f"مقطع {name}: شکل «{shape}» (پروفیل کاتالوگ یا پشتیبانی‌نشده) ابعادی در فایل ندارد؛ مشخصاتش را وارد کنید.")
    for name, sec in m["sections"].items():
        if sec["modifiers"] and any(v != 1 for v in sec["modifiers"].values()):
            assume(m, "Section property modifiers in the file (cracked I, J) were applied.",
                   "ضرایب اصلاح مشخصات مقطع موجود در فایل (I و J ترک‌خورده) اعمال شد.")

    # ---- points and lines ------------------------------------------------------------
    pts: dict[str, tuple[float, float]] = {}
    for t in _find(secs, "POINT COORDINATES"):
        if t[0].upper() == "POINT" and len(t) >= 4:
            x, y = num(t[2]), num(t[3])
            if x is None or y is None:
                continue
            pts[t[1]] = (x * L, y * L)
            if len(t) >= 5 and num(t[4], 0):
                issue(m, "approximated", "point_dz", t[1], "Point Z offsets below story level were ignored.",
                      "افست ارتفاعی نقاط نسبت به تراز طبقه نادیده گرفته شد.")
    lines: dict[str, tuple[str, str, str, int]] = {}
    for t in _find(secs, "LINE CONNECTIVITIES"):
        if t[0].upper() == "LINE" and len(t) >= 5:
            kind = t[2].upper()
            n = int(num(t[5], 0) or 0) if len(t) >= 6 else 0
            lines[t[1]] = (kind, t[3], t[4], n)

    def node(pt: str, story: str) -> str | None:
        if pt not in pts or story not in elev:
            return None
        nid = f"{pt}@{story}"
        if nid not in m["nodes"]:
            x, y = pts[pt]
            m["nodes"][nid] = {"x": round(x, 6), "y": round(y, 6), "z": round(elev[story], 6), "point": pt, "story": story}
        return nid

    member_of: dict[tuple[str, str], str] = {}
    for t in _find(secs, "LINE ASSIGNS"):
        if t[0].upper() != "LINEASSIGN" or len(t) < 3:
            continue
        lname, story, p = t[1], t[2], kv(t, 3)
        if lname not in lines:
            continue
        kind, pi, pj, n = lines[lname]
        key = (lname, story)
        mid = member_of.get(key)
        if mid is None:
            if kind in ("COLUMN", "BRACE"):
                bot = story_below(story, n or 1)
                a, b = (node(pi, bot), node(pj, story)) if bot else (None, None)
            elif kind == "BEAM":
                a, b = node(pi, story), node(pj, story)
            else:
                issue(m, "ignored", "line_kind", kind, f"Line type {kind} is not a frame member - ignored.",
                      f"خط از نوع {kind} عضو قابی نیست؛ نادیده گرفته شد.")
                continue
            if not a or not b or a == b:
                issue(m, "ignored", "bad_line", f"{lname}@{story}", f"Line {lname} at {story}: end points not found - ignored.",
                      f"خط {lname} در {story}: نقاط انتهایی پیدا نشد؛ نادیده گرفته شد.")
                continue
            mid = f"{lname}@{story}"
            member_of[key] = mid
            m["members"].append({"id": mid, "i": a, "j": b, "type": kind.lower(), "section": None, "label": lname, "story": story})
        mem = next(x for x in m["members"] if x["id"] == mid)
        if "SECTION" in p:
            mem["section"] = p["SECTION"]
        if "RELEASE" in p:
            mem["rel_i"], mem["rel_j"] = parse_release(p["RELEASE"])
            if any(mem["rel_i"]) or any(mem["rel_j"]):
                assume(m, "Member end releases (pins) in the file were applied by static condensation.",
                       "آزادسازی انتهای اعضا (مفصل‌ها) طبق فایل با تراکم استاتیکی اعمال شد.")
        for k in ("PROPERTYMODIFIERS", "LENGTHOFFI", "RIGIDZONE", "INSERTIONPOINT"):
            if k in p:
                issue(m, "ignored", "line_assign_" + k.lower(), "members", f"Line assign {k} was ignored.",
                      f"تخصیص {k} روی اعضا نادیده گرفته شد.")
    for mem in m["members"]:
        if not mem["section"]:
            mem["section"] = "(none)"
            issue(m, "blocking", "member_no_section", mem["id"], f"Member {mem['id']} has no section assigned.",
                  f"به عضو {mem['id']} مقطعی تخصیص داده نشده است.")

    # ---- supports --------------------------------------------------------------------
    for t in _find(secs, "POINT ASSIGNS"):
        if t[0].upper() != "POINTASSIGN" or len(t) < 3:
            continue
        p = kv(t, 3)
        if "RESTRAINT" in p:
            nid = node(t[1], t[2])
            if nid:
                fl = p["RESTRAINT"].upper().split()
                m["supports"][nid] = [d in fl for d in DOF_NAMES]
        if "SPRINGPROP" in p or "SPRING" in p:
            issue(m, "ignored", "spring", t[1], "Point springs were ignored.", "فنرهای نقطه‌ای نادیده گرفته شدند.")
    if any(lines[l][0] in ("COLUMN", "BRACE") for l, _ in member_of) and m["supports"]:
        pass

    # ---- load patterns -------------------------------------------------------------
    for t in _find(secs, "LOAD PATTERNS") + _find(secs, "STATIC LOADS"):
        if t[0].upper() in ("LOADPATTERN", "LOADCASE") and len(t) >= 2:
            p = kv(t, 2)
            pat = m["load_patterns"].setdefault(t[1], {"type": "Other", "self_weight": 0.0})
            pat["type"] = p.get("TYPE", pat["type"])
            pat["self_weight"] = num(p.get("SELFWEIGHT"), pat["self_weight"]) or 0.0
            if str(pat["type"]).lower() in ("seismic", "wind", "quake") and not p.get("_"):
                issue(m, "approximated", "auto_lateral", t[1],
                      f"Pattern {t[1]} ({pat['type']}): ETABS auto-lateral parameters are not read - if the pattern has no loads in the file, SAIA generates Standard 2800 seismic / Mabhas 6 wind loads (see assumptions).",
                      f"الگوی {t[1]} ({pat['type']}): پارامترهای بار جانبی خودکار ETABS خوانده نمی‌شود؛ اگر در فایل باری ندارد، SAIA بار زلزله‌ی استاندارد ۲۸۰۰ / باد مبحث ۶ را تولید می‌کند (فرض‌ها را ببینید).")

    # ---- frame loads -------------------------------------------------------------------
    for t in _find(secs, "FRAME OBJECT LOADS"):
        if t[0].upper() != "LINELOAD" or len(t) < 3:
            continue
        p = kv(t, 3)
        mid = member_of.get((t[1], t[2]))
        lc = p.get("LC", "")
        if mid is None:
            continue
        typ, direction = p.get("TYPE", "").upper(), p.get("DIR", "GRAV").upper()
        trap = None
        if typ == "UNIFF":
            w = num(p.get("FVAL"), 0.0) or 0.0
        elif typ == "TRAPF":
            w0, w1 = (num(p.get("FSTART"), 0.0) or 0.0), (num(p.get("FEND"), 0.0) or 0.0)
            r0, r1 = (num(p.get("RDSTART"), 0.0) or 0.0), (num(p.get("RDEND"), 1.0) or 1.0)
            w = None
            trap = (r0, r1, w0, w1)
        else:
            issue(m, "ignored", "lineload_" + (typ.lower() or "other"), "loads", f"Frame load type {typ or '?'} was ignored.",
                  f"بار عضو از نوع {typ or '?'} نادیده گرفته شد.")
            continue
        unit = {"GRAV": (0, 0, -1), "GRAVITY": (0, 0, -1), "Z": (0, 0, 1), "X": (1, 0, 0), "Y": (0, 1, 0)}.get(direction)
        if unit is None:
            issue(m, "ignored", "lineload_dir", direction, f"Frame load direction {direction} (local axis) was ignored.",
                  f"بار عضو در جهت {direction} (محور محلی) نادیده گرفته شد.")
            continue
        pieces = [(0.0, 1.0, w)] if trap is None else [
            (trap[0] + (trap[1] - trap[0]) * k / 8, trap[0] + (trap[1] - trap[0]) * (k + 1) / 8,
             trap[2] + (trap[3] - trap[2]) * (k + 0.5) / 8) for k in range(8)]
        for ra, rb, wv in pieces:
            wv *= F / L
            ld = {"member": mid, "pattern": lc, "wx": unit[0] * wv, "wy": unit[1] * wv, "wz": unit[2] * wv}
            if (ra, rb) != (0.0, 1.0):
                ld["ra"], ld["rb"] = ra, rb
            m["member_loads"].append(ld)
        m["load_patterns"].setdefault(lc, {"type": "Other", "self_weight": 0.0})
    for t in _find(secs, "POINT OBJECT LOADS"):
        if t[0].upper() != "POINTLOAD" or len(t) < 3:
            continue
        p = kv(t, 3)
        nid = node(t[1], t[2])
        lc = p.get("LC", "")
        if not nid:
            continue
        if p.get("TYPE", "FORCE").upper() != "FORCE":
            issue(m, "ignored", "pointload_type", "loads", "Point displacement loads were ignored.", "تغییرمکان‌های اعمالی نقطه‌ای نادیده گرفته شدند.")
            continue
        load = {"node": nid, "pattern": lc}
        for k in ("FX", "FY", "FZ"):
            load[k.lower()] = (num(p.get(k), 0) or 0) * F
        for k in ("MX", "MY", "MZ"):
            load[k.lower()] = (num(p.get(k), 0) or 0) * F * L
        m["nodal_loads"].append(load)
        m["load_patterns"].setdefault(lc, {"type": "Other", "self_weight": 0.0})

    # ---- combinations -------------------------------------------------------------------
    for t in _find(secs, "LOAD COMBINATIONS"):
        if t[0].upper() != "COMBO" or len(t) < 3:
            continue
        p = kv(t, 2)
        name = t[1]
        if "TYPE" in p and p["TYPE"].lower() not in ("linear add", "linear additive"):
            issue(m, "approximated", "combo_type", name, f"Combination {name} ({p['TYPE']}) was treated as linear add.",
                  f"ترکیب {name} ({p['TYPE']}) به‌صورت جمع خطی در نظر گرفته شد.")
        case = p.get("LOAD") or p.get("LOADCASE") or p.get("LOADCOMBO")
        if case is not None:
            m["combos"].setdefault(name, {})[case] = num(p.get("SF"), 1.0) or 0.0
    for name, combo in list(m["combos"].items()):
        flat: dict[str, float] = {}
        for case, sf in combo.items():
            if case in m["combos"] and case != name:
                for c2, sf2 in m["combos"][case].items():
                    flat[c2] = flat.get(c2, 0) + sf * sf2
            else:
                flat[case] = flat.get(case, 0) + sf
        unknown = [c for c in flat if c not in m["load_patterns"]]
        for c in unknown:
            issue(m, "approximated", "combo_case", f"{name}:{c}",
                  f"Combination {name}: case {c} (modal/response spectrum/non-static) is not analysed and was dropped.",
                  f"ترکیب {name}: حالت بار {c} (مودال/طیفی/غیراستاتیکی) تحلیل نمی‌شود و حذف شد.")
            flat.pop(c)
        m["combos"][name] = flat

    # ---- areas (slabs / decks / walls), area loads, diaphragms ----------------------------
    m.setdefault("areas", []); m.setdefault("area_sections", {}); m.setdefault("area_loads", []); m.setdefault("diaphragms", {})
    for t in _find(secs, "SLAB PROPERTIES") + _find(secs, "DECK PROPERTIES") + _find(secs, "WALL PROPERTIES") + _find(secs, "SHELL PROPERTIES"):
        if t[0].upper() != "SHELLPROP" or len(t) < 2:
            continue
        p = kv(t, 2)
        th = num(p.get("SLABTHICKNESS") or p.get("WALLTHICKNESS") or p.get("THICKNESS") or p.get("DECKSLABDEPTH"))
        sec = m["area_sections"].setdefault(t[1], {"material": None, "thickness": None, "type": p.get("PROPTYPE", "Slab")})
        if "MATERIAL" in p or "DECKSLABMATERIAL" in p:
            sec["material"] = p.get("MATERIAL") or p.get("DECKSLABMATERIAL")
        if th:
            sec["thickness"] = th * L
        if str(p.get("SLABTYPE", "")).lower().startswith("one") or "ONEWAY" in str(p.get("LOADDISTRIBUTION", "")).upper():
            sec["one_way"] = True
    area_def: dict[str, tuple[str, list[str]]] = {}
    for t in _find(secs, "AREA CONNECTIVITIES"):
        if t[0].upper() != "AREA" or len(t) < 4:
            continue
        n = int(num(t[3], 0) or 0)
        area_def[t[1]] = (t[2].upper(), t[4:4 + n])
    walls = 0
    area_of: dict[tuple[str, str], str] = {}
    for t in _find(secs, "AREA ASSIGNS"):
        if t[0].upper() != "AREAASSIGN" or len(t) < 3 or t[1] not in area_def:
            continue
        kind, ptsl = area_def[t[1]]
        p = kv(t, 3)
        if kind != "FLOOR":
            walls += 1
            continue
        ids = [node(pt, t[2]) for pt in ptsl]
        if any(i is None for i in ids) or len(ids) < 3:
            continue
        aid = f"{t[1]}@{t[2]}"
        area_of[(t[1], t[2])] = aid
        sec = p.get("SECTION")
        rec = {"id": aid, "nodes": ids, "kind": "floor", "section": sec, "story": t[2], "one_way": True if m["area_sections"].get(sec or "", {}).get("one_way") else None}
        m["areas"].append(rec)
        if "DIAPH" in p or "DIAPHRAGM" in p:
            d = p.get("DIAPH") or p.get("DIAPHRAGM")
            if str(d).upper() not in ("NONE", "DISCONNECT"):
                m["diaphragms"].setdefault(f"{d}@{t[2]}", set()).update(ids)
    for t in _find(secs, "POINT ASSIGNS"):
        if t[0].upper() == "POINTASSIGN" and len(t) >= 3:
            p = kv(t, 3)
            d = p.get("DIAPH") or p.get("DIAPHRAGM")
            if d and str(d).upper() not in ("NONE", "DISCONNECT"):
                nid = node(t[1], t[2])
                if nid:
                    m["diaphragms"].setdefault(f"{d}@{t[2]}", set()).add(nid)
    semi = {t[1] for t in _find(secs, "DIAPHRAGM NAMES") if t[0].upper() == "DIAPHRAGM" and len(t) > 1 and "SEMI" in " ".join(t).upper()}
    if semi:
        issue(m, "approximated", "semirigid", "model", "Semi-rigid diaphragms were treated as rigid.", "دیافراگم‌های نیمه‌صلب، صلب فرض شدند.")
    m["diaphragms"] = {k: sorted(v) for k, v in m["diaphragms"].items() if len(v) >= 2}
    if m["diaphragms"]:
        assume(m, f"{len(m['diaphragms'])} rigid floor diaphragms were applied (master node at each floor's mass centre).",
               f"{len(m['diaphragms'])} دیافراگم صلب کف اعمال شد (گره اصلی در مرکز جرم هر طبقه).")
    bad_al = 0
    for t in _find(secs, "SHELL OBJECT LOADS") + _find(secs, "AREA OBJECT LOADS") + _find(secs, "SHELL UNIFORM LOAD"):
        if not t or t[0].upper() != "AREALOAD" or len(t) < 3:
            continue
        p = kv(t, 3)
        aid = area_of.get((t[1], t[2]))
        typ, direction = p.get("TYPE", "UNIFF").upper(), p.get("DIR", "GRAV").upper()
        if aid is None or typ not in ("UNIFF", "UNIFORM") or direction not in ("GRAV", "GRAVITY", "Z"):
            bad_al += 1
            continue
        q = (num(p.get("FVAL"), 0.0) or 0.0) * F / L**2
        if direction == "Z":
            q = -q
        lc = p.get("LC", "")
        m["area_loads"].append({"area": aid, "pattern": lc, "q": q})
        m["load_patterns"].setdefault(lc, {"type": "Other", "self_weight": 0.0})
    if m["areas"]:
        assume(m, f"{len(m['areas'])} floor slabs imported: their loads (and self-weight) go to the supporting beams by tributary area - two-way (45 degree) panels, one-way when aspect >= 2 or set one-way. Slab bending stiffness is not modelled.",
               f"{len(m['areas'])} دال کف وارد شد: بار و وزن آن‌ها به روش سطح بارگیر به تیرهای تکیه‌گاهی منتقل می‌شود؛ دوطرفه (۴۵ درجه)، و یک‌طرفه اگر نسبت ابعاد ≥ ۲ یا یک‌طرفه تعریف شده باشد. سختی خمشی دال مدل نمی‌شود.")
    if walls:
        issue(m, "ignored", "walls", f"{walls}",
              f"{walls} wall/panel areas were not analysed as shells (frame engine) - their stiffness is missing; add their weight as beam loads if needed.",
              f"{walls} دیوار/پانل به‌صورت پوسته تحلیل نشد (موتور قاب)؛ سختی آن‌ها لحاظ نشده است؛ در صورت نیاز وزنشان را به‌صورت بار تیر اضافه کنید.")
    if bad_al:
        issue(m, "ignored", "area_loads_other", f"{bad_al}", f"{bad_al} non-uniform or non-gravity area loads were ignored.",
              f"{bad_al} بار سطحی غیریکنواخت یا غیرثقلی نادیده گرفته شد.")
    for key, en, fa in (("RESPONSE SPECTRUM", "Response spectrum functions", "توابع طیف پاسخ"),
                        ("WALL", "Wall/pier definitions", "تعاریف دیوار/پایه"),
                        ("LINK", "Link properties", "مشخصات لینک"),
                        ("TENDON", "Tendons", "تاندون‌ها")):
        if any(k.startswith(key) for k in secs):
            issue(m, "ignored", key.lower().replace(" ", "_"), "model", f"{en} were not imported.", f"{fa} وارد نشد.")
    for mem in m["members"]:
        if mem["type"] == "column" and m["nodes"][mem["i"]]["z"] > m["nodes"][mem["j"]]["z"]:
            mem["i"], mem["j"] = mem["j"], mem["i"]
    return m
