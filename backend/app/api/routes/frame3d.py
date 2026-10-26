"""3D frame text exports (ETABS .e2k, SAFE .f2k, SAP2000 .s2k, DXF) — /api/v1/frame3d."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.api.deps import get_current_account
from app.application.billing import service as billing
from app.application import csi_text_export as cte
from app.application.analysis.frame3d_solver import SpaceFrameSolverError
from app.application.frame3d_chat_analysis import build_frame3d_payload, run_frame3d_for_export
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/frame3d", tags=["frame3d"])


class Frame3dExportRequest(BaseModel):
    format: str = Field(description="e2k | f2k | s2k | dxf_plans | dxf_3d | dxf_rebar | dxf_foundation")
    inputs: dict[str, Any] = Field(description="`inputs` of a frame3d_analysis result (plus optional `parsed_from_request`)")


@router.post("/export")
def export_frame3d(
    body: Frame3dExportRequest,
    acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> Response:
    meta = cte.FORMATS.get(body.format)
    if meta is None:
        raise HTTPException(status_code=422, detail=f"Unknown format {body.format!r}; use one of {sorted(cte.FORMATS)}")
    billing.require_feature(getattr(acc, "account_id", None), "exports", "dxf" if body.format.startswith("dxf") else body.format)
    if body.format == "dxf_rebar":
        billing.require_feature(getattr(acc, "account_id", None), "design_sheets", "rebar_sheets")
    billing.check_frame_size(getattr(acc, "account_id", None), body.inputs)
    try:
        inputs = body.inputs
        if body.format in ("dxf_rebar", "dxf_foundation"):
            inputs = {**inputs, "design_code": "MABHAS9", **({"foundation": True} if body.format == "dxf_foundation" else {})}
        inp, raw, design = run_frame3d_for_export(inputs)
        content = cte.build_export(body.format, inp, raw, design)
    except (TypeError, ValueError, SpaceFrameSolverError) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot export this model: {exc}") from exc
    return Response(
        content=content.encode("utf-8"),
        media_type=meta["mime"],
        headers={"Content-Disposition": f'attachment; filename="{meta["filename"]}"'},
    )


class Frame3dRunRequest(BaseModel):
    inputs: dict[str, Any] = Field(description="Frame3dInputs fields from the manual Model page (storeys, bays_x, bay_x_m, ...)")
    assume_defaults: bool = Field(default=False, description="fill missing storeys/bays/spans with the documented defaults and report them in assumed_defaults")


@router.post("/run")
def run_frame3d_manual(
    body: Frame3dRunRequest,
    acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> dict[str, Any]:
    """Run the in-house 3D frame solver (+ 2800, Mabhas 9 design, footings) on manual-form inputs; same payload as chat."""
    billing.check_frame_size(getattr(acc, "account_id", None), body.inputs)
    billing.consume(getattr(acc, "account_id", None), "analyses_per_month")
    inputs = dict(body.inputs)
    assumed: list[str] = []
    if body.assume_defaults:
        from app.application import frame3d_followup as fu

        for k, v in fu.DEFAULTS.items():
            if inputs.get(k) in (None, "", 0):
                inputs[k] = v
                assumed.append(k)
    try:
        payload = build_frame3d_payload("", manual_inputs=inputs)
        if assumed and isinstance(payload, dict):
            payload["assumed_defaults"] = assumed
    except (TypeError, ValueError, SpaceFrameSolverError) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot analyse this model: {exc}") from exc
    return {"frame3d_analysis": payload}


class Frame3dOptimizeRequest(BaseModel):
    inputs: dict[str, Any] = Field(description="Frame3dInputs fields (storeys, bays_x, bays_y, bay_x_m, ...)")
    options: dict[str, Any] = Field(default_factory=dict, description="objective cost|weight, prices{concrete_m3,rebar_kg,formwork_m2}, seed, time_budget_s, max_evaluations, group_storeys")
    assume_defaults: bool = Field(default=False, description="fill missing storeys/bays/spans with the documented defaults and report them")


@router.post("/optimize")
def optimize_frame3d(
    body: Frame3dOptimizeRequest,
    acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> dict[str, Any]:
    """FSD analysis-design-reanalysis loop + discrete GA on the 3D frame (Mabhas 9 + 2800 drift + deflection)."""
    from app.application import frame3d_chat_analysis as f3
    from app.application import frame_optimizer as fopt

    billing.require_feature(getattr(acc, "account_id", None), "optimization")
    billing.check_frame_size(getattr(acc, "account_id", None), body.inputs)
    billing.consume(getattr(acc, "account_id", None), "analyses_per_month")

    try:
        data = {"seismic_code": "IRAN_2800", **body.inputs}
        inp = f3.inputs_from_dict(data)
        missing = f3.missing_inputs(inp)
        assumed: list[str] = []
        if missing and body.assume_defaults:
            from app.application import frame3d_followup as fu

            assumed = fu.apply_defaults(inp)
            missing = f3.missing_inputs(inp)
        if missing:
            raise ValueError("missing " + ", ".join(missing) + " (send assume_defaults=true to use typical defaults)")
        if inp.storeys > f3.MAX_STOREYS or max(inp.bays_x, inp.bays_y) > f3.MAX_BAYS or min(inp.storeys, inp.bays_x, inp.bays_y) < 1:
            raise ValueError(f"supports 1-{f3.MAX_STOREYS} storeys and 1-{f3.MAX_BAYS} bays per direction")
        opts = {**body.options}
        opts["time_budget_s"] = min(float(opts.get("time_budget_s", 45)), 90.0)
        opts["max_evaluations"] = min(int(opts.get("max_evaluations", 300)), 600)
        res = fopt.optimize_frame(inp, opts)
    except (TypeError, ValueError, SpaceFrameSolverError) as exc:
        raise HTTPException(status_code=422, detail=f"Cannot optimize this model: {exc}") from exc
    if assumed:
        res["assumed_defaults"] = assumed
        res["inputs_used"] = {k: getattr(inp, k) for k in assumed if hasattr(inp, k)}
    res["report_markdown"] = fopt.optimization_markdown(res, str(body.inputs.get("lang") or "en"))
    return {"frame_optimization": res}


# ---------------------------------------------------------------- downloads (tables / figures / drawings / models / ZIP)
from uuid import UUID as _UUID  # noqa: E402

from app.api.deps import get_conversation_service, get_file_ingestion_service, get_project_access_service  # noqa: E402


class Frame3dDownloadRequest(BaseModel):
    kind: str = Field(description="table | figure | model | drawing | report")
    name: str = Field(description="item key from GET /frame3d/downloads/catalog (table 'all' = every table in one .xlsx)")
    format: str = Field(default="", description="xlsx|csv (tables), png|svg (figures), dxf|pdf (drawings)")
    inputs: dict[str, Any] | None = None
    project_id: str | None = None
    optimization: dict[str, Any] | None = None
    save_to_files: bool = False


class Frame3dPackageRequest(BaseModel):
    inputs: dict[str, Any] | None = None
    project_id: str | None = None
    optimization: dict[str, Any] | None = None
    save_to_files: bool = True


def _resolve(body, acc, conv, access):
    if body.project_id:
        try:
            access.require_project(_UUID(body.project_id), acc)
        except ValueError as exc:
            raise HTTPException(422, "invalid project_id") from exc
    inputs = body.inputs
    if not inputs and body.project_id:
        from app.api.routes.autocad import latest_frame_inputs
        inputs = latest_frame_inputs(conv, acc, body.project_id)
    if not inputs:
        raise HTTPException(409, "No 3D frame analysis yet — run one in chat or on the Model page first.")
    billing.check_frame_size(getattr(acc, "account_id", None), inputs)
    return inputs


def _saver(files, project_id, acc):
    def save(name: str, data: bytes, ctype: str = "application/octet-stream") -> str:
        try:
            return str(files.ingest_upload(_UUID(project_id), filename=name, content=data, content_type=ctype,
                                           created_by=acc.account_id).id)
        except Exception:  # noqa: BLE001 — saving to Files is best effort; the download itself still succeeds
            return ""
    return save


@router.get("/downloads/catalog")
def downloads_catalog(acc: Annotated[AuthenticatedAccount, Depends(get_current_account)]) -> dict[str, Any]:
    from app.application import results_package as rp
    return rp.catalog()


@router.post("/download")
def download_item(body: Frame3dDownloadRequest, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                  conv=Depends(get_conversation_service), files=Depends(get_file_ingestion_service),
                  access=Depends(get_project_access_service)) -> Response:
    from app.application import results_package as rp
    inputs = _resolve(body, acc, conv, access)
    if body.kind in ("model", "drawing"):
        billing.require_feature(getattr(acc, "account_id", None), "exports", "dxf" if body.name.startswith(("dxf", "structural")) else body.name)
    try:
        name, data, mime = rp.item(body.kind, body.name, body.format, inputs, body.optimization)
    except KeyError as exc:
        raise HTTPException(404, f"unknown or empty item {body.kind}/{body.name}") from exc
    except (TypeError, ValueError, SpaceFrameSolverError) as exc:
        raise HTTPException(422, f"Cannot build this download: {exc}") from exc
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    if body.save_to_files and body.project_id:
        headers["X-File-Id"] = _saver(files, body.project_id, acc)(name, data, mime)
    return Response(content=data, media_type=mime, headers=headers)


@router.post("/package")
def download_package(body: Frame3dPackageRequest, acc: Annotated[AuthenticatedAccount, Depends(get_current_account)],
                     conv=Depends(get_conversation_service), files=Depends(get_file_ingestion_service),
                     access=Depends(get_project_access_service)) -> Response:
    """Everything for one run as a ZIP: tables (xlsx + csv), figures (png), model exports, drawings (dxf + set pdf), report."""
    from app.application import results_package as rp
    inputs = _resolve(body, acc, conv, access)
    billing.require_feature(getattr(acc, "account_id", None), "exports", "dxf")
    saved: list[str] = []
    on_file = None
    if body.save_to_files and body.project_id:
        save = _saver(files, body.project_id, acc)
        on_file = lambda n, d: saved.append(save(n, d, rp.XLSX if n.endswith(".xlsx") else "application/zip"))  # noqa: E731
    try:
        data, names = rp.build_zip(inputs, body.optimization, on_file=on_file)
    except (TypeError, ValueError, SpaceFrameSolverError) as exc:
        raise HTTPException(422, f"Cannot build the package: {exc}") from exc
    return Response(content=data, media_type="application/zip",
                    headers={"Content-Disposition": 'attachment; filename="frame-results.zip"',
                             "X-Files": str(len(names)), "X-File-Ids": ",".join(x for x in saved if x),
                             "Access-Control-Expose-Headers": "X-Files, X-File-Ids, X-File-Id"})
