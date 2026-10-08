"""CSI structural software adapter base — detection, connection, and vendor isolation."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from uuid import UUID, uuid4

from app.application.external_model_conversion import (
    build_external_model_export,
    parse_external_analysis_results,
    validate_external_model_export,
    validate_imported_results,
)
from app.domain.models.integration import (
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationResult,
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)
from app.domain.models.pem import ProjectEngineeringModel
from app.application.csi_result_normalization import normalize_csi_raw_results
from app.domain.models.csi_extraction import CsiExtractionStatus
from app.infrastructure.integrations.csi_detection import CSI_PROFILES, CsiSoftwareProfile, detect_software_capability
from app.infrastructure.integrations.csi_pem_builder import (
    CSI_UNIT_SYSTEM_KN_M_C,
    build_vendor_model_from_export,
)
from app.infrastructure.integrations.safe_foundation_builder import build_safe_foundation_model
from app.infrastructure.integrations.csi_result_extractor import extract_csi_results


def classify_vendor_failure(exc: Exception, *, default_class: str) -> tuple[IntegrationOperationStatus, str]:
    """Separate a license rejection from a model, analysis, or extraction failure."""
    text = str(exc).lower()
    if any(token in text for token in ("license", "licence", "not authorized", "no authorization")):
        return IntegrationOperationStatus.NOT_ACCESSIBLE, "LICENSING_FAILURE"
    return IntegrationOperationStatus.FAILED, default_class


def _failure_class_for_availability(status: IntegrationOperationStatus, message: str) -> str:
    if status == IntegrationOperationStatus.NOT_ACCESSIBLE and any(
        token in message.lower() for token in ("license", "licence", "not authorized")
    ):
        return "LICENSING_FAILURE"
    return "APPLICATION_UNAVAILABLE"


def _map_availability_to_status(
    availability: SoftwareAvailabilityStatus,
) -> IntegrationOperationStatus:
    mapping = {
        SoftwareAvailabilityStatus.AVAILABLE: IntegrationOperationStatus.SUCCESS,
        SoftwareAvailabilityStatus.NOT_INSTALLED: IntegrationOperationStatus.NOT_INSTALLED,
        SoftwareAvailabilityStatus.VERSION_MISMATCH: IntegrationOperationStatus.VERSION_MISMATCH,
        SoftwareAvailabilityStatus.NOT_ACCESSIBLE: IntegrationOperationStatus.NOT_ACCESSIBLE,
        SoftwareAvailabilityStatus.REQUIRES_LOCAL_SOFTWARE: IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
    }
    return mapping.get(availability, IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE)


class CsiStructuralAdapter:
    def __init__(
        self,
        profile: CsiSoftwareProfile,
        *,
        com_probe: Callable[[str], bool] | None = None,
        capability_override: SoftwareCapabilityReport | None = None,
    ) -> None:
        self._profile = profile
        self._com_probe = com_probe
        self._capability_override = capability_override
        self._helper: Any | None = None
        self._connected = False

    @property
    def software_name(self) -> str:
        return self._profile.software.value

    @property
    def software_version(self) -> str:
        return self._profile.expected_version

    def detect_capability(self) -> SoftwareCapabilityReport:
        if self._capability_override is not None:
            return self._capability_override
        return detect_software_capability(self._profile, com_probe=self._com_probe)

    def get_status(self) -> IntegrationResult:
        report = self.detect_capability()
        status = _map_availability_to_status(report.availability)
        if report.availability == SoftwareAvailabilityStatus.AVAILABLE:
            operation_status = IntegrationOperationStatus.SUCCESS
        elif report.availability == SoftwareAvailabilityStatus.NOT_INSTALLED:
            operation_status = IntegrationOperationStatus.NOT_INSTALLED
        elif report.availability == SoftwareAvailabilityStatus.VERSION_MISMATCH:
            operation_status = IntegrationOperationStatus.VERSION_MISMATCH
        elif report.availability == SoftwareAvailabilityStatus.NOT_ACCESSIBLE:
            operation_status = IntegrationOperationStatus.NOT_ACCESSIBLE
        else:
            operation_status = IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE

        return IntegrationResult(
            software=self._profile.software,
            operation=IntegrationOperation.STATUS,
            status=operation_status,
            message=report.message,
            metadata={
                "availability": report.availability.value,
                "expected_version": report.expected_version,
                "detected_version": report.detected_version,
                "install_path": report.install_path,
                **report.metadata,
            },
        )

    def connect(self, project_id: UUID) -> IntegrationResult:
        report = self.detect_capability()
        if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
            return self._unavailable(
                IntegrationOperation.CONNECT,
                project_id,
                report=report,
            )

        try:
            self._helper = self._start_application()
            self._connected = self._helper is not None
        except Exception as exc:  # noqa: BLE001
            status, failure_class = classify_vendor_failure(exc, default_class="APPLICATION_UNAVAILABLE")
            if failure_class == "APPLICATION_UNAVAILABLE":
                status = IntegrationOperationStatus.NOT_ACCESSIBLE
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.CONNECT,
                status=status,
                message=(
                    f"{self._profile.software.value} could not be connected. "
                    f"Check that the application is installed, licensed, and accessible."
                ),
                metadata={
                    "project_id": str(project_id),
                    "error": str(exc),
                    "failure_class": failure_class,
                    "analysis_executed": False,
                },
            )

        if not self._connected:
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.CONNECT,
                status=IntegrationOperationStatus.NOT_ACCESSIBLE,
                message=f"{self._profile.software.value} connection failed without vendor details.",
                metadata={"project_id": str(project_id)},
            )

        return IntegrationResult(
            software=self._profile.software,
            operation=IntegrationOperation.CONNECT,
            status=IntegrationOperationStatus.SUCCESS,
            message=f"Connected to {self._profile.software.value} {report.detected_version}.",
            metadata={
                "project_id": str(project_id),
                "detected_version": report.detected_version,
                "install_path": report.install_path,
            },
        )

    def disconnect(self, project_id: UUID) -> IntegrationResult:
        error: str | None = None
        if self._helper is not None:
            try:
                app_obj = getattr(self._helper, "ApplicationExit", None)
                if callable(app_obj):
                    app_obj(False)
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
            finally:
                self._helper = None
                self._connected = False

        return IntegrationResult(
            software=self._profile.software,
            operation=IntegrationOperation.DISCONNECT,
            status=IntegrationOperationStatus.SUCCESS,
            message=f"Disconnected from {self._profile.software.value}.",
            metadata={"project_id": str(project_id), "error": error},
        )

    def export_model_from_pem(
        self,
        project_id: UUID,
        *,
        pem: ProjectEngineeringModel,
        pem_snapshot_id: UUID,
        pem_version: int,
        destination_path: str,
        foundation_spec: dict[str, Any] | None = None,
    ) -> IntegrationResult:
        report = self.detect_capability()
        if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
            return self._unavailable(IntegrationOperation.EXPORT_MODEL, project_id, report=report)

        export = build_external_model_export(
            project_id=project_id,
            pem=pem,
            pem_snapshot_id=pem_snapshot_id,
            pem_version=pem_version,
            software=self._profile.software,
            software_version=report.detected_version or self._profile.expected_version,
        )
        valid, issues = validate_external_model_export(export)
        if not valid:
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.EXPORT_MODEL,
                status=IntegrationOperationStatus.FAILED,
                message="Model export validation failed before external software transfer.",
                metadata={
                    "project_id": str(project_id),
                    "validation_issues": issues,
                },
            )

        export_path = Path(destination_path)
        export_path.parent.mkdir(parents=True, exist_ok=True)
        export_path.write_text(json.dumps(export.model_dump(mode="json"), indent=2), encoding="utf-8")

        vendor_export_status = "MANIFEST_ONLY"
        vendor_error: str | None = None
        vendor_build_report: dict[str, Any] | None = None
        external_model_identity = str(uuid4())
        failure_class = "MODEL_BUILD_FAILURE"
        length_unit = "m"
        force_unit = "kN"
        unit_config = export.metadata.get("unit_configuration", {})
        if isinstance(unit_config, dict):
            length_unit = str(unit_config.get("length_unit", length_unit))
            force_unit = str(unit_config.get("force_unit", force_unit))
        if self._profile.software == IntegrationSoftware.SAFE and not (foundation_spec or {}).get("ready"):
            missing = list((foundation_spec or {}).get("missing") or [])
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.EXPORT_MODEL,
                status=IntegrationOperationStatus.FAILED,
                message=(
                    "SAFE foundation design did not start. "
                    + ("; ".join(missing) if missing else "A validated isolated-footing specification is required.")
                ),
                metadata={
                    "project_id": str(project_id),
                    "pem_snapshot_id": str(pem_snapshot_id),
                    "pem_version": pem_version,
                    "destination_path": str(export_path),
                    "vendor_export_status": "NOT_BUILT",
                    "failure_class": "MISSING_INPUTS",
                    "missing_inputs": missing,
                    "analysis_executed": False,
                    "manifest_is_not_analysis": True,
                },
            )
        try:
            if not self._connected:
                connect_result = self.connect(project_id)
                if connect_result.status != IntegrationOperationStatus.SUCCESS:
                    connect_result.metadata["manifest_is_not_analysis"] = True
                    connect_result.metadata["analysis_executed"] = False
                    return connect_result

            sap_model = getattr(self._helper, "SapModel", None)
            if sap_model is None:
                raise RuntimeError("Vendor SapModel object is not available")
            initialize = getattr(sap_model, "InitializeNewModel", None)
            if not callable(initialize):
                raise RuntimeError("Vendor InitializeNewModel API is not available")
            unit_system = CSI_UNIT_SYSTEM_KN_M_C
            init_result = initialize(unit_system)
            init_code = init_result[0] if isinstance(init_result, tuple) else init_result
            if init_code not in (0, None):
                raise RuntimeError(f"InitializeNewModel returned code {init_code}")
            vendor_export_status = "VENDOR_MODEL_INITIALIZED"
            if self._profile.software == IntegrationSoftware.SAFE:
                vendor_build_report = build_safe_foundation_model(sap_model, foundation_spec or {})
            else:
                vendor_build_report = build_vendor_model_from_export(
                    sap_model,
                    export,
                    length_unit=length_unit,
                    force_unit=force_unit,
                )
            build_status = vendor_build_report.get("vendor_build_status", "PARTIAL")
            if build_status == "COMPLETE":
                vendor_export_status = "VENDOR_MODEL_BUILT"
            elif build_status == "PARTIAL":
                vendor_export_status = "VENDOR_MODEL_PARTIAL"
            else:
                vendor_export_status = "VENDOR_MODEL_BUILD_FAILED"
        except Exception as exc:  # noqa: BLE001
            status, failure_class = classify_vendor_failure(exc, default_class="MODEL_BUILD_FAILURE")
            vendor_error = str(exc)
            vendor_export_status = "VENDOR_EXPORT_FAILED"
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.EXPORT_MODEL,
                status=status,
                message=(
                    f"{self._profile.software.value} model build failed. "
                    "The JSON export manifest is not an analysis result."
                ),
                metadata={
                    "project_id": str(project_id),
                    "pem_snapshot_id": str(pem_snapshot_id),
                    "pem_version": pem_version,
                    "destination_path": str(export_path),
                    "external_model_identity": external_model_identity,
                    "vendor_export_status": vendor_export_status,
                    "vendor_build_report": vendor_build_report,
                    "vendor_error": vendor_error,
                    "failure_class": failure_class,
                    "analysis_executed": False,
                    "manifest_is_not_analysis": True,
                    "exported_at": datetime.now(UTC).isoformat(),
                },
            )

        built = vendor_export_status == "VENDOR_MODEL_BUILT"
        return IntegrationResult(
            software=self._profile.software,
            operation=IntegrationOperation.EXPORT_MODEL,
            status=IntegrationOperationStatus.SUCCESS if built else IntegrationOperationStatus.FAILED,
            message=(
                f"{self._profile.software.value} vendor model was built from the PEM."
                if built
                else (
                    f"{self._profile.software.value} vendor model was not complete. "
                    "The JSON export manifest is not an analysis result and analysis was not run."
                )
            ),
            metadata={
                "project_id": str(project_id),
                "pem_snapshot_id": str(pem_snapshot_id),
                "pem_version": pem_version,
                "destination_path": str(export_path),
                "external_model_identity": external_model_identity,
                "vendor_export_status": vendor_export_status,
                "vendor_build_report": vendor_build_report,
                "vendor_error": vendor_error,
                "failure_class": None if built else failure_class,
                "analysis_executed": False,
                "manifest_is_not_analysis": True,
                "exported_at": datetime.now(UTC).isoformat(),
                "software_version": report.detected_version or self._profile.expected_version,
            },
        )

    def import_model(self, project_id: UUID, *, source_path: str) -> IntegrationResult:
        report = self.detect_capability()
        if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
            return self._unavailable(IntegrationOperation.IMPORT_MODEL, project_id, report=report)

        path = Path(source_path)
        if not path.is_file():
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.IMPORT_MODEL,
                status=IntegrationOperationStatus.FAILED,
                message="Import source file was not found.",
                metadata={"project_id": str(project_id), "source_path": source_path},
            )

        return IntegrationResult(
            software=self._profile.software,
            operation=IntegrationOperation.IMPORT_MODEL,
            status=IntegrationOperationStatus.SUCCESS,
            message=(
                f"Import manifest received for {self._profile.software.value}. "
                "External data must be validated before it can update engineering records."
            ),
            metadata={
                "project_id": str(project_id),
                "source_path": source_path,
                "imported_at": datetime.now(UTC).isoformat(),
            },
        )

    def export_model(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        return self._unavailable(
            IntegrationOperation.EXPORT_MODEL,
            project_id,
            message=(
                f"{self._profile.software.value} export requires PEM context. "
                "Use the project-scoped export workflow."
            ),
            destination_path=destination_path,
        )

    def run_analysis(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult:
        report = self.detect_capability()
        if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
            return self._unavailable(IntegrationOperation.RUN_ANALYSIS, project_id, report=report)

        if not self._connected:
            connect_result = self.connect(project_id)
            if connect_result.status != IntegrationOperationStatus.SUCCESS:
                return connect_result

        analysis_type = str(parameters.get("analysis_type", "STATIC")).upper()
        try:
            sap_model = getattr(self._helper, "SapModel", None)
            if sap_model is None:
                raise RuntimeError("Vendor SapModel object is not available")

            analyze = getattr(getattr(sap_model, "Analyze", None), "RunAnalysis", None)
            if not callable(analyze):
                raise RuntimeError("Vendor RunAnalysis API is not available")

            ret = analyze()
            ret_code = ret[0] if isinstance(ret, tuple) else ret
            if ret_code not in (0, None):
                raise RuntimeError(f"Vendor RunAnalysis returned code {ret_code}")
        except Exception as exc:  # noqa: BLE001
            status, failure_class = classify_vendor_failure(exc, default_class="ANALYSIS_FAILURE")
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.RUN_ANALYSIS,
                status=status,
                message=f"{self._profile.software.value} analysis execution failed.",
                metadata={
                    "project_id": str(project_id),
                    "analysis_type": analysis_type,
                    "error": str(exc),
                    "failure_class": failure_class,
                    "analysis_executed": False,
                },
            )

        return IntegrationResult(
            software=self._profile.software,
            operation=IntegrationOperation.RUN_ANALYSIS,
            status=IntegrationOperationStatus.SUCCESS,
            message=f"{self._profile.software.value} analysis executed successfully.",
            metadata={
                "project_id": str(project_id),
                "analysis_type": analysis_type,
                "executed_at": datetime.now(UTC).isoformat(),
                "execution_mode": "vendor",
                "failure_class": None,
                "analysis_executed": True,
            },
        )

    def extract_results(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult:
        report = self.detect_capability()
        if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
            return self._unavailable(
                IntegrationOperation.EXTRACT_RESULTS,
                project_id,
                report=report,
                extraction_status=CsiExtractionStatus.NOT_CONNECTED.value,
            )

        if not self._connected:
            connect_result = self.connect(project_id)
            if connect_result.status != IntegrationOperationStatus.SUCCESS:
                connect_result.metadata["extraction_status"] = CsiExtractionStatus.NOT_CONNECTED.value
                return connect_result

        pem_snapshot_id = UUID(str(parameters["pem_snapshot_id"]))
        pem_version = int(parameters["pem_version"])
        analysis_run_id = parameters.get("analysis_run_id")

        try:
            sap_model = getattr(self._helper, "SapModel", None)
            if sap_model is None:
                raise RuntimeError("Vendor SapModel object is not available")

            member_ids = {str(item) for item in parameters.get("member_ids", []) if item}
            joint_ids = {str(item) for item in parameters.get("joint_ids", []) if item}
            load_case_ids = {str(item) for item in parameters.get("load_case_ids", []) if item}
            load_combination_ids = {
                str(item) for item in parameters.get("load_combination_ids", []) if item
            }

            raw_results, extraction_summary = extract_csi_results(
                sap_model,
                software=self._profile.software,
                vendor_model_identity=parameters.get("external_model_identity"),
                pem_version=pem_version,
                member_ids=member_ids or None,
                joint_ids=joint_ids or None,
                load_case_ids=load_case_ids or None,
                load_combination_ids=load_combination_ids or None,
                include_shell_results=self._profile.software.value == "SAFE",
            )

            if extraction_summary.overall_status == CsiExtractionStatus.NOT_ANALYZED:
                return IntegrationResult(
                    software=self._profile.software,
                    operation=IntegrationOperation.EXTRACT_RESULTS,
                    status=IntegrationOperationStatus.FAILED,
                    message=(
                        f"{self._profile.software.value} model has not completed analysis; "
                        "no results were extracted."
                    ),
                    metadata={
                        "project_id": str(project_id),
                        "extraction_status": extraction_summary.overall_status.value,
                        "extraction_summary": extraction_summary.model_dump(mode="json"),
                        "engineering_results_available": False,
                        "failure_class": "EXTRACTION_FAILURE",
                    },
                )

            raw_results = normalize_csi_raw_results(
                raw_results,
                extraction_summary=extraction_summary,
                target_force_unit=str(parameters.get("target_force_unit", "kip")),
                target_moment_unit=str(parameters.get("target_moment_unit", "kip-ft")),
                target_length_unit=str(parameters.get("target_length_unit", "ft")),
            )
        except Exception as exc:  # noqa: BLE001
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.EXTRACT_RESULTS,
                status=IntegrationOperationStatus.FAILED,
                message=f"{self._profile.software.value} result extraction failed.",
                metadata={
                    "project_id": str(project_id),
                    "error": str(exc),
                    "extraction_status": CsiExtractionStatus.FAILED.value,
                    "engineering_results_available": False,
                    "failure_class": classify_vendor_failure(exc, default_class="EXTRACTION_FAILURE")[1],
                },
            )

        parsed = parse_external_analysis_results(
            software=self._profile.software,
            software_version=report.detected_version or self._profile.expected_version,
            project_id=project_id,
            pem_snapshot_id=pem_snapshot_id,
            pem_version=pem_version,
            raw_results=raw_results,
            analysis_run_id=UUID(str(analysis_run_id)) if analysis_run_id else None,
        )
        valid, issues = validate_imported_results(parsed)
        extraction_status = extraction_summary.overall_status.value
        if extraction_summary.validation_findings:
            extraction_status = CsiExtractionStatus.FAILED.value

        if not valid:
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.EXTRACT_RESULTS,
                status=IntegrationOperationStatus.FAILED,
                message="Imported results did not pass validation.",
                metadata={
                    "project_id": str(project_id),
                    "validation_issues": issues,
                    "parsed_results": parsed.model_dump(mode="json"),
                    "extraction_status": extraction_status,
                    "extraction_summary": extraction_summary.model_dump(mode="json"),
                    "engineering_results_available": False,
                    "failure_class": "EXTRACTION_FAILURE",
                },
            )

        requested_identity = parameters.get("external_model_identity")
        returned_identity = parsed.provenance.get("external_model_identity")
        if requested_identity and returned_identity and str(requested_identity) != str(returned_identity):
            return IntegrationResult(
                software=self._profile.software,
                operation=IntegrationOperation.EXTRACT_RESULTS,
                status=IntegrationOperationStatus.FAILED,
                message="Extracted results belong to a different vendor model than the one that was analyzed.",
                metadata={
                    "project_id": str(project_id),
                    "failure_class": "EXTRACTION_FAILURE",
                    "engineering_results_available": False,
                    "requested_model_identity": str(requested_identity),
                    "returned_model_identity": str(returned_identity),
                },
            )

        return IntegrationResult(
            software=self._profile.software,
            operation=IntegrationOperation.EXTRACT_RESULTS,
            status=IntegrationOperationStatus.SUCCESS,
            message=(
                f"Imported {len(parsed.result_types_present)} supported result type(s) "
                f"from {self._profile.software.value} ({extraction_summary.overall_status.value})."
            ),
            metadata={
                "project_id": str(project_id),
                "parsed_results": parsed.model_dump(mode="json"),
                "result_types_present": parsed.result_types_present,
                "extraction_status": extraction_status,
                "extraction_summary": extraction_summary.model_dump(mode="json"),
                "execution_mode": "vendor",
            },
        )

    def supports_operation(self, operation: IntegrationOperation) -> bool:
        return operation in {
            IntegrationOperation.IMPORT_MODEL,
            IntegrationOperation.EXPORT_MODEL,
            IntegrationOperation.RUN_ANALYSIS,
            IntegrationOperation.EXTRACT_RESULTS,
            IntegrationOperation.STATUS,
            IntegrationOperation.CONNECT,
            IntegrationOperation.DISCONNECT,
            IntegrationOperation.DETECT,
        }

    def _start_application(self) -> Any:
        last_error: Exception | None = None
        for prog_id in self._profile.prog_ids:
            try:
                helper = self._create_com_object(prog_id)
                start = getattr(helper, "ApplicationStart", None)
                if callable(start):
                    start(False)
                return helper
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError("No COM helper could be created")

    def _create_com_object(self, prog_id: str) -> Any:
        if self._com_probe is not None:
            if not self._com_probe(prog_id):
                raise RuntimeError(f"COM probe failed for {prog_id}")
            return object()

        try:
            import comtypes.client

            return comtypes.client.CreateObject(prog_id)
        except ImportError:
            pass
        except Exception:
            raise

        try:
            import win32com.client

            return win32com.client.Dispatch(prog_id)
        except ImportError as exc:
            raise RuntimeError("COM automation libraries are not installed") from exc

    def _unavailable(
        self,
        operation: IntegrationOperation,
        project_id: UUID,
        *,
        report: SoftwareCapabilityReport | None = None,
        message: str | None = None,
        **metadata: Any,
    ) -> IntegrationResult:
        report = report or self.detect_capability()
        status = _map_availability_to_status(report.availability)
        resolved_message = message or report.message or (
            f"{self._profile.software.value} {operation.value} requires local "
            f"{self._profile.software.value} {self._profile.expected_version} installation"
        )
        return IntegrationResult(
            software=self._profile.software,
            operation=operation,
            status=status,
            message=resolved_message,
            metadata={
                "project_id": str(project_id),
                "failure_class": _failure_class_for_availability(status, resolved_message),
                "analysis_executed": False,
                **report.metadata,
                **metadata,
            },
        )


class EtabsAdapter(CsiStructuralAdapter):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(CSI_PROFILES[IntegrationSoftware.ETABS], **kwargs)


class Sap2000Adapter(CsiStructuralAdapter):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(CSI_PROFILES[IntegrationSoftware.SAP2000], **kwargs)


class SafeAdapter(CsiStructuralAdapter):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(CSI_PROFILES[IntegrationSoftware.SAFE], **kwargs)
