"""SAP2000 .s2k text export ("$2k" database tables, SAP2000 v14+) of the chat 3D frame.

Same model as the ETABS .e2k exporter (``csi_text_export.build_e2k``): geometry, per-storey sections
(optimizer ``group_sections`` honoured), materials, fixed supports, rigid floor diaphragms, beam line loads,
User-Coefficient seismic patterns, modal case and the design combinations.  Plain text, units KN, m, C.
"""

from __future__ import annotations

import shlex
from typing import Any

from app.application.csi_text_export import _combo_table, _g, frame_layout

S2K_UNVERIFIED = [
    "Not yet opened in a licensed SAP2000 (cannot run on our Linux server): table/field names follow the SAP2000 v14-v24 "
    "$2k database format; use File > Import > SAP2000 .s2k and check the import log.",
    "Seismic EX/EY are written as AUTO SEISMIC - USER COEFFICIENT (C, K) without accidental eccentricity; if SAP2000 "
    "rejects that table delete it and define EX/EY via Define > Load Patterns > User Coefficient.",
    "Floors are rigid diaphragm joint constraints (one per storey); slabs are not shells — floor loads are already beam line loads.",
    "Mass source = element mass (beams MMod=0 because their weight is in the line loads) + 1.0 DEAD + 0.2 LIVE.",
]

_PAT = {"Dead": "DEAD", "Live": "LIVE", "EX": "EX", "EY": "EY"}


def _row(**kv: Any) -> str:
    out = []
    for k, v in kv.items():
        s = v if isinstance(v, str) else _g(float(v))
        if " " in s or s == "" or "," in s:
            s = f'"{s}"'
        out.append(f"{k}={s}")
    return "   " + "   ".join(out)


def build_s2k(inp, raw: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    from app.application.frame3d_chat_analysis import beam_dims, column_dims

    lay = frame_layout(inp)
    ex = raw["export"]
    XS, YS, Z, ns = lay["XS"], lay["YS"], lay["Z"], inp.storeys
    conc, rebar = lay["conc"], lay["rebar"]
    nxy = len(XS) * len(YS)
    jid = lambda i, j, k: str(k * nxy + i * len(YS) + j + 1)  # noqa: E731

    secs: dict[str, tuple[str, float, float]] = {}   # name -> (kind, b, h)
    col_sec, beam_sec = {}, {}
    for k in range(1, ns + 1):
        b, h = column_dims(inp, k); n = f"C{round(b*100):g}X{round(h*100):g}"; secs[n] = ("col", b, h); col_sec[k] = n
        b, h = beam_dims(inp, k); n = f"B{round(b*100):g}X{round(h*100):g}"; secs[n] = ("beam", b, h); beam_sec[k] = n

    T: list[str] = []
    add = T.append
    add('File "model.s2k" exported by SAAI (chat 3D frame) - units KN, m, C')
    add(" ")
    add('TABLE:  "PROGRAM CONTROL"')
    add(_row(ProgramName="SAP2000", Version="14.0.0", CurrUnits="KN, m, C", SteelCode="AISC360-05/IBC2006",
             ConcCode="ACI 318-05/IBC2003", RegenHinge="Yes"))
    add(" ")
    add('TABLE:  "ACTIVE DEGREES OF FREEDOM"')
    add(_row(UX="Yes", UY="Yes", UZ="Yes", RX="Yes", RY="Yes", RZ="Yes"))
    add(" ")
    add('TABLE:  "MATERIAL PROPERTIES 01 - GENERAL"')
    add(_row(Material=conc, Type="Concrete", SymType="Isotropic", TempDepend="No", Color="Gray8Dark"))
    add(_row(Material=rebar, Type="Rebar", SymType="Uniaxial", TempDepend="No", Color="White"))
    add(" ")
    Ec = ex["Ec_kn_m2"]
    add('TABLE:  "MATERIAL PROPERTIES 02 - BASIC MECHANICAL PROPERTIES"')
    add(_row(Material=conc, UnitWeight=25, UnitMass=2.5493, E1=Ec, G12=Ec / 2.4, U12=0.2, A1=1e-5))
    add(_row(Material=rebar, UnitWeight=76.9729, UnitMass=7.849, E1=2e8, A1=1.17e-5))
    add(" ")
    add('TABLE:  "MATERIAL PROPERTIES 03b - CONCRETE DATA"')
    add(_row(Material=conc, Fc=inp.fc_mpa * 1000, LtWtConc="No", SSCurveOpt="Mander", SSHysType="Takeda", SFc=0.002219, SCap=0.005))
    add(" ")
    add('TABLE:  "MATERIAL PROPERTIES 03e - REBAR DATA"')
    add(_row(Material=rebar, Fy=inp.fy_mpa * 1000, Fu=inp.fy_mpa * 1500, EffFy=inp.fy_mpa * 1100, EffFu=inp.fy_mpa * 1650,
             SSCurveOpt="Simple", SSHysType="Kinematic"))
    add(" ")
    add('TABLE:  "FRAME SECTION PROPERTIES 01 - GENERAL"')
    for n, (kind, b, h) in secs.items():
        mods = dict(JMod=0.15, I2Mod=0.7, I3Mod=0.7, MMod=1, WMod=1) if kind == "col" else dict(JMod=0.15, I2Mod=0.35, I3Mod=0.35, MMod=0, WMod=0)
        add(_row(SectionName=n, Material=conc, Shape="Rectangular", t3=h, t2=b, Area=b * h,
                 TorsConst=b * h ** 3 * (1 / 3 - 0.21 * min(b, h) / max(b, h) * (1 - min(b, h) ** 4 / (12 * max(b, h) ** 4))) if b <= h
                 else h * b ** 3 * (1 / 3 - 0.21 * h / b * (1 - h ** 4 / (12 * b ** 4))),
                 I33=b * h ** 3 / 12, I22=h * b ** 3 / 12, AS2=5 / 6 * b * h, AS3=5 / 6 * b * h,
                 AMod=1, A2Mod=1, A3Mod=1, **mods))
    add(" ")
    add('TABLE:  "FRAME SECTION PROPERTIES 02 - CONCRETE COLUMN"')
    for n, (kind, b, h) in secs.items():
        if kind == "col":
            add(_row(SectionName=n, RebarMatL=rebar, RebarMatC=rebar, ReinfConfig="Rectangular", LatReinf="Ties", Cover=0.04,
                     NumBars3Dir=3, NumBars2Dir=3, BarSizeL="20d", BarSizeC="10d", SpacingC=0.15, NumCBars2=3, NumCBars3=3, ReinfType="Design"))
    add(" ")
    add('TABLE:  "FRAME SECTION PROPERTIES 03 - CONCRETE BEAM"')
    for n, (kind, b, h) in secs.items():
        if kind == "beam":
            add(_row(SectionName=n, RebarMatL=rebar, RebarMatC=rebar, TopCover=0.05, BotCover=0.05, TopLeftArea=0, TopRghtArea=0, BotLeftArea=0, BotRghtArea=0))
    add(" ")
    add('TABLE:  "JOINT COORDINATES"')
    for k in range(ns + 1):
        for i, x in enumerate(XS):
            for j, y in enumerate(YS):
                add(_row(Joint=jid(i, j, k), CoordSys="GLOBAL", CoordType="Cartesian", XorR=x, Y=y, Z=Z[k], SpecialJt="No",
                         GlobalX=x, GlobalY=y, GlobalZ=Z[k]))
    add(" ")
    frames: list[tuple[str, str, str, str, int]] = []  # name, ji, jj, section, storey
    for k in range(1, ns + 1):
        for (i, j), p in lay["pts"].items():
            frames.append((f"C{p}_{k}", jid(i, j, k - 1), jid(i, j, k), col_sec[k], k))
    for k in range(1, ns + 1):
        for name, mid, *_r, dirn in lay["lines"]:
            i, j = (int(v) for v in mid[2:].split("_"))
            i2, j2 = (i + 1, j) if dirn == "X" else (i, j + 1)
            frames.append((f"{name}_{k}", jid(i, j, k), jid(i2, j2, k), beam_sec[k], k))
    add('TABLE:  "CONNECTIVITY - FRAME"')
    for n, a, b, _s, _k in frames:
        add(_row(Frame=n, JointI=a, JointJ=b, IsCurved="No"))
    add(" ")
    add('TABLE:  "FRAME SECTION ASSIGNMENTS"')
    for n, _a, _b, s, _k in frames:
        add(_row(Frame=n, SectionType="Rectangular", AutoSelect="N.A.", AnalSect=s, DesignSect=s, MatProp="Default"))
    add(" ")
    add('TABLE:  "FRAME INSERTION POINT ASSIGNMENTS"')
    for n, _a, _b, _s, _k in frames:
        add(_row(Frame=n, CardinalPt=("8 (Top Center)" if n.startswith("B") else "10 (Centroid)"), Mirror2="No", StiffTransform="Yes",
                 Offset1I=0, Offset2I=0, Offset3I=0, Offset1J=0, Offset2J=0, Offset3J=0, CoordSys="Local"))
    add(" ")
    add('TABLE:  "JOINT RESTRAINT ASSIGNMENTS"')
    for i in range(len(XS)):
        for j in range(len(YS)):
            add(_row(Joint=jid(i, j, 0), U1="Yes", U2="Yes", U3="Yes", R1="Yes", R2="Yes", R3="Yes"))
    add(" ")
    add('TABLE:  "CONSTRAINT DEFINITIONS - DIAPHRAGM"')
    for k in range(1, ns + 1):
        add(_row(Name=f"DIAPH{k}", CoordSys="GLOBAL", Axis="Z", MultiLevel="No"))
    add(" ")
    add('TABLE:  "JOINT CONSTRAINT ASSIGNMENTS"')
    for k in range(1, ns + 1):
        for i in range(len(XS)):
            for j in range(len(YS)):
                add(_row(Joint=jid(i, j, k), Constraint=f"DIAPH{k}", Type="Diaphragm"))
    add(" ")
    seismic = "Ex" in ex["reactions"]
    C = (raw.get("base_shear") or {}).get("C")
    kexp = raw["seismic"].get("k", 1.0) or 1.0
    add('TABLE:  "LOAD PATTERN DEFINITIONS"')
    add(_row(LoadPat="DEAD", DesignType="DEAD", SelfWtMult=1))
    add(_row(LoadPat="LIVE", DesignType="LIVE", SelfWtMult=0))
    if seismic:
        add(_row(LoadPat="EX", DesignType="QUAKE", SelfWtMult=0, AutoLoad="User Coefficient"))
        add(_row(LoadPat="EY", DesignType="QUAKE", SelfWtMult=0, AutoLoad="User Coefficient"))
    add(" ")
    if seismic:
        add('TABLE:  "AUTO SEISMIC - USER COEFFICIENT"')
        for nm, d in (("EX", "X"), ("EY", "Y")):
            add(_row(LoadPat=nm, Dir=d, PercentEcc=0, EccOverride="No", UserZ="No", TopZ=Z[-1], BottomZ=0, C=C, K=kexp))
        add(" ")
    add('TABLE:  "MASS SOURCE"')
    add(_row(MassSource="MSSSRC1", Elements="Yes", Masses="Yes", Loads="Yes", IsDefault="Yes", LoadPat="DEAD", Multiplier=1))
    add(_row(MassSource="MSSSRC1", LoadPat="LIVE", Multiplier=0.2))
    add(" ")
    cases = ["DEAD", "LIVE"] + (["EX", "EY"] if seismic else [])
    dtype = {"DEAD": "DEAD", "LIVE": "LIVE", "EX": "QUAKE", "EY": "QUAKE"}
    add('TABLE:  "LOAD CASE DEFINITIONS"')
    for c in cases:
        add(_row(Case=c, Type="LinStatic", InitialCond="Zero", DesTypeOpt="Prog Det", DesignType=dtype[c], AutoType="None", RunCase="Yes"))
    add(_row(Case="MODAL", Type="LinModal", InitialCond="Zero", DesTypeOpt="Prog Det", DesignType="OTHER", AutoType="None", RunCase="Yes"))
    add(" ")
    add('TABLE:  "CASE - STATIC 1 - LOAD ASSIGNMENTS"')
    for c in cases:
        add(_row(Case=c, LoadType="Load pattern", LoadName=c, LoadSF=1))
    add(" ")
    add('TABLE:  "CASE - MODAL 1 - GENERAL"')
    add(_row(Case="MODAL", ModeType="Eigen", MaxNumModes=max(3 * ns, 3), MinNumModes=1, EigenShift=0, EigenCutoff=0, EigenTol=1e-9, AutoShift="Yes"))
    add(" ")
    add('TABLE:  "FRAME LOADS - DISTRIBUTED"')
    for name, mid, *_r in lay["lines"]:
        for k in range(1, ns + 1):
            w = ex["beam_udl"][f"{mid}_{k}"]
            for case, pat in (("D", "DEAD"), ("L", "LIVE")):
                if w[case] > 1e-9:
                    add(_row(Frame=f"{name}_{k}", LoadPat=pat, CoordSys="GLOBAL", Type="Force", Dir="Gravity", DistType="RelDist",
                             RelDistA=0, RelDistB=1, FOverLA=w[case], FOverLB=w[case]))
    add(" ")
    add('TABLE:  "COMBINATION DEFINITIONS"')
    for cname, label, factors in _combo_table(raw):
        first = True
        for pat, sf in factors.items():
            if first:
                add(_row(ComboName=cname, ComboType="Linear Add", AutoDesign="No", CaseType="Linear Static", CaseName=_PAT[pat],
                         ScaleFactor=sf, SteelDesign="None", ConcDesign="Strength", AlumDesign="None", ColdDesign="None", Notes=label))
                first = False
            else:
                add(_row(ComboName=cname, CaseType="Linear Static", CaseName=_PAT[pat], ScaleFactor=sf))
    add(" ")
    add("END TABLE DATA")
    return "\r\n".join(T) + "\r\n"


def parse_s2k(text: str) -> dict[str, list[dict[str, str]]]:
    """Minimal $2k reader: {table name: [row dicts]} (tests / future imports)."""
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
