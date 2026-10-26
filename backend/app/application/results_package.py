"""Downloadable outputs of a 3D frame run: tables (xlsx/csv), figures (png/svg), drawings (dxf/pdf), model exports, report, ZIP.

Generic for any frame the in-house solver supports; everything is rebuilt deterministically from the run ``inputs``.
"""
from __future__ import annotations

import csv
import io
import json
import math
import zipfile
from typing import Any, Callable

Table = tuple[list[str], list[list[Any]]]

TABLES: dict[str, str] = {
    "joint_displacements": "Joint displacements (mm) per case/combo",
    "reactions": "Support reactions per case/combo",
    "member_forces": "Member forces N/V/M per case/combo",
    "storey_drift": "Storey drift (2800)",
    "modal": "Modal periods + mass participation",
    "base_shear": "Base shear / Standard 2800 checks",
    "design_beams": "Beam design D/C + rebar",
    "design_columns": "Column design D/C + rebar",
    "design_scwb": "Strong-column/weak-beam checks",
    "foundation": "Foundation design (groups)",
    "footings": "Footings (per column)",
    "optimization": "Optimization results",
}
FIGURES: dict[str, str] = {
    "view3d": "3D view", "deformed": "Deformed shape (governing combo)", "moment": "Bending-moment diagram (grid A)",
    "shear": "Shear diagram (grid A)", "axial": "Axial force diagram (grid A)", "drift": "Storey drift plot",
    "mode1": "Mode shape 1", "mode2": "Mode shape 2", "mode3": "Mode shape 3",
}
MODELS = {"e2k": "ETABS (.e2k)", "f2k": "SAFE (.f2k)", "s2k": "SAP2000 (.s2k)"}
DRAWINGS = {"dxf_plans": "Plans (.dxf)", "dxf_3d": "3D wireframe (.dxf)", "dxf_rebar": "Rebar details (.dxf)",
            "dxf_foundation": "Foundation details (.dxf)", "structural_set": "Structural drawing set (PDF + DXF)"}


def catalog() -> dict[str, Any]:
    return {"tables": TABLES, "figures": FIGURES, "models": MODELS, "drawings": DRAWINGS,
            "report": {"report_pdf": "Calculation report (.pdf)", "report_md": "Calculation report (.md)", "report_json": "Raw results (.json)"},
            "formats": {"tables": ["xlsx", "csv"], "figures": ["png", "svg"], "drawings": ["dxf", "pdf"]}}


# ------------------------------------------------------------------ run
def run(inputs: dict[str, Any]):
    from app.application.frame3d_chat_analysis import run_frame3d_for_export
    data = {"design_code": "MABHAS9", "seismic_code": "IRAN_2800", "foundation": True, **inputs}
    if data.get("seismic_code") in (None, "", "ASSUMED_C") and data.get("seismic_c") in (None, ""):
        data["seismic_code"] = "IRAN_2800"  # Iranian default: gives drift, modal + 2800 base-shear tables
    return run_frame3d_for_export(data)


def _combos(v: dict[str, Any]) -> dict[str, dict[str, float]]:
    out = {c: {c: 1.0} for c in v.get("cases") or []}
    out.update(v.get("combos") or {})
    return out


def _comb(per_case: dict[str, dict[str, list[float]]], factors: dict[str, float], key: str) -> list[float]:
    vals = None
    for c, f in factors.items():
        if not f:
            continue
        row = (per_case.get(c) or {}).get(key)
        if row is None:
            continue
        vals = [f * x for x in row] if vals is None else [a + f * x for a, x in zip(vals, row)]
    return vals or []


def _r(x: Any, n: int = 3) -> Any:
    return round(x, n) if isinstance(x, float) else x


def _dict_rows(rows: list[dict[str, Any]]) -> Table:
    heads: list[str] = []
    for r in rows:
        for k, v in r.items():
            if k not in heads and not isinstance(v, (dict, list)) or (k not in heads and isinstance(v, list) and all(isinstance(i, str) for i in v)):
                heads.append(k)
    return heads, [[_r("; ".join(r[h]) if isinstance(r.get(h), list) else r.get(h)) for h in heads] for r in rows]


def tables(inp, raw: dict[str, Any], design: dict[str, Any] | None, optimization: dict[str, Any] | None = None) -> dict[str, Table]:
    v = raw.get("viewer") or {}
    combos = _combos(v)
    out: dict[str, Table] = {}
    rows = []
    for name, fac in combos.items():
        for n in v.get("nodes") or []:
            d = _comb(v.get("displacements_mm") or {}, fac, n["id"])
            if d:
                rows.append([name, n["id"], n["x"], n["y"], n["z"], *[_r(x) for x in d]])
    out["joint_displacements"] = (["case/combo", "joint", "x_m", "y_m", "z_m", "Ux_mm", "Uy_mm", "Uz_mm"], rows)
    rows = []
    reac = (raw.get("export") or {}).get("reactions") or v.get("reactions") or {}
    for name, fac in combos.items():
        for nid in sorted({k for c in reac.values() for k in c}):
            r = _comb(reac, fac, nid)
            if r:
                rows.append([name, nid, *[_r(x, 2) for x in r]])
    out["reactions"] = (["case/combo", "joint", "Fx_kN", "Fy_kN", "Fz_kN", "Mx_kNm", "My_kNm", "Mz_kNm"], rows)
    rows = []
    mem = {m["id"]: m for m in v.get("members") or []}
    for name, fac in combos.items():
        for mid, m in mem.items():
            f = _comb(v.get("forces") or {}, fac, mid)
            if f:
                rows.append([name, mid, m["type"], m["storey"], m["i"], m["j"], *[_r(x, 2) for x in f[:4]]])
    out["member_forces"] = (["case/combo", "member", "type", "storey", "i", "j", "N_kN (comp +)", "V_kN", "M_i_kNm", "M_j_kNm"], rows)
    out["storey_drift"] = _dict_rows(raw.get("drift") or [])
    modal = raw.get("modal") or {}
    out["modal"] = _dict_rows(modal.get("modes") or [])
    bs = raw.get("base_shear") or {}
    rows = [[k, _r(val)] for k, val in {**bs, **{f"seismic.{k}": s for k, s in (raw.get("seismic") or {}).items()},
                                       "T_fundamental_s": modal.get("T_fundamental_s"),
                                       **{f"modes_for_90pct.{k}": s for k, s in (modal.get("modes_for_90pct") or {}).items()},
                                       **{f"spectrum.{d}.{k}": s for d, rs in (modal.get("response_spectrum") or {}).items()
                                          for k, s in rs.items() if not isinstance(s, (list, dict))}}.items() if val is not None]
    rows += [[f"W_level_kn.{k}", _r(x)] for k, x in (raw.get("W_level_kn") or {}).items()]
    rows += [[f"F_level_kn.{k}", _r(x)] for k, x in (raw.get("F_level_kn") or {}).items()]
    out["base_shear"] = (["item", "value"], rows)
    d = design or {}
    out["design_beams"] = _dict_rows(d.get("beams") or [])
    out["design_columns"] = _dict_rows(d.get("columns") or [])
    out["design_scwb"] = _dict_rows(d.get("scwb") or [])
    fd = raw.get("foundation_design") or {}
    out["foundation"] = _dict_rows(fd.get("rows") or [])
    out["footings"] = _dict_rows(fd.get("footings") or [])
    if optimization:
        rows = [[stage, *[_r((optimization.get(stage) or {}).get(k)) for k in ("objective", "cost_toman", "weight_kg", "concrete_m3", "rebar_kg", "formwork_m2", "feasible", "max_drift_ratio")]]
                for stage in ("initial", "fsd", "optimal") if optimization.get(stage)]
        h, gr = _dict_rows(optimization.get("groups") or [])
        out["optimization"] = (["stage", "objective", "cost_toman", "weight_kg", "concrete_m3", "rebar_kg", "formwork_m2", "feasible", "max_drift_ratio"], rows)
        out["optimization_groups"] = (h, gr)
    return {k: t for k, t in out.items() if t[1]}


def table_csv(t: Table) -> bytes:
    s = io.StringIO()
    w = csv.writer(s)
    w.writerow(t[0])
    w.writerows(t[1])
    return ("\ufeff" + s.getvalue()).encode("utf-8")


def tables_xlsx(ts: dict[str, Table]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    wb.remove(wb.active)
    for name, (h, rows) in ts.items():
        ws = wb.create_sheet(name[:31])
        ws.append(h)
        for c in ws[1]:
            c.font = Font(bold=True)
        for r in rows:
            ws.append([x if isinstance(x, (int, float, str, bool)) or x is None else str(x) for x in r])
        ws.freeze_panes = "A2"
        for i, col in enumerate(h, 1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = min(40, max(10, len(str(col)) + 2))
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


# ------------------------------------------------------------------ figures
def figure(name: str, inp, raw: dict[str, Any], fmt: str = "png") -> bytes:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    v = raw.get("viewer") or {}
    nodes = {n["id"]: (n["x"], n["y"], n["z"]) for n in v.get("nodes") or []}
    mem = v.get("members") or []
    combos = _combos(v)
    fig = plt.figure(figsize=(8, 6), dpi=130)
    title = FIGURES.get(name, name)
    if name in ("view3d", "deformed") or name.startswith("mode"):
        ax = fig.add_subplot(projection="3d")
        disp: dict[str, list[float]] = {}
        if name == "deformed":
            best, mx = None, -1.0
            for c, fac in (v.get("combos") or combos).items():
                m = max((math.hypot(*_comb(v.get("displacements_mm") or {}, fac, n)[:2]) for n in nodes), default=0)
                if m > mx:
                    best, mx = c, m
            disp = {n: _comb(v.get("displacements_mm") or {}, combos[best], n) for n in nodes} if best else {}
            title += f" — {best}, max {mx:.1f} mm"
        elif name.startswith("mode"):
            shapes = (raw.get("modal") or {}).get("shapes") or []
            k = int(name[4:]) - 1
            if k >= len(shapes):
                plt.close(fig)
                raise KeyError(name)
            sh = shapes[k]
            disp = {n: [x * 1000 for x in xyz] for n, xyz in (sh.get("disp") or {}).items()}
            title += f" — T = {sh.get('T_s')} s"
        span = max((max(p) for p in nodes.values()), default=1) or 1
        peak = max((abs(x) for d in disp.values() for x in d[:3]), default=0)
        sc = (0.08 * span * 1000 / peak) if peak else 0
        for m in mem:
            a, b = nodes[m["i"]], nodes[m["j"]]
            ax.plot(*zip(a, b), color="#9aa" if disp else ("#246" if m["type"] == "column" else "#c62"), lw=0.8 if disp else 1.4)
            if disp:
                da, db = disp.get(m["i"], [0, 0, 0]), disp.get(m["j"], [0, 0, 0])
                ax.plot(*zip([p + sc * q / 1000 for p, q in zip(a, da)], [p + sc * q / 1000 for p, q in zip(b, db)]), color="#d22", lw=1.4)
        for s in v.get("supports") or []:
            ax.scatter(*nodes[s], marker="^", color="k", s=18)
        ax.set_xlabel("X (m)"); ax.set_ylabel("Y (m)"); ax.set_zlabel("Z (m)")
        try:
            ax.set_box_aspect([max(1e-3, max(p[i] for p in nodes.values())) for i in range(3)])
        except Exception:
            pass
    elif name in ("moment", "shear", "axial"):
        ax = fig.add_subplot()
        idx = {"axial": 0, "shear": 1, "moment": 2}[name]
        c = next((k for k in combos if "+" in k and "E" in k), None) or next((k for k in combos if "+" in k), None) or next(iter(combos), None)
        if "1.2D+1.6L" in combos and name != "moment":
            c = "1.2D+1.6L"
        y0 = min((p[1] for p in nodes.values()), default=0)
        sel = [m for m in mem if nodes[m["i"]][1] == y0 and nodes[m["j"]][1] == y0]
        vals = {m["id"]: _comb(v.get("forces") or {}, combos[c], m["id"]) for m in sel} if c else {}
        peak = max((abs(x) for f in vals.values() for x in (f[0:1] if idx == 0 else f[1:4] if idx else [])), default=0)
        peak = max(peak, max((abs(f[2]) for f in vals.values() if f), default=0), 1e-9)
        h = max((p[2] for p in nodes.values()), default=3)
        sc = 0.15 * h / max(peak, 1e-9)
        for m in sel:
            a, b = nodes[m["i"]], nodes[m["j"]]
            ax.plot([a[0], b[0]], [a[2], b[2]], color="#333", lw=1.2)
            f = vals.get(m["id"]) or [0, 0, 0, 0, 0]
            L = math.dist(a, b) or 1
            ux, uz = (b[0] - a[0]) / L, (b[2] - a[2]) / L
            nx_, nz_ = -uz, ux
            pts = []
            for t in [i / 20 for i in range(21)]:
                x = t * L
                if idx == 2:
                    val = f[2] + (f[3] - f[2]) * t + (f[4] if len(f) > 4 else 0) * (x * x - x * L) / 2
                elif idx == 1:
                    val = f[1] - (f[4] if len(f) > 4 else 0) * x
                else:
                    val = f[0]
                pts.append((a[0] + ux * x + nx_ * val * sc, a[2] + uz * x + nz_ * val * sc))
            ax.fill(*zip((a[0], a[2]), *pts, (b[0], b[2])), color="#e55" if idx == 2 else "#58c", alpha=0.35, lw=0.6)
        ax.set_aspect("equal")
        ax.set_xlabel("X (m)"); ax.set_ylabel("Z (m)")
        title += f" — {c}, peak {peak:.1f}"
    elif name == "drift":
        ax = fig.add_subplot()
        dr = raw.get("drift") or []
        for d_ in sorted({r["direction"] for r in dr}):
            rr = sorted((r for r in dr if r["direction"] == d_), key=lambda r: r["storey"])
            ax.plot([r["ratio_amplified"] * 100 for r in rr], [r["storey"] for r in rr], marker="o", label=f"{d_} (amplified)")
        lim = (raw.get("seismic") or {}).get("drift_limit")
        if lim:
            ax.axvline(lim * 100, color="r", ls="--", label=f"limit {lim * 100:.1f}%")
        ax.set_xlabel("drift %"); ax.set_ylabel("storey")
        if dr:
            ax.legend()
        else:
            ax.text(0.5, 0.5, "No seismic drift (gravity-only run)", ha="center", transform=ax.transAxes)
    else:
        plt.close(fig)
        raise KeyError(name)
    fig.suptitle(title, fontsize=10)
    b = io.BytesIO()
    fig.savefig(b, format="svg" if fmt == "svg" else "png", bbox_inches="tight")
    plt.close(fig)
    return b.getvalue()


def figure_names(raw: dict[str, Any]) -> list[str]:
    n = len((raw.get("modal") or {}).get("shapes") or [])
    return [k for k in FIGURES if not k.startswith("mode") or int(k[4:]) <= n]


# ------------------------------------------------------------------ single item + zip
def item(kind: str, name: str, fmt: str, inputs: dict[str, Any], optimization: dict[str, Any] | None = None) -> tuple[str, bytes, str]:
    """Return (filename, bytes, mime)."""
    from app.application import csi_text_export as cte
    inp, raw, design = run(inputs)
    if kind == "table":
        ts = tables(inp, raw, design, optimization)
        if name == "all":
            return "frame-results.xlsx", tables_xlsx(ts), XLSX
        if name not in ts:
            raise KeyError(name)
        if fmt == "csv":
            return f"{name}.csv", table_csv(ts[name]), "text/csv"
        return f"{name}.xlsx", tables_xlsx({name: ts[name]}), XLSX
    if kind == "figure":
        f = "svg" if fmt == "svg" else "png"
        return f"{name}.{f}", figure(name, inp, raw, f), "image/svg+xml" if f == "svg" else "image/png"
    if kind in ("model", "drawing"):
        if name == "structural_set":
            from app.application.autocad import structural_set as ss
            sheets, _ = ss.build_structural_set(inp, raw, design, None)
            return "structural-set.pdf", ss.render_pdf(sheets), "application/pdf"
        if name not in cte.FORMATS:
            raise KeyError(name)
        meta = cte.FORMATS[name]
        if fmt == "pdf" and name.startswith("dxf"):
            import ezdxf
            from app.application.autocad import structural_set as ss
            doc = ezdxf.read(io.StringIO(cte.build_export(name, inp, raw, design)))
            return meta["filename"].replace(".dxf", ".pdf"), dxf_pdf(doc), "application/pdf"
        return meta["filename"], cte.build_export(name, inp, raw, design).encode("utf-8"), meta["mime"]
    if kind == "report":
        if name == "report_json":
            return "results.json", json.dumps({"inputs": inputs, "raw": {k: v for k, v in raw.items() if k != "viewer"}, "design": design},
                                              default=str, ensure_ascii=False, indent=1).encode("utf-8"), "application/json"
        if name == "report_pdf":
            from app.application.report_pdf import markdown_to_pdf
            return "report.pdf", markdown_to_pdf(report_md(inputs, optimization), rtl=str(inputs.get("lang") or "") == "fa"), "application/pdf"
        return "report.md", report_md(inputs, optimization).encode("utf-8"), "text/markdown"
    raise KeyError(kind)


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def report_md(inputs: dict[str, Any], optimization: dict[str, Any] | None = None) -> str:
    from app.application.frame3d_chat_analysis import build_frame3d_payload, frame3d_markdown
    md = frame3d_markdown(build_frame3d_payload("", manual_inputs={"design_code": "MABHAS9", "foundation": True, **inputs}))
    if optimization:
        from app.application.frame_optimizer import optimization_markdown
        md += "\n\n" + optimization_markdown(optimization, str(inputs.get("lang") or "en"))
    return md


def build_zip(inputs: dict[str, Any], optimization: dict[str, Any] | None = None, *, with_set: bool = True,
              on_file: Callable[[str, bytes], None] | None = None) -> tuple[bytes, list[str]]:
    from app.application import csi_text_export as cte
    inp, raw, design = run(inputs)
    buf = io.BytesIO()
    names: list[str] = []
    errors: list[str] = []
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        def put(path: str, data: bytes) -> None:
            z.writestr(path, data)
            names.append(path)
        ts = tables(inp, raw, design, optimization)
        put("tables/frame-results.xlsx", tables_xlsx(ts))
        for k, t in ts.items():
            put(f"tables/csv/{k}.csv", table_csv(t))
        for f in figure_names(raw):
            try:
                put(f"figures/{f}.png", figure(f, inp, raw, "png"))
            except Exception as exc:  # noqa: BLE001 — one bad figure must not kill the zip
                errors.append(f"figure {f}: {exc}")
        for f in ("e2k", "f2k", "s2k"):
            try:
                put(f"models/{cte.FORMATS[f]['filename']}", cte.build_export(f, inp, raw, design).encode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{f}: {exc}")
        for f in ("dxf_plans", "dxf_3d", "dxf_rebar", "dxf_foundation"):
            try:
                txt = cte.build_export(f, inp, raw, design)
                put(f"drawings/{cte.FORMATS[f]['filename']}", txt.encode("utf-8"))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{f}: {exc}")
                continue
            try:
                import ezdxf
                put(f"drawings/pdf/{cte.FORMATS[f]['filename'].rsplit('.', 1)[0]}.pdf", dxf_pdf(ezdxf.read(io.StringIO(txt))))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{f} pdf: {exc}")
        if with_set and design:
            try:
                from app.application.autocad import structural_set as ss
                sheets, _ = ss.build_structural_set(inp, raw, design, None)
                for sh in sheets:
                    put(f"drawings/structural-set/{sh.sheet_no}.dxf", sh.dxf_text().encode("utf-8"))
                put("drawings/structural-set/structural-set.pdf", ss.render_pdf(sheets))
            except Exception as exc:  # noqa: BLE001
                errors.append(f"structural set: {exc}")
        try:
            put("report/report.md", report_md(inputs, optimization).encode("utf-8"))
            from app.application.report_pdf import markdown_to_pdf
            put("report/report.pdf", markdown_to_pdf(report_md(inputs, optimization), rtl=str(inputs.get("lang") or "") == "fa"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"report: {exc}")
        put("inputs.json", json.dumps(inputs, ensure_ascii=False, indent=1, default=str).encode("utf-8"))
        if errors:
            put("ERRORS.txt", "\n".join(errors).encode("utf-8"))
    data = buf.getvalue()
    if on_file:
        on_file("frame-results.xlsx", tables_xlsx(ts))
        on_file("frame-results.zip", data)
    return data, names


def dxf_pdf(doc) -> bytes:
    """PDF of a DXF: its paper layouts (one page each) or, if it has none, the model space fitted to A3."""
    import pymupdf
    from ezdxf.addons.drawing import Frontend, RenderContext, layout as dlayout
    from ezdxf.addons.drawing import pymupdf as pmb
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration

    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK, min_lineweight=0.12)
    out = pymupdf.open()
    lays = [l for l in doc.layouts if l.name.lower() != "model" and len(l)] or [doc.modelspace()]
    for lay in lays:
        be = pmb.PyMuPdfBackend()
        Frontend(RenderContext(doc), be, config=cfg).draw_layout(lay, finalize=True)
        if lay.name.lower() == "model":
            page = dlayout.Page(420, 297, dlayout.Units.mm, margins=dlayout.Margins.all(10))
            data = be.get_pdf_bytes(page, settings=dlayout.Settings(fit_page=True))
        else:
            data = be.get_pdf_bytes(dlayout.Page(lay.dxf.paper_width or 420, lay.dxf.paper_height or 297, dlayout.Units.mm))
        out.insert_pdf(pymupdf.open("pdf", data))
    return out.tobytes(deflate=True)
