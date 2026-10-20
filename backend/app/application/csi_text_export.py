"""Text exports of a chat 3D frame model: ETABS .e2k, SAFE .f2k and DXF (plans + 3D wireframe).

No CSI API and no third-party packages are used: every file is written as plain text.

Syntax sources (checked against public files exported by ETABS 2016 v16.2 / ETABS 21-22 and by
ETABS "Export to SAFE"): the $-sections STORIES, GRIDS, DIAPHRAGM NAMES, MATERIAL PROPERTIES,
FRAME SECTIONS, CONCRETE SECTIONS, POINT COORDINATES, LINE CONNECTIVITIES, POINT ASSIGNS,
LINE ASSIGNS, LOAD PATTERNS (incl. SEISMIC "User Coefficient" SHEARCOEFF/HEIGHTEXPONENT),
FRAME OBJECT LOADS, MASS SOURCE, LOAD CASES and LOAD COMBINATIONS follow those files line for line.
Unverified parts are listed in ``E2K_UNVERIFIED`` / ``F2K_UNVERIFIED`` and shown to the user.
"""

from __future__ import annotations

import shlex
from typing import Any

E2K_UNVERIFIED = [
    "Not yet opened in a licensed ETABS: syntax copied from public ETABS 2016/21 exports, import not confirmed.",
    "Seismic EX/EY use DIR \"X\"/\"Y\" without the ±5% accidental eccentricity (our analysis includes it); "
    "set 'X + Ecc. Y' in ETABS if you need it.",
    "Mass source = element self mass (columns only; beam MMOD=0 because beam weight is in the line loads) "
    "+ 1.0·Dead + 0.2·Live loads — check Define > Mass Source after import.",
    "Slabs are not modelled as shells: floor loads are already distributed to beams as line loads (tributary areas).",
]
F2K_UNVERIFIED = [
    "When a foundation design exists the placeholder mat is replaced by one footing area per column (sizes/thickness from the design); soil spring ks is still a placeholder.",
    "Point table, load patterns/cases/combinations and point loads follow an ETABS→SAFE 2014 export (SAFE v12–2016 table names).",
    "The mat outline tables (MATERIAL PROPERTIES 0x, SLAB PROPERTIES 01, SOIL PROPERTIES, OBJECT GEOMETRY - AREAS 01, "
    "SLAB/SOIL PROPERTY ASSIGNMENTS) are written from memory of the SAFE 12 format and are a PLACEHOLDER — "
    "delete them if SAFE rejects the file and draw the mat/footings in SAFE.",
]

FORMATS = {
    "e2k": {"filename": "model.e2k", "label": "ETABS model (.e2k)", "mime": "text/plain"},
    "f2k": {"filename": "foundation.f2k", "label": "SAFE foundation loads (.f2k)", "mime": "text/plain"},
    "dxf_plans": {"filename": "plans.dxf", "label": "AutoCAD plans per storey (.dxf)", "mime": "application/dxf"},
    "dxf_3d": {"filename": "frame3d.dxf", "label": "AutoCAD 3D wireframe (.dxf)", "mime": "application/dxf"},
    "dxf_rebar": {"filename": "rebar-details.dxf", "label": "Rebar detailing sheets + bar bending schedule (.dxf)", "mime": "application/dxf"},
    "dxf_foundation": {"filename": "foundation-details.dxf", "label": "Foundation plan, footing sections + bending schedule (.dxf)", "mime": "application/dxf"},
}


# --------------------------------------------------------------------------- model helpers
def _g(v: float) -> str:
    """Compact, locale-independent number (always '.' decimal)."""
    if abs(v) < 1e-12:
        return "0"
    return (f"{v:.6g}" if abs(v) < 1e5 else f"{v:.7g}").upper()


def _x_label(i: int) -> str:
    return str(i + 1)


def _y_label(j: int) -> str:
    s, n = "", j
    while True:
        s = chr(65 + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            return s


def _sec(prefix: str, b: float, h: float) -> str:
    return f"{prefix}{round(b * 100):g}X{round(h * 100):g}"


def frame_layout(inp) -> dict[str, Any]:
    """Plan points, plan lines and story names shared by all exporters."""
    nx, ny, ns = inp.bays_x, inp.bays_y, inp.storeys
    from app.application.frame3d_chat_analysis import grid_coords

    XS, YS = grid_coords(inp)
    Z = [k * inp.storey_height_m for k in range(ns + 1)]
    pts = {(i, j): str(i * (ny + 1) + j + 1) for i in range(nx + 1) for j in range(ny + 1)}
    lines = []  # (plan name, model-id prefix, point a, point b, dir)
    n = 0
    for j in range(ny + 1):
        for i in range(nx):
            n += 1; lines.append((f"B{n}", f"BX{i}_{j}", pts[(i, j)], pts[(i + 1, j)], "X"))
    for i in range(nx + 1):
        for j in range(ny):
            n += 1; lines.append((f"B{n}", f"BY{i}_{j}", pts[(i, j)], pts[(i, j + 1)], "Y"))
    stories = ["Base"] + [f"Story{k}" for k in range(1, ns + 1)]
    return {"XS": XS, "YS": YS, "Z": Z, "pts": pts, "lines": lines, "stories": stories,
            "col_sec": _sec("C", inp.column_b_m, inp.column_h_m), "beam_sec": _sec("B", inp.beam_b_m, inp.beam_h_m),
            "conc": f"C{inp.fc_mpa:g}", "rebar": f"S{inp.fy_mpa:g}"}


def _combo_table(raw: dict[str, Any]) -> list[tuple[str, str, dict[str, float]]]:
    """[(COMBn, original name, {pattern: factor})] with ETABS pattern names."""
    names = {"D": "Dead", "L": "Live", "Ex": "EX", "Ey": "EY"}
    out = []
    for n, (label, factors) in enumerate(raw["export"]["combo_factors"].items(), start=1):
        out.append((f"COMB{n}", label, {names[c]: v for c, v in factors.items()}))
    return out


# --------------------------------------------------------------------------- ETABS .e2k
def build_e2k(inp, raw: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    lay = frame_layout(inp)
    ex = raw["export"]
    st = lay["stories"]; ns = inp.storeys
    conc, rebar, cs, bs = lay["conc"], lay["rebar"], lay["col_sec"], lay["beam_sec"]
    L: list[str] = []
    add = L.append
    add("$ File model.e2k exported by StructuralAIAgent (chat 3D frame) - units kN, m")
    add(" ")
    add("$ PROGRAM INFORMATION")
    add('  PROGRAM  "ETABS"  VERSION "16.2.1"  ')
    add("")
    add("$ CONTROLS")
    add('  UNITS  "KN"  "M"  "C"  ')
    add('  TITLE1  "StructuralAIAgent"  ')
    add(f'  TITLE2  "{ns}-storey RC frame {inp.bays_x}x{inp.bays_y} bays"  ')
    add("  PREFERENCE  MERGETOL 0.001")
    add("")
    add("$ STORIES - IN SEQUENCE FROM TOP")
    for k in range(ns, 0, -1):
        add(f'  STORY "{st[k]}"  HEIGHT {_g(inp.storey_height_m)}' + (' MASTERSTORY "Yes"  ' if k == ns else " "))
    add('  STORY "Base"  ELEV 0 ')
    add("")
    add("$ GRIDS")
    add('  GRIDSYSTEM "G1"  TYPE "CARTESIAN"  BUBBLESIZE 1.25 ')
    for i, x in enumerate(lay["XS"]):
        add(f'  GRID "G1"  LABEL "{_x_label(i)}"  DIR "X"  COORD {_g(x)} VISIBLE "Yes"  BUBBLELOC "End"  ')
    for j, y in enumerate(lay["YS"]):
        add(f'  GRID "G1"  LABEL "{_y_label(j)}"  DIR "Y"  COORD {_g(y)} VISIBLE "Yes"  BUBBLELOC "Start"  ')
    add("")
    add("$ DIAPHRAGM NAMES")
    add('  DIAPHRAGM "D1"    TYPE RIGID')
    add("")
    add("$ MATERIAL PROPERTIES")
    Ec = ex["Ec_kn_m2"]
    add(f'  MATERIAL  "{conc}"    TYPE "Concrete"    WEIGHTPERVOLUME 25')
    add(f'  MATERIAL  "{conc}"    SYMTYPE "Isotropic"  E {_g(Ec)}  U 0.2  A 1E-05')
    add(f'  MATERIAL  "{conc}"    FC {_g(inp.fc_mpa * 1000)}')
    add(f'  MATERIAL  "{rebar}"    TYPE "Rebar"    WEIGHTPERVOLUME 76.9729')
    add(f'  MATERIAL  "{rebar}"    SYMTYPE "Uniaxial"  E 2E+08  A 1.17E-05')
    add(f'  MATERIAL  "{rebar}"  FY {_g(inp.fy_mpa * 1000)}  FU {_g(inp.fy_mpa * 1500)} FYE {_g(inp.fy_mpa * 1100)}  FUE {_g(inp.fy_mpa * 1650)}')
    add("")
    add("$ FRAME SECTIONS")
    add(f'  FRAMESECTION  "{cs}"  MATERIAL "{conc}"  SHAPE "Concrete Rectangular"  D {_g(inp.column_h_m)} B {_g(inp.column_b_m)} ')
    add(f'  FRAMESECTION  "{bs}"  MATERIAL "{conc}"  SHAPE "Concrete Rectangular"  D {_g(inp.beam_h_m)} B {_g(inp.beam_b_m)} ')
    # cracked-section modifiers used by our analysis; beam weight/mass are carried by the line loads
    add(f'  FRAMESECTION  "{cs}"  JMOD 0.15 I2MOD 0.7 I3MOD 0.7 ')
    add(f'  FRAMESECTION  "{bs}"  JMOD 0.15 I2MOD 0.35 I3MOD 0.35 MMOD 0 WMOD 0 ')
    add("")
    add("$ CONCRETE SECTIONS")
    add(f'  CONCRETESECTION  "{cs}"  LONGBARMATERIAL "{rebar}"  CONFINEBARMATERIAL "{rebar}"  TYPE "Column"  PATTERN "R-3-3"  '
        'TRANSREINF "TIES"  DESIGNCHECK "DESIGN"  COVER 0.04 LONGBARAREA 0.000314 CONFINEBARAREA 7.85E-05 CONFINEBARSPACING 0.15 '
        'NUMCONFINEBARS3 3 NUMCONFINEBARS2 3 ')
    add(f'  CONCRETESECTION  "{bs}"  LONGBARMATERIAL "{rebar}"  CONFINEBARMATERIAL "{rebar}"  TYPE "Beam"  COVERTOP 0.05 COVERBOTTOM 0.05 '
        'ATI 0 ABI 0 ATJ 0 ABJ 0 ')
    add("")
    add("$ POINT COORDINATES")
    for (i, j), p in lay["pts"].items():
        add(f'  POINT "{p}"  {_g(lay["XS"][i])} {_g(lay["YS"][j])} ')
    add("")
    add("$ LINE CONNECTIVITIES")
    for (i, j), p in lay["pts"].items():
        add(f'  LINE  "C{p}"  COLUMN  "{p}"  "{p}"  1')
    for name, _mid, a, b, _d in lay["lines"]:
        add(f'  LINE  "{name}"  BEAM  "{a}"  "{b}"  0')
    add("")
    add("$ POINT ASSIGNS")
    for p in lay["pts"].values():
        add(f'  POINTASSIGN  "{p}"  "Base"  RESTRAINT "UX UY UZ RX RY RZ"  DIAPH "DISCONNECTED"  ')
    for k in range(1, ns + 1):
        for p in lay["pts"].values():
            add(f'  POINTASSIGN  "{p}"  "{st[k]}"  DIAPH "D1"  ')
    add("")
    add("$ LINE ASSIGNS")
    for k in range(ns, 0, -1):
        for p in lay["pts"].values():
            add(f'  LINEASSIGN  "C{p}"  "{st[k]}"  SECTION "{cs}"  CARDINALPT 10  MINNUMSTA 3 AUTOMESH "YES"  MESHATINTERSECTIONS "YES"  ')
        for name, *_ in lay["lines"]:
            add(f'  LINEASSIGN  "{name}"  "{st[k]}"  SECTION "{bs}"  CARDINALPT 8  MAXSTASPC 0.5 AUTOMESH "YES"  MESHATINTERSECTIONS "YES"  ')
    add("")
    seismic = "Ex" in ex["reactions"]
    C = (raw.get("base_shear") or {}).get("C")
    kexp = raw["seismic"].get("k", 1.0) or 1.0
    add("$ LOAD PATTERNS")
    add('  LOADPATTERN "Dead"  TYPE  "Dead"  SELFWEIGHT  1')
    add('  LOADPATTERN "Live"  TYPE  "Live"  SELFWEIGHT  0')
    if seismic:
        for nm, d in (("EX", "X"), ("EY", "Y")):
            add(f'  LOADPATTERN "{nm}"  TYPE  "Seismic"  SELFWEIGHT  0')
            add(f'  SEISMIC "{nm}"  "User Coefficient"    DIR "{d}"    TOPSTORY "{st[ns]}"    BOTTOMSTORY "Base"    '
                f'SHEARCOEFF {_g(C)}  HEIGHTEXPONENT {_g(kexp)}')
    add("")
    add("$ POINT OBJECT LOADS")
    add("")
    add("$ FRAME OBJECT LOADS")
    for name, mid, *_ in lay["lines"]:
        for k in range(1, ns + 1):
            w = ex["beam_udl"][f"{mid}_{k}"]
            for case, pat in (("D", "Dead"), ("L", "Live")):
                if w[case] > 1e-9:
                    add(f'  LINELOAD  "{name}"  "{st[k]}"  TYPE "UNIFF"  DIR "GRAV"  LC "{pat}"  FVAL {_g(w[case])}')
    add("")
    add("$ ANALYSIS OPTIONS")
    add('  ACTIVEDOF "UX UY UZ RX RY RZ"  ')
    add('  PDELTA  METHOD "NONE"  ')
    add("")
    add("$ MASS SOURCE")
    add('  MASSSOURCE  "MsSrc1"    INCLUDEELEMENTS "Yes"    INCLUDEADDEDMASS "No"    INCLUDELOADS "Yes"    INCLUDEMOVE "No"    '
        'INCLUDELATERALMASS "Yes"    INCLUDEVERTICALMASS "No"    LUMPATSTORIES "Yes"    ISDEFAULT "Yes"  ')
    add('  MASSSOURCELOAD  "MsSrc1"  "Dead"  1 ')
    add('  MASSSOURCELOAD  "MsSrc1"  "Live"  0.2 ')
    add("")
    add("$ LOAD CASES")
    add('  LOADCASE "Modal"  TYPE  "Modal - Eigen"  INITCOND  "PRESET"  ')
    add(f'  LOADCASE "Modal"  MAXMODES  {max(3 * ns, 3)} MINMODES  1 EIGENSHIFTFREQ  0 EIGENCUTOFF  0 EIGENTOL  1E-09 ')
    for pat in ["Dead", "Live"] + (["EX", "EY"] if seismic else []):
        add(f'  LOADCASE "{pat}"  TYPE  "Linear Static"  INITCOND  "PRESET"  ')
        add(f'  LOADCASE "{pat}"  LOADPAT  "{pat}"  SF  1 ')
    add("")
    add("$ LOAD COMBINATIONS")
    for cname, label, factors in _combo_table(raw):
        add(f'  COMBO "{cname}"  TYPE "Linear Add"  NOTES "{label}"  ')
        add(f'  COMBO "{cname}"  DESIGN "Concrete"  COMBOTYPE "Strength"  ')
        for pat, sf in factors.items():
            add(f'  COMBO "{cname}"  LOADCASE "{pat}"  SF {_g(sf)} ')
    add("")
    add("$ PROJECT INFORMATION")
    add('  PROJECTINFO    COMPANYNAME "StructuralAIAgent"    MODELNAME "chat-frame3d"  ')
    add("")
    add("$ END OF MODEL FILE")
    return "\r\n".join(L) + "\r\n"


def parse_e2k(text: str) -> dict[str, Any]:
    """Minimal e2k reader (sections → tokenised lines). Used for the round-trip test and future imports."""
    sections: dict[str, list[list[str]]] = {}
    cur = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("$"):
            cur = line[1:].strip()
            if cur.startswith("STORIES"):
                cur = "STORIES"
            sections.setdefault(cur, [])
            continue
        if cur is None:
            raise ValueError(f"data before first section: {line!r}")
        sections[cur].append(shlex.split(line, posix=True))
    out: dict[str, Any] = {"sections": sections}
    # stories (top first) → elevations
    rows = sections.get("STORIES", [])
    elev = {}
    base = next(r for r in rows if "ELEV" in r)
    z = float(base[base.index("ELEV") + 1]); elev[base[1]] = z
    for r in reversed([r for r in rows if "HEIGHT" in r]):
        z += float(r[r.index("HEIGHT") + 1]); elev[r[1]] = z
    out["story_elev"] = elev
    out["points"] = {r[1]: (float(r[2]), float(r[3])) for r in sections.get("POINT COORDINATES", [])}
    out["lines"] = {r[1]: (r[2], r[3], r[4]) for r in sections.get("LINE CONNECTIVITIES", [])}
    out["line_assigns"] = [(r[1], r[2], r[r.index("SECTION") + 1]) for r in sections.get("LINE ASSIGNS", [])]
    out["restraints"] = {r[1] for r in sections.get("POINT ASSIGNS", []) if "RESTRAINT" in r}
    out["diaph"] = [(r[1], r[2]) for r in sections.get("POINT ASSIGNS", []) if "DIAPH" in r and r[r.index("DIAPH") + 1] == "D1"]
    out["frame_sections"] = {r[1]: r for r in sections.get("FRAME SECTIONS", []) if "SHAPE" in r}
    out["line_loads"] = [(r[1], r[2], r[r.index("LC") + 1], float(r[r.index("FVAL") + 1])) for r in sections.get("FRAME OBJECT LOADS", [])]
    out["load_patterns"] = [r[1] for r in sections.get("LOAD PATTERNS", []) if r[0] == "LOADPATTERN"]
    out["seismic"] = {r[1]: {"C": float(r[r.index("SHEARCOEFF") + 1]), "k": float(r[r.index("HEIGHTEXPONENT") + 1]),
                             "dir": r[r.index("DIR") + 1]} for r in sections.get("LOAD PATTERNS", []) if r[0] == "SEISMIC"}
    combos: dict[str, dict[str, float]] = {}
    for r in sections.get("LOAD COMBINATIONS", []):
        if "LOADCASE" in r:
            combos.setdefault(r[1], {})[r[r.index("LOADCASE") + 1]] = float(r[r.index("SF") + 1])
    out["combos"] = combos
    out["mass_source"] = {r[2]: float(r[3]) for r in sections.get("MASS SOURCE", []) if r[0] == "MASSSOURCELOAD"}
    return out


def e2k_members_3d(parsed: dict[str, Any]) -> list[tuple[str, str, tuple, tuple]]:
    """Expand plan lines × story assigns into 3D members (name, kind, end i xyz, end j xyz)."""
    elev = parsed["story_elev"]; order = sorted(elev, key=elev.get)
    below = {order[n]: order[n - 1] for n in range(1, len(order))}
    out = []
    for name, story, _sec in parsed["line_assigns"]:
        kind, a, b = parsed["lines"][name]
        if kind == "COLUMN":
            (x, y) = parsed["points"][a]
            out.append((name, kind, (x, y, elev[below[story]]), (x, y, elev[story])))
        else:
            (x1, y1), (x2, y2) = parsed["points"][a], parsed["points"][b]
            out.append((name, kind, (x1, y1, elev[story]), (x2, y2, elev[story])))
    return out


# --------------------------------------------------------------------------- SAFE .f2k
def build_f2k(inp, raw: dict[str, Any]) -> str:
    lay = frame_layout(inp)
    ex = raw["export"]
    pats = {"D": "DEAD", "L": "LIVE", "Ex": "EX", "Ey": "EY"}
    T: list[str] = []
    add = T.append
    add('File "foundation.f2k" exported by StructuralAIAgent (column reactions of the chat 3D frame; units kN, m)')
    add(" ")
    add('TABLE:  "PROGRAM CONTROL"')
    add('   ProgramName="SAFE 2014"   Version=14.0.0   ProgLevel="Post Tensioning"   CurrUnits="KN, m, C"   ModelDatum=0')
    add(" ")
    add('TABLE:  "GRID LINES"')
    for i, x in enumerate(lay["XS"]):
        add(f'   CoordSys=GLOBAL   AxisDir=X   GridID="{_x_label(i)}"   Ordinate={_g(x)}')
    for j, y in enumerate(lay["YS"]):
        add(f'   CoordSys=GLOBAL   AxisDir=Y   GridID="{_y_label(j)}"   Ordinate={_g(y)}')
    add(" ")
    fd = raw.get("foundation_design")
    ftgs = fd["footings"] if fd and fd.get("status") == "PASS" and fd.get("footings") else None
    ov = 1.0; t_mat = 0.6; ks = 20000.0
    x0, x1 = -ov, lay["XS"][-1] + ov
    y0, y1 = -ov, lay["YS"][-1] + ov
    areas: list[tuple[str, str, list[str]]] = []   # (area name, slab property, corner point names)
    extra_pts: dict[str, tuple[float, float]] = {}
    slabs: dict[str, float] = {}
    if ftgs:
        for n, f_ in enumerate(ftgs, start=1):
            pn = []
            for c, (sx, sy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1)), start=1):
                extra_pts[f"F{n}_{c}"] = (f_["x"] + sx * f_["B_m"] / 2, f_["y"] + sy * f_["B_m"] / 2); pn.append(f"F{n}_{c}")
            prop = f"FTG_H{round(f_['h_m'] * 100)}"
            slabs[prop] = f_["h_m"]
            areas.append((f"FTG{n}", prop, pn))
    else:
        extra_pts = {"M1": (x0, y0), "M2": (x1, y0), "M3": (x1, y1), "M4": (x0, y1)}
        slabs["MAT_PLACEHOLDER"] = t_mat
        areas.append(("MAT1", "MAT_PLACEHOLDER", list(extra_pts)))
    add('TABLE:  "OBJECT GEOMETRY - POINT COORDINATES"')
    for (i, j), p in lay["pts"].items():
        add(f'   Point={p}   GlobalX={_g(lay["XS"][i])}   GlobalY={_g(lay["YS"][j])}   GlobalZ=0   SpecialPt=Yes')
    for name, (x, y) in extra_pts.items():
        add(f'   Point={name}   GlobalX={_g(x)}   GlobalY={_g(y)}   GlobalZ=0   SpecialPt=No')
    add(" ")
    conc = lay["conc"]
    label = "isolated footings from the foundation design" if ftgs else "PLACEHOLDER mat material"
    add('TABLE:  "MATERIAL PROPERTIES 01 - GENERAL"')
    add(f'   Material={conc}   Type=Concrete   Notes="{label}"')
    add(" ")
    add('TABLE:  "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"')
    Ec = ex["Ec_kn_m2"]
    add(f'   Material={conc}   UnitWeight=25   UnitMass=2.5493   E1={_g(Ec)}   G12={_g(Ec / 2.4)}   U12=0.2   A1=1E-05')
    add(" ")
    add('TABLE:  "MATERIAL PROPERTIES 03 - CONCRETE"')
    add(f'   Material={conc}   Fc={_g(inp.fc_mpa * 1000)}   LtWtConc=No')
    add(" ")
    add('TABLE:  "SLAB PROPERTIES 01 - GENERAL"')
    for sname, th in slabs.items():
        add(f'   Slab={sname}   Type={"Footing" if ftgs else "Mat"}   MatProp={conc}   Thickness={_g(th)}   Ortho=No')
    add(" ")
    add('TABLE:  "SOIL PROPERTIES"')
    add(f'   Soil=SOIL_PLACEHOLDER   Subgrade={_g(ks)}   NonlinOpt="Compression Only"')
    add(" ")
    add('TABLE:  "OBJECT GEOMETRY - AREAS 01 - GENERAL"')
    for an, _sp, pn in areas:
        add(f'   Area={an}   NumPoints=4   ' + "   ".join(f"Point{k}={p}" for k, p in enumerate(pn, start=1)))
    add(" ")
    add('TABLE:  "SLAB PROPERTY ASSIGNMENTS"')
    for an, sp, _pn in areas:
        add(f'   Area={an}   SlabProp={sp}')
    add(" ")
    add('TABLE:  "SOIL PROPERTY ASSIGNMENTS"')
    for an, _sp, _pn in areas:
        add(f'   Area={an}   SoilProp=SOIL_PLACEHOLDER')
    add(" ")
    add('TABLE:  "LOAD PATTERNS"')
    add("   LoadPat=DEAD   Type=DEAD   SelfWtMult=1")
    add("   LoadPat=LIVE   Type=LIVE   SelfWtMult=0")
    seismic = "Ex" in ex["reactions"]
    if seismic:
        add("   LoadPat=EX   Type=QUAKE   SelfWtMult=0")
        add("   LoadPat=EY   Type=QUAKE   SelfWtMult=0")
    add(" ")
    add('TABLE:  "LOAD CASES 01 - GENERAL"')
    dtype = {"DEAD": "DEAD", "LIVE": "LIVE", "EX": "QUAKE", "EY": "QUAKE"}
    used = [pats[c] for c in ex["reactions"]]
    for p in used:
        add(f"   LoadCase={p}   Type=LinStatic   DesignType={dtype[p]}")
    add(" ")
    add('TABLE:  "LOAD CASES 06 - LOADS APPLIED"')
    for p in used:
        add(f"   LoadCase={p}   LoadPat={p}   SF=1")
    add(" ")
    add('TABLE:  "LOAD COMBINATIONS"')
    rename = {"Dead": "DEAD", "Live": "LIVE", "EX": "EX", "EY": "EY"}
    combos = [(c, lbl, {rename[k]: v for k, v in f.items()}) for c, lbl, f in _combo_table(raw)]
    service = [("SERV1", "D+L (service, soil pressure)", {"DEAD": 1.0, "LIVE": 1.0})]
    if seismic:
        for s, sg in ((1, "+"), (-1, "-")):
            for E in ("EX", "EY"):
                service.append((f"SERV-{E}{sg}", f"D+0.75L{sg}0.525{E} (service, assumed)", {"DEAD": 1.0, "LIVE": 0.75, E: 0.525 * s}))
    for cname, _lbl, factors in combos + service:
        for pat, sf in factors.items():
            add(f'   Combo={cname}   Load={pat}   Type="Linear Add"   SF={_g(sf)}')
    add(" ")
    add('TABLE:  "LOAD ASSIGNMENTS - POINT LOADS"')
    nodes = {f"N{i}_{j}_0": p for (i, j), p in lay["pts"].items()}
    for case, reac in ex["reactions"].items():
        for nid, r in reac.items():
            fx, fy, fz, mx, my, mz = (-v for v in r)  # load on the foundation = - support reaction
            add(f"   Point={nodes[nid]}   LoadPat={pats[case]}   Fx={_g(fx)}   Fy={_g(fy)}   Fgrav={_g(-fz)}   "
                f"Mx={_g(mx)}   My={_g(my)}   Mz={_g(mz)}   XDim={_g(inp.column_b_m)}   YDim={_g(inp.column_h_m)}")
    add(" ")
    add("END TABLE DATA")
    return "\r\n".join(T) + "\r\n"


def parse_f2k(text: str) -> dict[str, list[dict[str, str]]]:
    tables: dict[str, list[dict[str, str]]] = {}
    cur = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("TABLE:"):
            cur = shlex.split(s[6:])[0]; tables[cur] = []
        elif s == "END TABLE DATA":
            cur = None
        elif s and cur:
            row = {}
            for tok in shlex.split(s):
                k, _, v = tok.partition("=")
                row[k] = v
            tables[cur].append(row)
    return tables


# --------------------------------------------------------------------------- DXF (R12 ASCII, no dependencies)
class _Dxf:
    LAYERS = {"GRID": 8, "GRID_TEXT": 8, "COLUMNS": 1, "BEAMS": 5, "SECTION_TEXT": 3, "TITLE": 7, "DESIGN_TEXT": 6,
              "FRAME_COLUMNS": 1, "FRAME_BEAMS": 5, "FRAME_LABELS": 3, "FOUNDATION": 2, "FOUNDATION_TEXT": 2}

    def __init__(self) -> None:
        self.e: list[str] = []

    def _p(self, *pairs) -> None:
        for code, val in pairs:
            self.e += [str(code), val if isinstance(val, str) else _g(float(val))]

    def line(self, layer, a, b) -> None:
        a = (*a, 0.0)[:3]; b = (*b, 0.0)[:3]
        self._p((0, "LINE"), (8, layer), (10, a[0]), (20, a[1]), (30, a[2]), (11, b[0]), (21, b[1]), (31, b[2]))

    def text(self, layer, p, h, s, center=False) -> None:
        self._p((0, "TEXT"), (8, layer), (10, p[0]), (20, p[1]), (30, 0.0), (40, h), (1, s))
        if center:
            self._p((72, "1"), (73, "2"), (11, p[0]), (21, p[1]), (31, 0.0))

    def circle(self, layer, c, r) -> None:
        self._p((0, "CIRCLE"), (8, layer), (10, c[0]), (20, c[1]), (30, 0.0), (40, r))

    def poly(self, layer, pts, closed=False, three_d=False) -> None:
        flag = (1 if closed else 0) + (8 if three_d else 0)
        self._p((0, "POLYLINE"), (8, layer), (66, "1"), (10, 0.0), (20, 0.0), (30, 0.0), (70, str(flag)))
        for p in pts:
            p = (*p, 0.0)[:3]
            self._p((0, "VERTEX"), (8, layer), (10, p[0]), (20, p[1]), (30, p[2]), (70, "32" if three_d else "0"))
        self._p((0, "SEQEND"), (8, layer))

    def render(self) -> str:
        out = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "6", "0", "ENDSEC",
               "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LTYPE", "70", "1",
               "0", "LTYPE", "2", "CONTINUOUS", "70", "0", "3", "Solid line", "72", "65", "73", "0", "40", "0.0", "0", "ENDTAB",
               "0", "TABLE", "2", "LAYER", "70", str(len(self.LAYERS))]
        for name, color in self.LAYERS.items():
            out += ["0", "LAYER", "2", name, "70", "0", "62", str(color), "6", "CONTINUOUS"]
        out += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"] + self.e + ["0", "ENDSEC", "0", "EOF"]
        return "\r\n".join(out) + "\r\n"


def _design_labels(design: dict[str, Any] | None) -> tuple[dict, dict]:
    beams, cols = {}, {}
    if design and design.get("beams"):
        for b in design["beams"]:
            beams[(b["storey"], b["direction"], b["position"])] = f"T:{b['top_bars']} B:{b['bottom_bars']} {b['stirrups'] or ''}".strip()
        for c in design["columns"]:
            cols[(c["storey"], c["position"])] = f"{c['bars']} {c['ties'] or ''}".strip()
    return beams, cols


def build_dxf_plans(inp, raw: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    lay = frame_layout(inp)
    XS, YS, ns = lay["XS"], lay["YS"], inp.storeys
    nx, ny = inp.bays_x, inp.bays_y
    W, H = XS[-1], YS[-1]
    gap = max(6.0, 0.4 * W) + 4.0
    d = _Dxf()
    blabel, clabel = _design_labels(design)
    cb, ch = inp.column_b_m, inp.column_h_m
    th = max(0.2, min(W, H) / 40)
    for k in range(1, ns + 1):
        ox = (k - 1) * (W + gap)
        ext = 1.5
        d.text("TITLE", (ox, -ext - 2.2), th * 2, f"STORY {k} PLAN (+{lay['Z'][k]:.2f} m)  cols {lay['col_sec']}  beams {lay['beam_sec']}")
        for i, x in enumerate(XS):
            d.line("GRID", (ox + x, -ext), (ox + x, H + ext))
            d.circle("GRID_TEXT", (ox + x, H + ext + 0.5), 0.5)
            d.text("GRID_TEXT", (ox + x, H + ext + 0.5), 0.45, _x_label(i), center=True)
        for j, y in enumerate(YS):
            d.line("GRID", (ox - ext, y), (ox + W + ext, y))
            d.circle("GRID_TEXT", (ox - ext - 0.5, y), 0.5)
            d.text("GRID_TEXT", (ox - ext - 0.5, y), 0.45, _y_label(j), center=True)
        for i, x in enumerate(XS):
            for j, y in enumerate(YS):
                cx, cy = ox + x, y
                d.poly("COLUMNS", [(cx - cb / 2, cy - ch / 2), (cx + cb / 2, cy - ch / 2), (cx + cb / 2, cy + ch / 2), (cx - cb / 2, cy + ch / 2)], closed=True)
                pos = "corner" if (i in (0, nx) and j in (0, ny)) else "edge" if (i in (0, nx) or j in (0, ny)) else "interior"
                d.text("SECTION_TEXT", (cx + cb / 2 + 0.1, cy + ch / 2 + 0.1), th, f"C{lay['pts'][(i, j)]} {lay['col_sec']}")
                if (k, pos) in clabel:
                    d.text("DESIGN_TEXT", (cx + cb / 2 + 0.1, cy - ch / 2 - th - 0.1), th * 0.8, clabel[(k, pos)])
        for name, mid, a, b, dirn in lay["lines"]:
            i, j = (int(v) for v in mid[2:].split("_"))
            if dirn == "X":
                p1, p2 = (ox + XS[i] + cb / 2, YS[j]), (ox + XS[i + 1] - cb / 2, YS[j]); edge = j in (0, ny)
                mx, my = (p1[0] + p2[0]) / 2, YS[j] + 0.15
            else:
                p1, p2 = (ox + XS[i], YS[j] + ch / 2), (ox + XS[i], YS[j + 1] - ch / 2); edge = i in (0, nx)
                mx, my = XS[i] + ox + 0.15, (p1[1] + p2[1]) / 2
            d.line("BEAMS", p1, p2)
            d.text("SECTION_TEXT", (mx, my), th, f"{name} {lay['beam_sec']}")
            key = (k, dirn, "edge" if edge else "interior")
            if key in blabel:
                d.text("DESIGN_TEXT", (mx, my - th * 1.6 if dirn == "X" else my - th * 1.6), th * 0.7, blabel[key])
    fd = raw.get("foundation_design")
    if fd and fd.get("footings"):
        ox = ns * (W + gap)
        d.text("TITLE", (ox, -ext - 2.2), th * 2, f"FOUNDATION PLAN  qa={fd['qa_kpa']:g} kPa" + (" (assumed)" if fd["qa_assumed"] else "")
               + ("  - FOOTINGS OVERLAP, see report" if fd["status"] == "OVERLAP" else ""))
        for i, x in enumerate(XS):
            d.line("GRID", (ox + x, -ext), (ox + x, H + ext))
            d.text("GRID_TEXT", (ox + x, H + ext + 0.5), 0.45, _x_label(i), center=True)
        for j, y in enumerate(YS):
            d.line("GRID", (ox - ext, y), (ox + W + ext, y))
            d.text("GRID_TEXT", (ox - ext - 0.5, y), 0.45, _y_label(j), center=True)
        for f_ in fd["footings"]:
            cx, cy, bq = ox + f_["x"], f_["y"], f_["B_m"] / 2
            d.poly("FOUNDATION", [(cx - bq, cy - bq), (cx + bq, cy - bq), (cx + bq, cy + bq), (cx - bq, cy + bq)], closed=True)
            d.poly("COLUMNS", [(cx - cb / 2, cy - ch / 2), (cx + cb / 2, cy - ch / 2), (cx + cb / 2, cy + ch / 2), (cx - cb / 2, cy + ch / 2)], closed=True)
            d.text("FOUNDATION_TEXT", (cx - bq + 0.1, cy - bq + 0.1), th * 0.8, f"F{f_['B_m']:.1f}x{f_['B_m']:.1f}x{f_['h_m']:.2f}")
        for row in fd["rows"]:
            if row["status"] == "PASS":
                d.text("FOUNDATION_TEXT", (ox, -ext - 3.4 - 0.7 * list(fd["rows"]).index(row)), th * 0.8, f"{row['group']}: {row['bars']}")
    return d.render()


def build_dxf_3d(inp, raw: dict[str, Any]) -> str:
    """3D wireframe (mm, true Z) on the office standard, with a title-block sheet showing an isometric view."""
    import io as _io

    from app.application import drawing_standard as ds

    lay = frame_layout(inp)
    XS, YS, Z, ns = ([v * 1000 for v in lay["XS"]], [v * 1000 for v in lay["YS"]], [v * 1000 for v in lay["Z"]], inp.storeys)
    doc = ds.new_document()
    for name, col in (("FRAME_COLUMNS", 1), ("FRAME_BEAMS", 5), ("FRAME_LABELS", 7)):
        doc.layers.add(name, color=col)
    msp = doc.modelspace()
    for (i, j), _p in lay["pts"].items():
        x, y = XS[i], YS[j]
        msp.add_polyline3d([(x, y, z) for z in Z], dxfattribs={"layer": "FRAME_COLUMNS"})
        for k in range(1, ns + 1):
            msp.add_line((x, y, Z[k - 1]), (x, y, Z[k]), dxfattribs={"layer": "FRAME_COLUMNS"})
    for k in range(1, ns + 1):
        for _name, mid, _a, _b, dirn in lay["lines"]:
            i, j = (int(v) for v in mid[2:].split("_"))
            p1 = (XS[i], YS[j], Z[k])
            p2 = (XS[i + 1], YS[j], Z[k]) if dirn == "X" else (XS[i], YS[j + 1], Z[k])
            msp.add_line(p1, p2, dxfattribs={"layer": "FRAME_BEAMS"})
    W, H, T = XS[-1], YS[-1], Z[-1]
    # 2D isometric projection drawn beside the true-3D model (any viewer, any plotter shows it the same way)
    ox = W + 0.9 * H + 20000
    iso = lambda x, y, z: (ox + (x + H - y) * 0.866, (x + y) * 0.5 + z)  # noqa: E731
    u0, u1, v1 = ox, ox + (W + H) * 0.866, (W + H) * 0.5 + T
    paper, scale = ds.choose_sheet(u1 - u0 + 60 * 100, v1 + 60 * 100)
    pen = ds.Pen(msp, (0, 0), scale)
    for x in XS:
        pen.line("S-AXIS", iso(x, -6 * scale, 0)[:2], iso(x, H + 6 * scale, 0)[:2])
    for y in YS:
        pen.line("S-AXIS", iso(-6 * scale, y, 0)[:2], iso(W + 6 * scale, y, 0)[:2])
    for x in XS:
        for y in YS:
            pen.line("S-CONC", iso(x, y, 0), iso(x, y, T))
    for k in range(1, ns + 1):
        for _name, mid, _a, _b, dirn in lay["lines"]:
            i, j = (int(v) for v in mid[2:].split("_"))
            p1 = (XS[i], YS[j], Z[k])
            p2 = (XS[i + 1], YS[j], Z[k]) if dirn == "X" else (XS[i], YS[j + 1], Z[k])
            pen.line("S-CONC", iso(*p1), iso(*p2))
        pen.level_mark(iso(W, 0, Z[k])[0] + 6 * scale, iso(W, 0, Z[k])[1], Z[k] / 1000)
        pen.text("S-NOTES", (iso(W, 0, Z[k])[0] + 24 * scale, iso(W, 0, Z[k])[1] + 1.2 * scale), f"STORY {k}", h=2.5)
    for i, x in enumerate(XS):
        pen.bubble(iso(x, -6 * scale - 4 * scale * 1.4, 0), _x_label(i))
    for j, y in enumerate(YS):
        pen.bubble(iso(-6 * scale - 4 * scale * 1.4, y, 0), _y_label(j))
    o = (u0 - 5 * scale, v1 - 25 * scale)  # isometric axis tripod
    pen._arrow(o, (o[0] + 10.4 * scale, o[1] + 6 * scale), "X")
    pen._arrow(o, (o[0] - 10.4 * scale, o[1] + 6 * scale), "Y")
    pen._arrow(o, (o[0], o[1] + 12 * scale), "Z")
    pen.text("S-NOTES", (u0, -28 * scale), "Isometric from SE: X to the right-up, Y to the left-up", h=2.5)
    pen.text("S-NOTES", (u0, -32.5 * scale), "3D model (true X/Y/Z, mm) is at the drawing origin: use 3D Orbit", h=2.5)
    pen.text("S-TITLE", ((u0 + u1) / 2, -18 * scale), "3D FRAME - ISOMETRIC VIEW / نمای ایزومتریک قاب", h=5, align="TOP_CENTER")
    ds.add_sheet(doc, "S-3D", (u0 - 20 * scale, -38 * scale, u1 + 40 * scale, v1 + 10 * scale), ds.title_info(inp),
                 "S-3D", "مدل سه‌بعدی قاب", "3D FRAME (ISOMETRIC)", scale=scale)
    buf = _io.StringIO()
    doc.write(buf)
    return buf.getvalue()


def parse_dxf_entities(text: str) -> list[dict[str, Any]]:
    """Group-code reader for our R12 output (tests)."""
    lines = text.splitlines()
    pairs = [(lines[n].strip(), lines[n + 1]) for n in range(0, len(lines) - 1, 2)]
    ents, cur, in_ent = [], None, False
    for code, val in pairs:
        if code == "2" and val == "ENTITIES":
            in_ent = True; continue
        if not in_ent:
            continue
        if code == "0":
            if cur:
                ents.append(cur)
            if val in ("ENDSEC", "EOF"):
                break
            cur = {"type": val}
        elif cur is not None:
            cur.setdefault(code, val)
    return ents


# --------------------------------------------------------------------------- entry points
def build_export(fmt: str, inp, raw: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    if fmt == "e2k":
        return build_e2k(inp, raw, design)
    if fmt == "f2k":
        return build_f2k(inp, raw)
    if fmt == "dxf_plans":
        from app.application.structural_drawings import build_dxf_plans as build_pro_plans

        return build_pro_plans(inp, raw, design)
    if fmt == "dxf_3d":
        return build_dxf_3d(inp, raw)
    if fmt == "dxf_rebar":
        from app.application.rebar_detailing import build_dxf_rebar

        if not design:
            raise ValueError("rebar detailing needs the Mabhas 9 design (design code MABHAS9)")
        return build_dxf_rebar(inp, raw, design)
    if fmt == "dxf_foundation":
        from app.application.foundation_detailing import build_dxf_foundation

        return build_dxf_foundation(inp, raw, design)
    raise ValueError(f"unknown export format {fmt!r}")


def export_descriptors(requested: list[str] | None = None) -> list[dict[str, Any]]:
    req = set(requested or [])
    notes = {"e2k": E2K_UNVERIFIED, "f2k": F2K_UNVERIFIED,
             "dxf_plans": ["DXF R2010 (ezdxf, audited); office drawing standard: A3/A1 paper-space sheets with title block, S-0k story plans, S-10 column/beam schedules, S-F1 foundation plan + footing schedule, E-xx elevations per grid line; units mm."],
             "dxf_3d": ["DXF R12 ASCII; LINE entities with Z plus one 3D POLYLINE per column stack (use 3D Orbit)."],
             "dxf_rebar": ["DXF R2010 (ezdxf, audited); sheets R-01 beams, R-02 columns, R-03 bar bending schedule; units mm.",
                           "Detailing rules marked [code] / [assumed] on sheet R-03; engineer review required before construction."],
             "dxf_foundation": ["DXF R2010 (ezdxf, audited); FD-01 footing plan + schedule, FD-02 sections per footing type + bending schedule; units mm.",
                                "Footings designed to Mabhas 9 (flexure at the column face, one-way and punching shear); cover/Df/lean concrete changeable from chat."]}
    return [{"format": f, **{k: v for k, v in meta.items()}, "requested": f in req, "notes": notes[f]} for f, meta in FORMATS.items()]
