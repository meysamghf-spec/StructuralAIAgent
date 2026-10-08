"""AutoCAD 2027 integration adapter boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from uuid import UUID

from app.domain.models.integration import (
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationResult,
    IntegrationSoftware,
    SoftwareCapabilityReport,
)
from app.infrastructure.integrations.autocad_detection import detect_autocad_capability
from app.infrastructure.integrations.autocad_drawing import validate_sheet_plan


class AutocadAdapter:
    def __init__(
        self,
        com_factory: Callable[[], Any] | None = None,
        capability_override: SoftwareCapabilityReport | None = None,
    ) -> None:
        self._com_factory = com_factory
        self._capability_override = capability_override
    @property
    def software_name(self) -> str:
        return IntegrationSoftware.AUTOCAD.value

    @property
    def software_version(self) -> str:
        return "2027"

    def detect_capability(self) -> SoftwareCapabilityReport:
        if self._capability_override is not None:
            return self._capability_override
        return detect_autocad_capability()

    def get_status(self) -> IntegrationResult:
        capability = self.detect_capability()
        status = IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE
        if capability.availability.value == "AVAILABLE":
            status = IntegrationOperationStatus.SUCCESS
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.STATUS,
            status=status,
            message=capability.message,
            metadata={
                "availability": capability.availability.value,
                "detected_version": capability.detected_version,
                "install_path": capability.install_path,
                "adapter": "autocad",
                "version": self.software_version,
            },
        )

    def generate_drawing(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult:
        capability = self.detect_capability()
        plan = parameters.get("sheet_plan") if isinstance(parameters.get("sheet_plan"), dict) else None
        plan_summary = _plan_summary(plan)
        if capability.availability.value != "AVAILABLE":
            result = self._requires_local(IntegrationOperation.GENERATE_DRAWING, project_id, capability.message)
            result.metadata.update(plan_summary)
            result.metadata["construction_ready"] = False
            result.metadata["drawing_executed"] = False
            return result
        valid, reason = validate_sheet_plan(plan)
        if not valid or plan is None:
            return IntegrationResult(
                software=IntegrationSoftware.AUTOCAD,
                operation=IntegrationOperation.GENERATE_DRAWING,
                status=IntegrationOperationStatus.FAILED,
                message=reason,
                metadata={
                    "project_id": str(project_id),
                    "failure_class": "EMPTY_DRAWING",
                    "drawing_executed": False,
                    "construction_ready": False,
                    **plan_summary,
                },
            )
        output_dir = Path(str(parameters.get("output_dir") or "")).expanduser()
        if not parameters.get("output_dir"):
            return IntegrationResult(
                software=IntegrationSoftware.AUTOCAD,
                operation=IntegrationOperation.GENERATE_DRAWING,
                status=IntegrationOperationStatus.FAILED,
                message="AutoCAD generation requires an output directory. No DWG was saved.",
                metadata={
                    "project_id": str(project_id),
                    "failure_class": "EMPTY_DRAWING",
                    "drawing_executed": False,
                    "construction_ready": False,
                },
            )
        try:
            return self._draw_with_autocad(project_id, plan, output_dir, capability)
        except Exception as exc:  # noqa: BLE001
            failure_class = "LICENSING_FAILURE" if "license" in str(exc).lower() else "MODEL_BUILD_FAILURE"
            return IntegrationResult(
                software=IntegrationSoftware.AUTOCAD,
                operation=IntegrationOperation.GENERATE_DRAWING,
                status=IntegrationOperationStatus.FAILED,
                message=f"AutoCAD drawing generation failed: {exc}",
                metadata={
                    "project_id": str(project_id),
                    "failure_class": failure_class,
                    "drawing_executed": False,
                    "construction_ready": False,
                    **plan_summary,
                },
            )

    def export_dxf(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.EXPORT_DXF,
            status=IntegrationOperationStatus.NOT_IMPLEMENTED,
            message="Use platform DXF generation; AutoCAD is not required for DXF export.",
            metadata={"project_id": str(project_id), "destination_path": destination_path},
        )

    def export_dwg(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        capability = self.detect_capability()
        if capability.availability.value != "AVAILABLE":
            return self._requires_local(IntegrationOperation.EXPORT_DWG, project_id, capability.message)
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.EXPORT_DWG,
            status=IntegrationOperationStatus.FAILED,
            message=(
                "An empty AutoCAD document is not a drawing. "
                "Use generate_drawing with a PEM sheet plan that contains geometry."
            ),
            metadata={
                "project_id": str(project_id),
                "destination_path": destination_path,
                "failure_class": "EMPTY_DRAWING",
                "drawing_executed": False,
                "install_path": capability.install_path,
            },
        )

    def _draw_with_autocad(
        self,
        project_id: UUID,
        plan: dict[str, Any],
        output_dir: Path,
        capability: SoftwareCapabilityReport,
    ) -> IntegrationResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        app = self._com_factory() if self._com_factory is not None else _dispatch_autocad()
        document = app.Documents.Add()
        model_space = document.ModelSpace
        created = 0
        errors: list[str] = []
        for command in plan["commands"]:
            try:
                _draw_command(model_space, command)
                created += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{command.get('sheet')} {command.get('kind')}: {exc}")
        geometry_commands = [
            item for item in plan["commands"] if item.get("kind") in {"LINE", "POLYLINE", "CIRCLE"} and item.get("points")
        ]
        dwg_path = output_dir / f"{project_id}.dwg"
        pdf_path = output_dir / f"{project_id}.pdf"
        if errors or created < len(geometry_commands) or created == 0:
            _close_quietly(document)
            return IntegrationResult(
                software=IntegrationSoftware.AUTOCAD,
                operation=IntegrationOperation.GENERATE_DRAWING,
                status=IntegrationOperationStatus.FAILED,
                message="AutoCAD did not create every requested entity. No success is recorded.",
                metadata={
                    "project_id": str(project_id),
                    "failure_class": "EMPTY_DRAWING" if created == 0 else "MODEL_BUILD_FAILURE",
                    "entities_created": created,
                    "errors": errors,
                    "drawing_executed": False,
                    "construction_ready": False,
                    **_plan_summary(plan),
                },
            )
        document.SaveAs(str(dwg_path))
        if not dwg_path.is_file() or dwg_path.stat().st_size <= 0:
            _close_quietly(document)
            return IntegrationResult(
                software=IntegrationSoftware.AUTOCAD,
                operation=IntegrationOperation.GENERATE_DRAWING,
                status=IntegrationOperationStatus.FAILED,
                message="AutoCAD SaveAs did not produce a non-empty DWG.",
                metadata={
                    "project_id": str(project_id),
                    "failure_class": "EMPTY_DRAWING",
                    "drawing_executed": False,
                    "construction_ready": False,
                },
            )
        pdf_status, pdf_error = _export_pdf(document, pdf_path)
        _close_quietly(document)
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.GENERATE_DRAWING,
            status=IntegrationOperationStatus.SUCCESS,
            message="AutoCAD wrote a DWG from the PEM sheet plan. This is not a construction issue.",
            metadata={
                "project_id": str(project_id),
                "dwg_path": str(dwg_path),
                "dwg_bytes": dwg_path.stat().st_size,
                "entities_created": created,
                "pdf_status": pdf_status,
                "pdf_path": str(pdf_path) if pdf_status == "EXPORTED" else None,
                "pdf_error": pdf_error,
                "drawing_executed": True,
                "construction_ready": False,
                "detected_version": capability.detected_version,
                "failure_class": None,
                **_plan_summary(plan),
            },
        )

    def supports_operation(self, operation: IntegrationOperation) -> bool:
        return operation in {
            IntegrationOperation.GENERATE_DRAWING,
            IntegrationOperation.EXPORT_DXF,
            IntegrationOperation.EXPORT_DWG,
            IntegrationOperation.STATUS,
        }

    def _requires_local(
        self,
        operation: IntegrationOperation,
        project_id: UUID,
        message: str,
    ) -> IntegrationResult:
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=operation,
            status=IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
            message=message,
            metadata={"project_id": str(project_id), "failure_class": "APPLICATION_UNAVAILABLE", "drawing_executed": False},
        )


def _plan_summary(plan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {"geometry_count": 0, "missing_construction_details": []}
    return {
        "geometry_count": plan.get("geometry_count") or 0,
        "annotation_count": plan.get("annotation_count") or 0,
        "sheets": plan.get("sheets") or [],
        "missing_construction_details": plan.get("missing_construction_details") or [],
        "source_snapshot_id": plan.get("source_snapshot_id"),
        "pem_version": plan.get("pem_version"),
        "units": plan.get("units"),
    }


def _dispatch_autocad() -> Any:
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("AutoCAD COM automation requires pywin32 on this computer.") from exc
    return win32com.client.Dispatch("AutoCAD.Application")


def _com_point(values: list[float]) -> Any:
    numbers = [float(value) for value in values]
    try:
        import pythoncom  # type: ignore[import-untyped]
        from win32com.client import VARIANT  # type: ignore[import-untyped]

        return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, numbers)
    except ImportError:
        return numbers


def _draw_command(model_space: Any, command: dict[str, Any]) -> None:
    kind = command.get("kind")
    points = command.get("points") or []
    if kind == "LINE":
        if len(points) < 2:
            raise RuntimeError("LINE needs two points")
        model_space.AddLine(_com_point(points[0]), _com_point(points[1]))
        return
    if kind == "POLYLINE":
        if len(points) < 2:
            raise RuntimeError("POLYLINE needs at least two points")
        flat: list[float] = []
        for point in points:
            flat.extend([float(point[0]), float(point[1])])
        polyline = model_space.AddLightWeightPolyline(_com_point(flat))
        if command.get("closed") and hasattr(polyline, "Closed"):
            polyline.Closed = True
        return
    if kind == "CIRCLE":
        if not points or command.get("radius_mm") in (None, 0):
            raise RuntimeError("CIRCLE needs a center and radius")
        model_space.AddCircle(_com_point(points[0]), float(command["radius_mm"]))
        return
    if kind == "TEXT":
        if not points or not command.get("text"):
            raise RuntimeError("TEXT needs an insertion point and text")
        model_space.AddText(str(command["text"]), _com_point(points[0]), float(command.get("text_height_mm") or 250.0))
        return
    raise RuntimeError(f"Drawing entity kind '{kind}' is not supported")


def _export_pdf(document: Any, pdf_path: Path) -> tuple[str, str | None]:
    plot = getattr(document, "Plot", None)
    plot_to_file = getattr(plot, "PlotToFile", None)
    if not callable(plot_to_file):
        return "NOT_SUPPORTED", "This AutoCAD document has no Plot.PlotToFile method."
    try:
        plot_to_file(str(pdf_path))
    except Exception as exc:  # noqa: BLE001
        return "FAILED", str(exc)
    if pdf_path.is_file() and pdf_path.stat().st_size > 0:
        return "EXPORTED", None
    return "FAILED", "PlotToFile did not produce a non-empty PDF."


def _close_quietly(document: Any) -> None:
    close = getattr(document, "Close", None)
    if callable(close):
        try:
            close(False)
        except Exception:
            return
