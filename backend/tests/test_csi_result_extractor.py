"""Tests for CSI deep result extraction, normalization, and adapter integration."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.csi_result_normalization import normalize_csi_raw_results
from app.application.design_calculations import extract_member_force_demand
from app.application.engineering_result_normalization import normalize_vendor_results
from app.application.service_factory import build_engineering_result_service, build_project_service
from app.domain.models.csi_extraction import CsiExtractionStatus
from app.domain.models.engineering_results import EngineeringResultIngestionRequest
from app.domain.models.integration import (
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)
from app.infrastructure.integrations.csi_result_extractor import extract_csi_results
from app.infrastructure.integrations.csi_structural_adapter import EtabsAdapter, SafeAdapter, Sap2000Adapter
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)
from app.application.service_factory import build_pem_model_service


class _MockAnalyze:
    def __init__(self, analyzed: bool = True) -> None:
        self._analyzed = analyzed

    def GetRunFlag(self) -> int:
        return 1 if self._analyzed else 0


class _MockResultsSetup:
    def DeselectAllCasesAndCombosForOutput(self) -> int:
        return 0

    def SetCaseSelectedForOutput(self, _name: str) -> int:
        return 0


class _MockResults:
    def __init__(self, *, include_shell: bool = False, include_reactions: bool = True) -> None:
        self.Setup = _MockResultsSetup()
        self._include_shell = include_shell
        self._include_reactions = include_reactions

    def FrameForce(
        self,
        _name,
        _item_type,
        _max_min,
        number_results,
        obj,
        elm,
        load_case,
        step_type,
        step_num,
        p,
        v2,
        v3,
        torsion,
        m2,
        m3,
        station,
    ):
        obj.extend(["mbr-1", "mbr-2"])
        elm.extend(["1", "1"])
        load_case.extend(["lc-dead", "lc-dead"])
        step_type.extend(["StepByStep", "StepByStep"])
        step_num.extend([0, 0])
        p.extend([100.0, 80.0])
        v2.extend([12.0, 10.0])
        v3.extend([2.0, 1.5])
        torsion.extend([0.5, 0.4])
        m2.extend([250.0, 200.0])
        m3.extend([20.0, 15.0])
        station.extend([0.0, 1.0])
        number_results[0] = 2
        return 0

    def JointDispl(
        self,
        _name,
        _item_type,
        number_results,
        joint_name,
        load_case,
        step_type,
        step_num,
        u1,
        u2,
        u3,
        r1,
        r2,
        r3,
    ):
        joint_name.extend(["pt-1"])
        load_case.extend(["lc-dead"])
        step_type.extend(["StepByStep"])
        step_num.extend([0])
        u1.extend([0.01])
        u2.extend([0.0])
        u3.extend([0.0])
        r1.extend([0.0])
        r2.extend([0.0])
        r3.extend([0.0])
        number_results[0] = 1
        return 0

    def JointReact(
        self,
        _item_type,
        number_results,
        joint_name,
        load_case,
        step_type,
        step_num,
        f1,
        f2,
        f3,
        m1,
        m2,
        m3,
    ):
        if not self._include_reactions:
            number_results[0] = 0
            return 0
        joint_name.extend(["pt-1"])
        load_case.extend(["lc-dead"])
        step_type.extend(["StepByStep"])
        step_num.extend([0])
        f1.extend([50.0])
        f2.extend([0.0])
        f3.extend([0.0])
        m1.extend([0.0])
        m2.extend([0.0])
        m3.extend([0.0])
        number_results[0] = 1
        return 0

    def AreaForceShell(
        self,
        _name,
        _item_type,
        number_results,
        obj,
        elm,
        load_case,
        step_type,
        step_num,
        values,
    ):
        if not self._include_shell:
            number_results[0] = 0
            return 0
        obj.extend(["slab-1"])
        elm.extend(["1"])
        load_case.extend(["lc-dead"])
        step_type.extend(["StepByStep"])
        step_num.extend([0])
        values.extend([[1.0, 2.0, 3.0]])
        number_results[0] = 1
        return 0


class _MockLoadPatterns:
    def GetNameList(self, number_names, names):
        names.extend(["lc-dead"])
        number_names[0] = 1


class _MockRespCombo:
    def GetNameList(self, number_names, names):
        names.extend(["combo-1"])
        number_names[0] = 1


class _MockSapModel:
    def __init__(self, *, analyzed: bool = True, include_shell: bool = False) -> None:
        self.Analyze = _MockAnalyze(analyzed=analyzed)
        self.Results = _MockResults(include_shell=include_shell)
        self.LoadPatterns = _MockLoadPatterns()
        self.RespCombo = _MockRespCombo()


def _available_report(software: IntegrationSoftware) -> SoftwareCapabilityReport:
    return SoftwareCapabilityReport(
        software=software,
        expected_version="23",
        availability=SoftwareAvailabilityStatus.AVAILABLE,
        message="Mock CSI available",
    )


def test_extract_frame_forces_and_joint_results_from_mock_sap_model() -> None:
    raw, summary = extract_csi_results(
        _MockSapModel(),
        software=IntegrationSoftware.ETABS,
        member_ids={"mbr-1", "mbr-2"},
        joint_ids={"pt-1"},
        load_case_ids={"lc-dead"},
    )
    assert summary.overall_status == CsiExtractionStatus.COMPLETE
    assert len(raw["member_forces"]) == 2
    assert raw["member_forces"][0]["id"] == "mbr-1"
    assert raw["joint_displacements"][0]["joint_name"] == "pt-1"
    assert raw["reactions"][0]["force_fx"] == 50.0


def test_unanalyzed_model_returns_not_analyzed_without_rows() -> None:
    raw, summary = extract_csi_results(
        _MockSapModel(analyzed=False),
        software=IntegrationSoftware.SAP2000,
    )
    assert summary.overall_status == CsiExtractionStatus.NOT_ANALYZED
    assert "member_forces" not in raw


def test_normalize_csi_units_kn_to_kip() -> None:
    raw = {
        "member_forces": [
            {
                "id": "mbr-1",
                "axial_force": 44.48,
                "shear_v2": 4.448,
                "shear_v3": 0.0,
                "torsion": 0.0,
                "moment_m2": 135.58,
                "moment_m3": 0.0,
                "load_case": "lc-dead",
                "source_units": {"force": "kN", "moment": "kN-m"},
            }
        ]
    }
    normalized = normalize_csi_raw_results(raw)
    row = normalized["member_forces"][0]
    assert row["axial_force"] == pytest.approx(10.0, rel=0.02)
    assert row["moment_m2"] == pytest.approx(100.0, rel=0.02)
    assert row["units"]["force"] == "kip"


def test_normalized_frame_forces_feed_codeengine_demand() -> None:
    vendor = normalize_vendor_results(
        {
            "member_forces": [
                {
                    "id": "mbr-1",
                    "axial_force": 10.0,
                    "shear_v2": 4.0,
                    "shear_v3": 0.0,
                    "moment_m2": 120.0,
                    "moment_m3": 15.0,
                    "values": [10.0, 4.0, 0.0, 0.0, 120.0, 15.0],
                    "load_case": "lc-dead",
                }
            ]
        }
    )
    results = vendor.model_dump(mode="json")
    assert extract_member_force_demand(results, "mbr-1", component="moment") == 120.0
    assert extract_member_force_demand(results, "mbr-1", component="axial") == 10.0
    assert extract_member_force_demand(results, "mbr-1", component="shear") == 4.0


def test_etabs_adapter_extract_results_with_mock_helper() -> None:
    adapter = EtabsAdapter(capability_override=_available_report(IntegrationSoftware.ETABS))
    adapter._helper = type("Helper", (), {"SapModel": _MockSapModel()})()
    adapter._connected = True
    result = adapter.extract_results(
        uuid4(),
        parameters={
            "pem_snapshot_id": str(uuid4()),
            "pem_version": 1,
            "member_ids": ["mbr-1", "mbr-2"],
            "joint_ids": ["pt-1"],
            "load_case_ids": ["lc-dead"],
        },
    )
    assert result.status == IntegrationOperationStatus.SUCCESS
    assert result.metadata["extraction_status"] in {"PARTIAL", "COMPLETE"}
    assert "member_forces" in result.metadata["parsed_results"]["results"]


def test_safe_shell_results_supported_when_api_present() -> None:
    raw, summary = extract_csi_results(
        _MockSapModel(include_shell=True),
        software=IntegrationSoftware.SAFE,
        include_shell_results=True,
    )
    assert raw["shell_results"]
    shell_report = next(item for item in summary.categories if item.category.value == "shell_results")
    assert shell_report.status == CsiExtractionStatus.COMPLETE


def test_disconnected_adapter_reports_not_connected() -> None:
    adapter = Sap2000Adapter(com_probe=lambda _prog_id: False)
    result = adapter.extract_results(
        uuid4(),
        parameters={"pem_snapshot_id": str(uuid4()), "pem_version": 1},
    )
    assert result.status in {
        IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
        IntegrationOperationStatus.NOT_INSTALLED,
        IntegrationOperationStatus.NOT_ACCESSIBLE,
    }


def test_stable_ordering_of_extracted_rows() -> None:
    raw, _ = extract_csi_results(_MockSapModel(), software=IntegrationSoftware.ETABS)
    member_ids = [row["id"] for row in raw["member_forces"]]
    assert member_ids == sorted(member_ids)


def test_ingest_unwraps_external_analysis_results_shape(db_session) -> None:
    project = build_project_service().create_project("CSI ingest unwrap").project
    model = build_pem_model_service()
    model.update_geometry(project.id, sample_geometry(), summary="Geometry")
    model.update_materials(project.id, sample_materials(), summary="Materials")
    model.update_sections(project.id, sample_sections(), summary="Sections")
    model.update_members(project.id, sample_members(), summary="Members")
    model.update_supports(project.id, sample_supports(), summary="Supports")
    model.update_load_cases(project.id, sample_load_cases(), summary="Loads")
    model.update_load_combinations(project.id, sample_load_combinations(), summary="Combos")
    _, version, snapshot_id = model.get_current_model(project.id)

    wrapped = {
        "results": {
            "member_forces": [
                {
                    "id": "mbr-1",
                    "values": [10.0, 4.0, 0.0, 0.0, 120.0, 15.0],
                    "load_case": "lc-dead",
                    "units": "kip",
                }
            ]
        },
        "provenance": {"execution_mode": "vendor", "source_software": "ETABS"},
    }
    result_set = build_engineering_result_service().ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project.id,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results=wrapped,
            provenance={"source_software": "ETABS", "execution_mode": "vendor"},
        )
    )
    assert result_set.engineering_results_available is True
    assert result_set.results["frame_forces"]


@pytest.mark.integration
def test_real_com_integration_if_available() -> None:
    adapter = EtabsAdapter()
    report = adapter.detect_capability()
    if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
        pytest.skip("COM integration not executed — vendor software unavailable")
    connect = adapter.connect(uuid4())
    if connect.status != IntegrationOperationStatus.SUCCESS:
        pytest.skip("COM integration not executed — vendor software unavailable")
    assert adapter.supports_operation(IntegrationOperation.EXTRACT_RESULTS)
