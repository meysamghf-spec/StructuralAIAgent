"""
Phase H structural schedules: S-201 beams, S-202 columns, S-203 slabs.

Schedules are a derived view of the persisted PEM. A cell is filled only from
a section, reinforcement set, or design check that already exists on that
member. Missing data stays ``N/A — not available in PEM``. ``NOT_CHECKED`` is
never promoted to ``PASS``.

Rows may be grouped when section, level, reinforcement and status match, but
every PEM member id in the group is kept on the row and on the table geometry.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from app.application.drawing.annotation import LAYER_SCHEDULE, LAYER_TEXT, PrimitiveFactory
from app.application.drawing.sheet_builder import SheetBuildContext
from app.domain.models.drawing import (
    NOT_IN_PEM,
    Discipline,
    DrawingSchedule,
    DrawingSheet,
    DrawingView,
    ProjectionKind,
    ScheduleRow,
    SheetAvailability,
    SourceElementKind,
)
from app.domain.models.pem_architecture import Point2D
from app.domain.models.pem_structural import (
    DesignCheckStatus,
    MemberDesignCheck,
    MemberType,
    ReinforcementBarSet,
    StirrupLayout,
    StructuralMember,
)

DEFAULT_PAGE_ROWS = 22
_ROW_HEIGHT_M = 0.42
_HEADER_HEIGHT_M = 0.50
_TEXT_HEIGHT_M = 0.16

_SCHEDULES: tuple[tuple[str, str, MemberType, SourceElementKind], ...] = (
    ("S-201", "Beam schedule", MemberType.BEAM, SourceElementKind.BEAM),
    ("S-202", "Column schedule", MemberType.COLUMN, SourceElementKind.COLUMN),
    ("S-203", "Slab / reinforcement schedule", MemberType.SLAB, SourceElementKind.SLAB),
)


@dataclass(frozen=True)
class _Column:
    header: str
    width_m: float


_BEAM_COLUMNS = (
    _Column("MARK", 1.8),
    _Column("QTY", 0.7),
    _Column("LEVEL", 1.6),
    _Column("SECTION m", 2.2),
    _Column("LONGITUDINAL", 3.4),
    _Column("STIRRUPS", 3.4),
    _Column("STATUS", 1.6),
)
_COLUMN_COLUMNS = (
    _Column("MARK", 1.8),
    _Column("QTY", 0.7),
    _Column("LEVEL", 1.6),
    _Column("SECTION m", 2.2),
    _Column("LONGITUDINAL", 3.4),
    _Column("TIES", 3.4),
    _Column("STATUS", 1.6),
)
_SLAB_COLUMNS = (
    _Column("MARK", 1.8),
    _Column("QTY", 0.7),
    _Column("LEVEL", 1.6),
    _Column("THICKNESS m", 1.8),
    _Column("BOTTOM", 3.2),
    _Column("TOP", 3.2),
    _Column("STATUS", 1.6),
)


def build_schedule_sheets(
    context: SheetBuildContext,
    *,
    page_rows: int = DEFAULT_PAGE_ROWS,
) -> list[DrawingSheet]:
    """S-201, S-202 and S-203, split onto continuation sheets when a table overflows."""
    if page_rows < 1:
        raise ValueError("page_rows must be at least 1")
    sheets: list[DrawingSheet] = []
    for number, title, member_type, kind in _SCHEDULES:
        sheets.extend(
            _sheets_for_member_type(
                context,
                sheet_number=number,
                title=title,
                member_type=member_type,
                kind=kind,
                page_rows=page_rows,
            )
        )
    return sheets


def _sheets_for_member_type(
    context: SheetBuildContext,
    *,
    sheet_number: str,
    title: str,
    member_type: MemberType,
    kind: SourceElementKind,
    page_rows: int,
) -> list[DrawingSheet]:
    members = list(context.pem.members_by_type.get(member_type, []))
    columns = _columns_for(member_type)
    rows = _group_rows(context, members, member_type, kind)
    if not rows:
        rows = [
            ScheduleRow(
                cells=[NOT_IN_PEM] * len(columns),
                source_element_ids=[],
                source_element_kind=kind,
                metadata={"source_element_type": kind.value, "empty": True},
            )
        ]
    pages = [rows[index : index + page_rows] for index in range(0, len(rows), page_rows)]
    page_count = len(pages)
    built: list[DrawingSheet] = []
    for page_index, page_rows_slice in enumerate(pages, start=1):
        number = sheet_number if page_index == 1 else f"{sheet_number}.{page_index}"
        page_title = title if page_count == 1 else f"{title} ({page_index} of {page_count})"
        built.append(
            _build_page(
                context,
                sheet_number=number,
                family=sheet_number,
                title=page_title,
                columns=columns,
                rows=page_rows_slice,
                kind=kind,
                page_index=page_index,
                page_count=page_count,
                member_count=len(members),
            )
        )
    return built


def _columns_for(member_type: MemberType) -> tuple[_Column, ...]:
    if member_type is MemberType.COLUMN:
        return _COLUMN_COLUMNS
    if member_type is MemberType.SLAB:
        return _SLAB_COLUMNS
    return _BEAM_COLUMNS


def _group_rows(
    context: SheetBuildContext,
    members: list[StructuralMember],
    member_type: MemberType,
    kind: SourceElementKind,
) -> list[ScheduleRow]:
    grouped: dict[tuple[str, ...], list[StructuralMember]] = defaultdict(list)
    descriptions: dict[tuple[str, ...], list[str]] = {}
    for member in members:
        cells = _member_cells(context, member, member_type)
        key = tuple(cells)
        grouped[key].append(member)
        descriptions[key] = cells
    rows: list[ScheduleRow] = []
    ordered = sorted(grouped, key=lambda key: (key[2], key[0], key))
    for key in ordered:
        group = sorted(grouped[key], key=lambda item: item.id)
        ids = [member.id for member in group]
        cells = list(descriptions[key])
        cells[1] = str(len(ids))
        rows.append(
            ScheduleRow(
                cells=cells,
                source_element_ids=ids,
                source_element_kind=kind,
                metadata={
                    "source_element_type": kind.value,
                    "member_count": len(ids),
                },
            )
        )
    return rows


def _member_cells(
    context: SheetBuildContext,
    member: StructuralMember,
    member_type: MemberType,
) -> list[str]:
    pem = context.pem
    level = pem.levels.get(member.level_id or "")
    level_text = level.name if level is not None and level.name else NOT_IN_PEM
    reinforcement = pem.reinforcement.get(member.id)
    status = _status_text(pem.checks.get(member.id, []))
    if member_type is MemberType.SLAB:
        section = pem.slab_sections.get(member.section_id)
        mark = section.name if section is not None and section.name else NOT_IN_PEM
        thickness = (
            f"{section.thickness:.3f}"
            if section is not None
            else NOT_IN_PEM
        )
        bottom = _bar_sets(reinforcement.slab_bottom if reinforcement else [])
        top = _bar_sets(reinforcement.slab_top if reinforcement else [])
        return [mark, "1", level_text, thickness, bottom, top, status]
    if member_type is MemberType.COLUMN:
        section = pem.column_sections.get(member.section_id)
    else:
        section = pem.beam_sections.get(member.section_id)
    mark = section.name if section is not None and section.name else NOT_IN_PEM
    size = (
        f"{section.width:.3f} x {section.depth:.3f}"
        if section is not None
        else NOT_IN_PEM
    )
    longitudinal = _bar_sets(reinforcement.longitudinal if reinforcement else [])
    transverse = _stirrup_text(reinforcement.stirrups if reinforcement else None)
    return [mark, "1", level_text, size, longitudinal, transverse, status]


def _bar_sets(bars: list[ReinforcementBarSet]) -> str:
    if not bars:
        return NOT_IN_PEM
    return "; ".join(_one_bar(bar) for bar in bars)


def _one_bar(bar: ReinforcementBarSet) -> str:
    designation = bar.designation.strip() if bar.designation else ""
    size = f"{bar.diameter_mm:.0f} mm"
    if bar.spacing_mm is not None:
        spaced = f"{designation} ({size}) @ {bar.spacing_mm:.0f} mm".strip()
        return spaced
    count = f"{bar.count} x " if bar.count else ""
    named = f"{designation} " if designation else ""
    return f"{count}{named}({size})".replace("  ", " ").strip()


def _stirrup_text(layout: StirrupLayout | None) -> str:
    if layout is None:
        return NOT_IN_PEM
    designation = layout.designation.strip() if layout.designation else ""
    named = f"{designation} " if designation else ""
    return (
        f"{layout.legs}-leg {named}({layout.diameter_mm:.0f} mm) @ {layout.spacing_mm:.0f} mm"
    ).replace("  ", " ")


def _status_text(checks: list[MemberDesignCheck]) -> str:
    """Worst truthful status. NOT_CHECKED outranks PASS and is never rewritten."""
    if not checks:
        return DesignCheckStatus.NOT_CHECKED.value
    if any(item.status is DesignCheckStatus.FAIL for item in checks):
        return DesignCheckStatus.FAIL.value
    if any(item.status is DesignCheckStatus.NOT_CHECKED for item in checks):
        return DesignCheckStatus.NOT_CHECKED.value
    if any(item.status is DesignCheckStatus.WARNING for item in checks):
        return DesignCheckStatus.WARNING.value
    if any(item.status is DesignCheckStatus.PASS for item in checks):
        return DesignCheckStatus.PASS.value
    return DesignCheckStatus.NOT_CHECKED.value


def _build_page(
    context: SheetBuildContext,
    *,
    sheet_number: str,
    family: str,
    title: str,
    columns: tuple[_Column, ...],
    rows: list[ScheduleRow],
    kind: SourceElementKind,
    page_index: int,
    page_count: int,
    member_count: int,
) -> DrawingSheet:
    view = _table_view(sheet_number, columns, rows, kind, context.source_model_id)
    missing = sorted(
        {
            columns[index].header
            for row in rows
            for index, cell in enumerate(row.cells)
            if cell == NOT_IN_PEM or cell == DesignCheckStatus.NOT_CHECKED.value
        }
    )
    empty = member_count == 0
    availability = SheetAvailability.NOT_AVAILABLE if empty else (
        SheetAvailability.PARTIAL if missing else SheetAvailability.AVAILABLE
    )
    notes = [
        "PRELIMINARY schedule derived only from persisted PEM sections, reinforcement and design checks.",
        "Grouped rows keep every underlying PEM member id in source_element_ids.",
        "A blank engineering value is N/A — not available in PEM. Nothing is inferred.",
        "NOT_CHECKED is not a passing result and is not promoted to PASS.",
        "Reinforcement detailing beyond the PEM record, punching shear, and full slab FEM are not added here.",
    ]
    if page_count > 1:
        notes.append(f"Sheet {page_index} of {page_count} for {family}.")
    schedule = DrawingSchedule(
        id=f"SCH-{sheet_number}",
        title=title,
        columns=[column.header for column in columns],
        rows=rows,
        notes=list(notes),
        metadata={
            "schedule_family": family,
            "page": page_index,
            "page_count": page_count,
            "source_element_type": kind.value,
            "member_count": member_count,
        },
    )
    return context.build_sheet(
        sheet_number=sheet_number,
        title=title,
        discipline=Discipline.STRUCTURAL,
        views=[view],
        schedule=schedule,
        notes=notes,
        availability=availability,
        missing_data=missing,
        metadata={
            "schedule_family": family,
            "page": page_index,
            "page_count": page_count,
            "source_element_type": kind.value,
            "member_count": member_count,
            "phase": "H",
        },
    )


def _table_view(
    sheet_number: str,
    columns: tuple[_Column, ...],
    rows: list[ScheduleRow],
    kind: SourceElementKind,
    source_model_id: str,
) -> DrawingView:
    factory = PrimitiveFactory(f"{sheet_number}-TABLE", f"SCHEDULE:{sheet_number}")
    total_width = sum(column.width_m for column in columns)
    total_height = _HEADER_HEIGHT_M + len(rows) * _ROW_HEIGHT_M
    primitives = []
    primitives.extend(
        _grid(
            factory,
            total_width=total_width,
            total_height=total_height,
            columns=columns,
            row_count=len(rows),
            kind=kind,
            row_ids=[row.source_element_ids for row in rows],
            source_model_id=source_model_id,
        )
    )
    primitives.extend(
        _header_text(factory, columns, total_height, source_model_id)
    )
    for index, row in enumerate(rows):
        top = total_height - _HEADER_HEIGHT_M - index * _ROW_HEIGHT_M
        baseline = top - _ROW_HEIGHT_M * 0.62
        primitives.extend(_row_text(factory, columns, row, kind, baseline))
    return DrawingView(
        id=f"{sheet_number}-TABLE",
        name=sheet_number,
        projection=ProjectionKind.SCHEDULE,
        projection_label=f"SCHEDULE:{sheet_number}",
        primitives=primitives,
        metadata={"source_element_type": kind.value},
    )


def _grid(
    factory: PrimitiveFactory,
    *,
    total_width: float,
    total_height: float,
    columns: tuple[_Column, ...],
    row_count: int,
    kind: SourceElementKind,
    row_ids: list[list[str]],
    source_model_id: str,
) -> list:
    lines = [
        factory.polyline(
            [
                Point2D(x=0.0, y=0.0),
                Point2D(x=total_width, y=0.0),
                Point2D(x=total_width, y=total_height),
                Point2D(x=0.0, y=total_height),
            ],
            layer=LAYER_SCHEDULE,
            closed=True,
            source_element_ids=[source_model_id],
            source_element_kind=SourceElementKind.PROJECT,
            metadata={"source_element_type": "PROJECT", "role": "table-border"},
        )
    ]
    y = total_height - _HEADER_HEIGHT_M
    lines.append(
        factory.line(
            Point2D(x=0.0, y=y),
            Point2D(x=total_width, y=y),
            layer=LAYER_SCHEDULE,
            source_element_ids=[source_model_id],
            source_element_kind=SourceElementKind.PROJECT,
            metadata={"source_element_type": "PROJECT", "role": "header-rule"},
        )
    )
    for index in range(row_count):
        y = total_height - _HEADER_HEIGHT_M - (index + 1) * _ROW_HEIGHT_M
        ids = row_ids[index]
        lines.append(
            factory.line(
                Point2D(x=0.0, y=y),
                Point2D(x=total_width, y=y),
                layer=LAYER_SCHEDULE,
                source_element_ids=list(ids),
                source_element_kind=kind if ids else SourceElementKind.PROJECT,
                metadata={"source_element_type": kind.value, "role": "row-rule"},
            )
        )
    x = 0.0
    for column in columns[:-1]:
        x += column.width_m
        lines.append(
            factory.line(
                Point2D(x=x, y=0.0),
                Point2D(x=x, y=total_height),
                layer=LAYER_SCHEDULE,
                source_element_ids=[source_model_id],
                source_element_kind=SourceElementKind.PROJECT,
                metadata={"source_element_type": "PROJECT", "role": "column-rule"},
            )
        )
    return lines


def _header_text(
    factory: PrimitiveFactory,
    columns: tuple[_Column, ...],
    total_height: float,
    source_model_id: str,
) -> list:
    texts = []
    x = 0.08
    y = total_height - _HEADER_HEIGHT_M * 0.62
    for column in columns:
        texts.append(
            factory.text(
                Point2D(x=x, y=y),
                column.header,
                layer=LAYER_TEXT,
                height_m=_TEXT_HEIGHT_M,
                anchor="LEFT",
                source_element_ids=[source_model_id],
                source_element_kind=SourceElementKind.PROJECT,
                metadata={"source_element_type": "PROJECT", "role": "header"},
            )
        )
        x += column.width_m
    return texts


def _row_text(
    factory: PrimitiveFactory,
    columns: tuple[_Column, ...],
    row: ScheduleRow,
    kind: SourceElementKind,
    baseline: float,
) -> list:
    texts = []
    x = 0.08
    ids = list(row.source_element_ids)
    element_kind = kind if ids else SourceElementKind.PROJECT
    for index, column in enumerate(columns):
        value = row.cells[index] if index < len(row.cells) else NOT_IN_PEM
        texts.append(
            factory.text(
                Point2D(x=x, y=baseline),
                value,
                layer=LAYER_TEXT,
                height_m=_TEXT_HEIGHT_M,
                anchor="LEFT",
                source_element_ids=ids or [],
                source_element_kind=element_kind,
                metadata={"source_element_type": kind.value, "column": column.header},
            )
        )
        x += column.width_m
    return texts


def schedule_source_ids(sheets: list[DrawingSheet], family: str) -> set[str]:
    """Every PEM id retained by one schedule family, including continuation sheets."""
    found: set[str] = set()
    for sheet in sheets:
        if sheet.metadata.get("schedule_family") != family or sheet.schedule is None:
            continue
        for row in sheet.schedule.rows:
            found.update(row.source_element_ids)
    return found
