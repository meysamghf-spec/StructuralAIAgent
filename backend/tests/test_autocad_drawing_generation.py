"""AutoCAD drawing commands and execution states. Fake COM is not an AutoCAD run."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.models.drawing import (
    Discipline,
    DrawingPrimitive,
    DrawingSet,
    DrawingSheet,
    DrawingView,
    PrimitiveKind,
    ProjectionKind,
    TitleBlock,
)
from app.domain.models.integration import (
    IntegrationOperationStatus,
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)
from app.infrastructure.integrations.autocad_adapter import AutocadAdapter
from app.infrastructure.integrations.autocad_drawing import commands_from_drawing_set, validate_sheet_plan


def _available() -> SoftwareCapabilityReport:
    return SoftwareCapabilityReport(
        software=IntegrationSoftware.AUTOCAD,
        expected_version="2027",
        availability=SoftwareAvailabilityStatus.AVAILABLE,
        detected_version="2027",
        message="Fake capability for a unit test. AutoCAD was not started.",
    )


def _plan() -> dict:
    return {
        "commands": [
            {
                "kind": "LINE",
                "layer": "S-COLS",
                "points": [[0.0, 0.0, 0.0], [3000.0, 0.0, 0.0]],
                "closed": False,
                "text": None,
                "text_height_mm": 250.0,
                "radius_mm": None,
                "sheet": "S-101",
                "source_element_ids": ["col-1"],
            },
            {
                "kind": "TEXT",
                "layer": "S-TEXT",
                "points": [[100.0, 100.0, 0.0]],
                "closed": False,
                "text": "S-101 foundation plan",
                "text_height_mm": 250.0,
                "radius_mm": None,
                "sheet": "S-101",
                "source_element_ids": ["col-1"],
            },
        ],
        "geometry_count": 1,
        "annotation_count": 1,
        "sheets": [{"sheet": "S-101", "title": "Foundation", "geometry_count": 1, "annotation_count": 1}],
        "missing_construction_details": ["S-301 structural sections", "S-401 reinforcement details"],
        "units": "mm",
        "construction_ready": False,
        "source_snapshot_id": "snap-1",
        "pem_version": 2,
    }


class _Polyline:
    Closed = False


class _ModelSpace:
    def __init__(self) -> None:
        self.lines: list[tuple[object, object]] = []
        self.texts: list[str] = []

    def AddLine(self, start: object, end: object) -> None:
        self.lines.append((start, end))

    def AddText(self, text: str, point: object, height: float) -> None:
        self.texts.append(text)


class _Document:
    def __init__(self, model: _ModelSpace) -> None:
        self.ModelSpace = model
        self.saved: str | None = None
        self.closed = False

    def SaveAs(self, path: str) -> None:
        Path(path).write_bytes(b"AC1024 fake dwg with geometry")
        self.saved = path

    def Close(self, save: bool) -> None:
        self.closed = True


class _Documents:
    def __init__(self, document: _Document) -> None:
        self._document = document

    def Add(self) -> _Document:
        return self._document


class _Application:
    def __init__(self, document: _Document) -> None:
        self.Documents = _Documents(document)


def test_sheet_plan_converts_metres_and_reports_missing_details() -> None:
    now = datetime.now(UTC)
    title = TitleBlock(
        project_name="Plan",
        drawing_number="S-101",
        drawing_title="Foundation",
        discipline=Discipline.STRUCTURAL,
        revision="0",
        scale="1:100",
        units="m",
        generated_at=now,
        source_model_id="model",
    )
    sheet = DrawingSheet(
        sheet_number="S-101",
        title="Foundation",
        discipline=Discipline.STRUCTURAL,
        source_model_id="model",
        title_block=title,
        views=[
            DrawingView(
                id="v1",
                name="Plan",
                projection=ProjectionKind.PLAN,
                primitives=[
                    DrawingPrimitive(
                        id="p1",
                        kind=PrimitiveKind.LINE,
                        layer="S-COLS",
                        points=[{"x": 1.0, "y": 2.0}, {"x": 4.0, "y": 2.0}],
                        source_element_ids=["col-1"],
                    )
                ],
            )
        ],
    )
    drawing_set = DrawingSet(
        id="ds",
        project_id=uuid4(),
        project_name="Plan",
        source_model_id="model",
        pem_version=3,
        sheets=[sheet],
        metadata={"pending_milestones": ["S-401 reinforcement details"]},
    )
    plan = commands_from_drawing_set(drawing_set)
    assert plan["geometry_count"] == 1
    assert plan["commands"][0]["points"][0] == [1000.0, 2000.0, 0.0]
    assert plan["commands"][0]["points"][1] == [4000.0, 2000.0, 0.0]
    assert plan["missing_construction_details"] == ["S-401 reinforcement details"]
    assert plan["construction_ready"] is False
    valid, _reason = validate_sheet_plan(plan)
    assert valid is True
    empty_valid, empty_reason = validate_sheet_plan({"commands": [], "geometry_count": 0})
    assert empty_valid is False
    assert "no drawable geometry" in empty_reason


def test_fake_com_saves_a_non_empty_dwg_and_does_not_mark_construction_ready(tmp_path: Path) -> None:
    model = _ModelSpace()
    document = _Document(model)
    adapter = AutocadAdapter(com_factory=lambda: _Application(document), capability_override=_available())
    result = adapter.generate_drawing(
        uuid4(),
        parameters={"sheet_plan": _plan(), "output_dir": str(tmp_path)},
    )
    assert result.status == IntegrationOperationStatus.SUCCESS
    assert result.metadata["drawing_executed"] is True
    assert result.metadata["construction_ready"] is False
    assert result.metadata["dwg_bytes"] > 0
    assert result.metadata["missing_construction_details"]
    assert model.lines
    assert model.texts == ["S-101 foundation plan"]
    assert document.saved is not None


def test_empty_plan_is_not_a_successful_drawing(tmp_path: Path) -> None:
    called = {"saved": False}

    class _NoSave(_Document):
        def SaveAs(self, path: str) -> None:
            called["saved"] = True

    adapter = AutocadAdapter(
        com_factory=lambda: _Application(_NoSave(_ModelSpace())),
        capability_override=_available(),
    )
    result = adapter.generate_drawing(
        uuid4(),
        parameters={"sheet_plan": {"commands": [], "geometry_count": 0, "missing_construction_details": ["S-301 structural sections"]}, "output_dir": str(tmp_path)},
    )
    assert result.status == IntegrationOperationStatus.FAILED
    assert result.metadata["failure_class"] == "EMPTY_DRAWING"
    assert result.metadata["drawing_executed"] is False
    assert called["saved"] is False


def test_empty_file_from_saveas_is_not_success(tmp_path: Path) -> None:
    class _EmptySave(_Document):
        def SaveAs(self, path: str) -> None:
            Path(path).write_bytes(b"")

    adapter = AutocadAdapter(
        com_factory=lambda: _Application(_EmptySave(_ModelSpace())),
        capability_override=_available(),
    )
    result = adapter.generate_drawing(
        uuid4(),
        parameters={"sheet_plan": _plan(), "output_dir": str(tmp_path)},
    )
    assert result.status == IntegrationOperationStatus.FAILED
    assert result.metadata["failure_class"] == "EMPTY_DRAWING"
    assert result.metadata["construction_ready"] is False
