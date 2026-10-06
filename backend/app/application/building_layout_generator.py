"""
Deterministic architectural layout generator.

Given a parsed :class:`BuildingBrief` this produces a complete
:class:`BuildingModel` with real coordinates: plot, per-storey footprints, rooms,
corridors, a vertical circulation core, parking bays, walls, doors and windows.

Layout strategy (first version — prioritises geometric validity over architectural
creativity, per the product brief):

* The footprint is the plot reduced by whatever setbacks the brief stated. No
  zoning rule is invented; a missing setback means zero and is recorded as an
  assumption.
* A vertical **core** (stair, optional elevator, service shaft) occupies a band at
  the rear of the footprint. Its x/y position is identical on every storey because
  it is a vertical element.
* Residential storeys use a **central corridor spine** running front-to-back,
  aligned with the stair. Rooms are stacked in two columns either side of the
  spine, so every room shares an edge with the corridor and can take a real door.
* The parking storey places 90-degree bays in rows served by a drive aisle that
  reaches the street edge, with a pedestrian route from the aisle to the core.

Every dimension below is metres. Areas are computed from geometry, never stored
as independent numbers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.application.exceptions import (
    BuildingBriefIncompleteError,
    BuildingLayoutInfeasibleError,
)
from app.domain.models.building_brief import BuildingBrief
from app.domain.models.pem_architecture import (
    ApartmentDefinition,
    BuildingModel,
    CoreDefinition,
    DoorDefinition,
    ElevatorDefinition,
    FloorPlanDefinition,
    FloorType,
    ParkingSpaceDefinition,
    Point2D,
    Polygon2D,
    SiteDefinition,
    SpaceDefinition,
    SpaceUsage,
    StairDefinition,
    StructuralSystem,
    WallDefinition,
    WallType,
    WindowDefinition,
    rectangle,
)


@dataclass(frozen=True)
class LayoutDefaults:
    """Dimensional defaults. Each one applied is recorded as an assumption."""

    storey_height_m: float = 3.0
    parking_storey_height_m: float = 3.0

    exterior_wall_thickness_m: float = 0.25
    interior_wall_thickness_m: float = 0.10
    core_wall_thickness_m: float = 0.20

    corridor_width_m: float = 1.40
    min_room_dimension_m: float = 1.50
    min_room_band_depth_m: float = 2.40

    stair_width_m: float = 2.60
    stair_depth_m: float = 4.60
    elevator_width_m: float = 1.80
    elevator_depth_m: float = 1.80
    shaft_width_m: float = 0.80
    shaft_depth_m: float = 0.80

    riser_height_m: float = 0.175
    tread_depth_m: float = 0.280
    stair_clear_width_m: float = 1.10

    parking_bay_width_m: float = 2.50
    parking_bay_length_m: float = 5.00
    parking_aisle_width_m: float = 5.50
    accessible_bay_width_m: float = 3.60
    pedestrian_route_width_m: float = 1.20

    door_width_m: float = 0.90
    entrance_door_width_m: float = 1.20
    door_height_m: float = 2.10
    window_height_m: float = 1.40
    window_sill_height_m: float = 0.90
    window_width_ratio: float = 0.40


@dataclass
class RoomProgramEntry:
    """
    One requested room, its relative area weight, and an optional area cap.

    The cap keeps service rooms realistic on a large floor plate: without it a
    purely proportional split gives a 20 m2 WC. Surplus area is redistributed to
    the uncapped rooms in the same column.
    """

    name: str
    usage: SpaceUsage
    weight: float
    max_area_m2: float | None = None


@dataclass
class BuildingLayoutResult:
    building_model: BuildingModel
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    overlaps: list[str] = field(default_factory=list)


class BuildingLayoutGenerator:
    """Turns a :class:`BuildingBrief` into geometry."""

    def __init__(self, defaults: LayoutDefaults | None = None) -> None:
        self._d = defaults or LayoutDefaults()

    # -- public API --------------------------------------------------------

    def generate(self, brief: BuildingBrief) -> BuildingLayoutResult:
        missing = brief.missing_critical_inputs()
        if missing:
            raise BuildingBriefIncompleteError(missing)

        assumptions: list[str] = []
        warnings: list[str] = []

        site = self._build_site(brief, assumptions)
        footprint = site.buildable_boundary
        if footprint.area <= 0.0:
            raise BuildingLayoutInfeasibleError(
                "Setbacks consume the entire plot; no buildable footprint remains.",
                details={"plot_area_m2": site.plot_area_m2},
            )

        storey_height = brief.storey_height_m or self._d.storey_height_m
        if brief.storey_height_m is None:
            assumptions.append(
                f"Storey height assumed {storey_height:.2f} m (not stated in the brief)."
            )

        residential_floors = brief.residential_floor_count or 0
        if brief.residential_floor_count is None and brief.has_piloti:
            residential_floors = 0
            warnings.append("No residential storey count was stated; only the parking storey was generated.")

        apartments_per_floor = brief.apartments_per_floor or 1
        if brief.apartments_per_floor is None and residential_floors:
            assumptions.append("One apartment per residential floor assumed (not stated in the brief).")

        core = self._core_layout(footprint)
        levels = self._level_schedule(brief, storey_height, residential_floors)

        floor_plans: list[FloorPlanDefinition] = []
        stair_levels: list[str] = []
        elevator_levels: list[str] = []

        for level_id, level_name, floor_type, elevation, height in levels:
            stair_levels.append(level_id)
            if brief.requires_elevator:
                elevator_levels.append(level_id)
            if floor_type in (FloorType.PARKING, FloorType.PILOTI):
                plan = self._build_parking_floor(
                    level_id=level_id,
                    level_name=level_name,
                    elevation=elevation,
                    storey_height=height,
                    footprint=footprint,
                    core=core,
                    brief=brief,
                    assumptions=assumptions,
                    warnings=warnings,
                )
            elif floor_type is FloorType.ROOF:
                plan = self._build_roof_floor(
                    level_id=level_id,
                    level_name=level_name,
                    elevation=elevation,
                    storey_height=height,
                    footprint=footprint,
                    core=core,
                )
            else:
                plan = self._build_residential_floor(
                    level_id=level_id,
                    level_name=level_name,
                    elevation=elevation,
                    storey_height=height,
                    footprint=footprint,
                    core=core,
                    brief=brief,
                    apartments_per_floor=apartments_per_floor,
                    assumptions=assumptions,
                    warnings=warnings,
                )
            plan.walls = self._build_walls(plan, height)
            plan.doors = self._build_doors(plan)
            plan.windows = self._build_windows(plan)
            floor_plans.append(plan)

        stair = StairDefinition(
            id="STAIR-1",
            name="Main stair",
            boundary=core.stair_boundary,
            served_level_ids=stair_levels,
            riser_count_per_storey=max(2, int(round(storey_height / self._d.riser_height_m))),
            riser_height_m=round(storey_height / max(2, int(round(storey_height / self._d.riser_height_m))), 4),
            tread_depth_m=self._d.tread_depth_m,
            clear_width_m=self._d.stair_clear_width_m,
        )
        elevators: list[ElevatorDefinition] = []
        if brief.requires_elevator and core.elevator_boundary is not None:
            elevators.append(
                ElevatorDefinition(
                    id="ELEV-1",
                    boundary=core.elevator_boundary,
                    served_level_ids=elevator_levels,
                )
            )

        core_definition = CoreDefinition(
            id="CORE-1",
            boundary=core.boundary,
            stair_id=stair.id,
            elevator_id=elevators[0].id if elevators else None,
            shaft_space_ids=[
                space.id
                for plan in floor_plans
                for space in plan.spaces
                if space.usage is SpaceUsage.SHAFT
            ],
            served_level_ids=stair_levels,
        )

        system = brief.structural_system
        if system is StructuralSystem.UNDETERMINED:
            system = StructuralSystem.RC_MOMENT_FRAME
            assumptions.append(
                "Structural system selected as a reinforced-concrete moment frame with RC slabs "
                "(no system stated in the brief)."
            )

        model = BuildingModel(
            site=site,
            floor_plans=floor_plans,
            stairs=[stair],
            elevators=elevators,
            cores=[core_definition],
            structural_system=system,
            generated_by="BuildingLayoutGenerator",
            generation_assumptions=assumptions,
            metadata={
                "apartments_per_floor": apartments_per_floor,
                "residential_floor_count": residential_floors,
                "storey_height_m": storey_height,
                "brief_language": brief.language.value,
            },
        )

        overlaps = self.detect_overlaps(model)
        return BuildingLayoutResult(
            building_model=model,
            assumptions=assumptions,
            warnings=warnings,
            overlaps=overlaps,
        )

    def detect_overlaps(self, model: BuildingModel, *, tolerance_m2: float = 1e-3) -> list[str]:
        """Pairwise overlap check between every space and parking bay on each storey."""
        problems: list[str] = []
        for plan in model.floor_plans:
            items: list[tuple[str, Polygon2D]] = [
                (f"{space.name} ({space.id})", space.boundary) for space in plan.spaces
            ]
            items.extend((f"{slot.label} ({slot.id})", slot.boundary) for slot in plan.parking_spaces)
            for index, (left_name, left) in enumerate(items):
                for right_name, right in items[index + 1 :]:
                    overlap = left.overlap_area_with(right)
                    if overlap > tolerance_m2:
                        problems.append(
                            f"{plan.name}: '{left_name}' overlaps '{right_name}' by {overlap:.3f} m2"
                        )
        return problems

    # -- site and levels ---------------------------------------------------

    def _build_site(self, brief: BuildingBrief, assumptions: list[str]) -> SiteDefinition:
        length = brief.plot_length_m or 0.0
        width = brief.plot_width_m or 0.0

        # The frontage dimension runs along +x. If the brief names a frontage that
        # matches the second dimension, swap so the plot is oriented correctly.
        if brief.frontage_m is not None:
            if math.isclose(brief.frontage_m, width, abs_tol=0.05) and not math.isclose(
                brief.frontage_m, length, abs_tol=0.05
            ):
                length, width = width, length
            elif not math.isclose(brief.frontage_m, length, abs_tol=0.05):
                assumptions.append(
                    f"Stated frontage {brief.frontage_m:.2f} m does not match either plot dimension; "
                    f"the {length:.2f} m dimension was treated as the frontage."
                )
        frontage = brief.frontage_m if brief.frontage_m is not None else length
        if brief.frontage_m is None:
            assumptions.append(
                f"Frontage assumed to be the {length:.2f} m plot dimension (not stated in the brief)."
            )

        front = brief.setback_front_m
        rear = brief.setback_rear_m
        side = brief.setback_side_m
        if front is None and rear is None and side is None:
            assumptions.append(
                "No setbacks were stated, so the full plot is treated as buildable. "
                "Confirm setbacks with the authority having jurisdiction before use."
            )

        return SiteDefinition(
            id="SITE-1",
            name="Plot",
            boundary=rectangle(0.0, 0.0, length, width),
            frontage_m=frontage,
            depth_m=width,
            setback_front_m=front or 0.0,
            setback_rear_m=rear or 0.0,
            setback_left_m=side or 0.0,
            setback_right_m=side or 0.0,
            metadata={"frontage_edge": "y=0 (+x along frontage)"},
        )

    def _level_schedule(
        self,
        brief: BuildingBrief,
        storey_height: float,
        residential_floors: int,
    ) -> list[tuple[str, str, FloorType, float, float]]:
        """``(level_id, name, floor_type, elevation, storey_height)`` from grade up."""
        schedule: list[tuple[str, str, FloorType, float, float]] = []
        elevation = 0.0
        index = 0
        if brief.has_piloti:
            height = self._d.parking_storey_height_m
            schedule.append((f"L{index}", "Piloti / parking", FloorType.PILOTI, elevation, height))
            elevation += height
            index += 1
        for floor_number in range(1, residential_floors + 1):
            schedule.append(
                (
                    f"L{index}",
                    f"Residential floor {floor_number}",
                    FloorType.RESIDENTIAL,
                    elevation,
                    storey_height,
                )
            )
            elevation += storey_height
            index += 1
        schedule.append((f"L{index}", "Roof", FloorType.ROOF, elevation, 0.0))
        return schedule

    # -- core --------------------------------------------------------------

    @dataclass(frozen=True)
    class _CoreLayout:
        boundary: Polygon2D
        stair_boundary: Polygon2D
        elevator_boundary: Polygon2D | None
        shaft_boundary: Polygon2D | None
        band_y0: float
        band_y1: float
        spine_x0: float
        spine_x1: float

    def _core_layout(self, footprint: Polygon2D) -> _CoreLayout:
        min_x, min_y, max_x, max_y = footprint.bounds
        width = max_x - min_x
        depth = max_y - min_y

        band_depth = min(self._d.stair_depth_m, max(2.5, depth * 0.3))
        band_y1 = max_y
        band_y0 = max_y - band_depth

        # The corridor spine is centred on the footprint and the stair is aligned to
        # it so that circulation is continuous from the stair into every storey.
        spine_width = self._d.corridor_width_m
        spine_x0 = min_x + (width - spine_width) / 2.0
        spine_x1 = spine_x0 + spine_width

        stair_width = min(self._d.stair_width_m, width * 0.4)
        stair_x0 = max(min_x, min(spine_x0 - (stair_width - spine_width) / 2.0, max_x - stair_width))
        stair = rectangle(stair_x0, band_y0, stair_width, band_depth)

        elevator: Polygon2D | None = None
        shaft: Polygon2D | None = None
        remaining_right = max_x - (stair_x0 + stair_width)
        if remaining_right >= self._d.elevator_width_m:
            elevator = rectangle(
                stair_x0 + stair_width,
                band_y0,
                self._d.elevator_width_m,
                min(self._d.elevator_depth_m, band_depth),
            )
            if remaining_right >= self._d.elevator_width_m + self._d.shaft_width_m:
                shaft = rectangle(
                    stair_x0 + stair_width + self._d.elevator_width_m,
                    band_y0,
                    self._d.shaft_width_m,
                    min(self._d.shaft_depth_m, band_depth),
                )

        return self._CoreLayout(
            boundary=rectangle(min_x, band_y0, width, band_depth),
            stair_boundary=stair,
            elevator_boundary=elevator,
            shaft_boundary=shaft,
            band_y0=band_y0,
            band_y1=band_y1,
            spine_x0=spine_x0,
            spine_x1=spine_x1,
        )

    def _core_spaces(
        self,
        core: _CoreLayout,
        level_id: str,
        *,
        include_elevator: bool,
    ) -> list[SpaceDefinition]:
        spaces = [
            SpaceDefinition(
                id=f"SPC-{level_id}-STAIR",
                name="Stair",
                usage=SpaceUsage.STAIR,
                boundary=core.stair_boundary,
                level_id=level_id,
                metadata={"vertical_element": True},
            )
        ]
        if include_elevator and core.elevator_boundary is not None:
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-ELEV",
                    name="Elevator",
                    usage=SpaceUsage.ELEVATOR,
                    boundary=core.elevator_boundary,
                    level_id=level_id,
                    metadata={"vertical_element": True},
                )
            )
        if core.shaft_boundary is not None:
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-SHAFT",
                    name="Service shaft",
                    usage=SpaceUsage.SHAFT,
                    boundary=core.shaft_boundary,
                    level_id=level_id,
                    metadata={"vertical_element": True},
                )
            )
        return spaces

    # -- residential storey ------------------------------------------------

    def _room_program(self, brief: BuildingBrief) -> list[RoomProgramEntry]:
        program: list[RoomProgramEntry] = []
        bedrooms = brief.bedrooms_per_apartment or 0
        for index in range(bedrooms):
            if index == 0:
                program.append(RoomProgramEntry("Master bedroom", SpaceUsage.MASTER_BEDROOM, 1.70))
            else:
                program.append(RoomProgramEntry(f"Bedroom {index + 1}", SpaceUsage.BEDROOM, 1.30))
        if brief.has_living_room or bedrooms:
            program.append(RoomProgramEntry("Living room", SpaceUsage.LIVING, 2.40))
        if brief.has_kitchen or bedrooms:
            program.append(RoomProgramEntry("Kitchen", SpaceUsage.KITCHEN, 1.30))
        bathrooms = brief.bathrooms_per_apartment or (1 if bedrooms else 0)
        for index in range(bathrooms):
            if index == 0:
                program.append(RoomProgramEntry("Bathroom", SpaceUsage.BATHROOM, 0.75, max_area_m2=7.0))
            else:
                program.append(RoomProgramEntry(f"WC {index}", SpaceUsage.WC, 0.50, max_area_m2=4.0))
        return program

    def _build_residential_floor(
        self,
        *,
        level_id: str,
        level_name: str,
        elevation: float,
        storey_height: float,
        footprint: Polygon2D,
        core: _CoreLayout,
        brief: BuildingBrief,
        apartments_per_floor: int,
        assumptions: list[str],
        warnings: list[str],
    ) -> FloorPlanDefinition:
        min_x, min_y, max_x, _ = footprint.bounds
        width = max_x - min_x
        usable_depth = core.band_y0 - min_y

        spaces = self._core_spaces(core, level_id, include_elevator=brief.requires_elevator)

        # Lobby fills whatever is left of the core band beside the stair/elevator.
        lobby_x0 = min_x
        lobby_width = core.stair_boundary.bounds[0] - min_x
        if lobby_width >= self._d.min_room_dimension_m:
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-LOBBY",
                    name="Lift lobby",
                    usage=SpaceUsage.LOBBY,
                    boundary=rectangle(lobby_x0, core.band_y0, lobby_width, core.band_y1 - core.band_y0),
                    level_id=level_id,
                )
            )

        if usable_depth < self._d.min_room_band_depth_m:
            raise BuildingLayoutInfeasibleError(
                "Footprint is too shallow to fit the circulation core and any habitable rooms.",
                details={"usable_depth_m": round(usable_depth, 3)},
            )

        # Corridor spine: full usable depth, aligned with the stair.
        spine_width = core.spine_x1 - core.spine_x0
        spaces.append(
            SpaceDefinition(
                id=f"SPC-{level_id}-CORR",
                name="Corridor",
                usage=SpaceUsage.CORRIDOR,
                boundary=rectangle(core.spine_x0, min_y, spine_width, usable_depth),
                level_id=level_id,
                metadata={"circulation_spine": True},
            )
        )

        left_width = core.spine_x0 - min_x
        right_width = max_x - core.spine_x1
        if min(left_width, right_width) < self._d.min_room_dimension_m:
            raise BuildingLayoutInfeasibleError(
                "Footprint is too narrow for a central corridor with rooms on both sides.",
                details={"width_m": round(width, 3)},
            )

        program = self._room_program(brief)
        if not program:
            warnings.append(f"{level_name}: no room program was derived from the brief.")
            program = [RoomProgramEntry("Open area", SpaceUsage.OTHER, 1.0)]

        if apartments_per_floor > 1:
            warnings.append(
                f"{level_name}: {apartments_per_floor} apartments per floor were requested; the first "
                "version lays out a single unit per floor and records the remainder as unresolved."
            )

        left_program, right_program = self._split_program(program)
        apartment_space_ids: list[str] = []
        for column_program, column_x0, column_width in (
            (left_program, min_x, left_width),
            (right_program, core.spine_x1, right_width),
        ):
            column_spaces = self._stack_column(
                program=column_program,
                level_id=level_id,
                origin_x=column_x0,
                origin_y=min_y,
                width=column_width,
                depth=usable_depth,
            )
            spaces.extend(column_spaces)
            apartment_space_ids.extend(space.id for space in column_spaces)

        apartment = ApartmentDefinition(
            id=f"APT-{level_id}-1",
            name=f"Apartment {level_name}",
            level_id=level_id,
            space_ids=apartment_space_ids,
            bedroom_count=brief.bedrooms_per_apartment or 0,
            bathroom_count=brief.bathrooms_per_apartment or 0,
        )

        for space in spaces:
            if space.id in apartment_space_ids:
                space.apartment_id = apartment.id

        return FloorPlanDefinition(
            id=f"FLR-{level_id}",
            name=level_name,
            level_id=level_id,
            floor_type=FloorType.RESIDENTIAL,
            elevation_m=elevation,
            storey_height_m=storey_height,
            boundary=footprint,
            spaces=spaces,
            apartments=[apartment],
            metadata={"apartments_requested": apartments_per_floor},
        )

    @staticmethod
    def _split_program(
        program: list[RoomProgramEntry],
    ) -> tuple[list[RoomProgramEntry], list[RoomProgramEntry]]:
        """Greedy balance of area weight between the two corridor-side columns."""
        left: list[RoomProgramEntry] = []
        right: list[RoomProgramEntry] = []
        left_weight = 0.0
        right_weight = 0.0
        for entry in sorted(program, key=lambda item: item.weight, reverse=True):
            if left_weight <= right_weight:
                left.append(entry)
                left_weight += entry.weight
            else:
                right.append(entry)
                right_weight += entry.weight
        return left, right

    def _stack_column(
        self,
        *,
        program: list[RoomProgramEntry],
        level_id: str,
        origin_x: float,
        origin_y: float,
        width: float,
        depth: float,
    ) -> list[SpaceDefinition]:
        """Stack rooms along +y, dividing the depth in proportion to area weight."""
        if not program:
            return []
        depths = self._allocate_depths(
            weights=[entry.weight for entry in program],
            maximum_depths=[
                (entry.max_area_m2 / width) if (entry.max_area_m2 and width > 0) else None
                for entry in program
            ],
            total_depth=depth,
            minimum=min(self._d.min_room_band_depth_m, depth / len(program)),
        )
        spaces: list[SpaceDefinition] = []
        cursor = origin_y
        for entry, band_depth in zip(program, depths, strict=True):
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-{_slug(entry.name)}",
                    name=entry.name,
                    usage=entry.usage,
                    boundary=rectangle(origin_x, cursor, width, band_depth),
                    level_id=level_id,
                )
            )
            cursor += band_depth
        return spaces

    @staticmethod
    def _allocate_depths(
        *,
        weights: list[float],
        maximum_depths: list[float | None],
        total_depth: float,
        minimum: float,
    ) -> list[float]:
        """
        Split ``total_depth`` proportionally to ``weights``, honouring a minimum band
        depth and per-room maxima. Rooms that hit their cap are frozen and their
        surplus is redistributed to the rest, repeating until nothing else clamps.

        The returned depths always sum to ``total_depth`` exactly, so stacked rooms
        neither overlap nor leave a gap.
        """
        count = len(weights)
        if count == 0:
            return []

        floor_depth = min(minimum, total_depth / count)
        depths = [floor_depth] * count
        frozen = [False] * count

        for _ in range(count + 1):
            remaining = total_depth - sum(depths[i] for i in range(count) if frozen[i])
            open_indices = [i for i in range(count) if not frozen[i]]
            if not open_indices or remaining <= 0:
                break
            open_floor = min(floor_depth, remaining / len(open_indices))
            slack = remaining - open_floor * len(open_indices)
            weight_total = sum(weights[i] for i in open_indices) or float(len(open_indices))
            clamped_any = False
            for index in open_indices:
                depths[index] = open_floor + slack * (weights[index] / weight_total)
                cap = maximum_depths[index]
                if cap is not None and depths[index] > cap > 0:
                    depths[index] = max(cap, open_floor)
                    frozen[index] = True
                    clamped_any = True
            if not clamped_any:
                break

        # Absorb residue (including the case where every room was capped) into the
        # largest uncapped room, or the last room if all are capped.
        residue = total_depth - sum(depths)
        if abs(residue) > 1e-12:
            open_indices = [i for i in range(count) if not frozen[i]]
            target = max(open_indices, key=lambda i: depths[i]) if open_indices else count - 1
            depths[target] += residue
        return depths

    # -- parking storey ----------------------------------------------------

    def _build_parking_floor(
        self,
        *,
        level_id: str,
        level_name: str,
        elevation: float,
        storey_height: float,
        footprint: Polygon2D,
        core: _CoreLayout,
        brief: BuildingBrief,
        assumptions: list[str],
        warnings: list[str],
    ) -> FloorPlanDefinition:
        min_x, min_y, max_x, _ = footprint.bounds
        width = max_x - min_x
        usable_depth = core.band_y0 - min_y

        spaces = self._core_spaces(core, level_id, include_elevator=brief.requires_elevator)
        lobby_width = core.stair_boundary.bounds[0] - min_x
        if lobby_width >= self._d.min_room_dimension_m:
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-LOBBY",
                    name="Entrance lobby",
                    usage=SpaceUsage.ENTRANCE,
                    boundary=rectangle(min_x, core.band_y0, lobby_width, core.band_y1 - core.band_y0),
                    level_id=level_id,
                )
            )

        requested = brief.parking_space_count or 0
        bays_per_row = max(1, int((width) // self._d.parking_bay_width_m))
        row_count = max(1, math.ceil(requested / bays_per_row)) if requested else 0

        aisle_depth = self._d.parking_aisle_width_m
        bay_length = self._d.parking_bay_length_m
        required_depth = row_count * bay_length + (aisle_depth if row_count else 0.0)

        parking_spaces: list[ParkingSpaceDefinition] = []
        if row_count and required_depth > usable_depth + 1e-9:
            warnings.append(
                f"{level_name}: {requested} bays need {required_depth:.2f} m of depth but only "
                f"{usable_depth:.2f} m is available; the layout was reduced to what fits."
            )
            row_count = max(0, int((usable_depth - aisle_depth) // bay_length))

        if row_count:
            # Drive aisle sits at the street edge (y = min_y) so vehicles enter directly.
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-AISLE",
                    name="Drive aisle",
                    usage=SpaceUsage.DRIVE_AISLE,
                    boundary=rectangle(min_x, min_y, width, aisle_depth),
                    level_id=level_id,
                    metadata={"serves": "parking bays", "entry_edge": "y=0"},
                )
            )

            placed = 0
            bay_width = self._d.parking_bay_width_m
            row_bay_total = min(bays_per_row, max(1, requested)) if requested else 0
            bays_span = row_bay_total * bay_width
            # Keep the leftover width as a continuous pedestrian route to the core
            # rather than two unusable slivers.
            bay_origin_x = min_x
            for row_index in range(row_count):
                row_y0 = min_y + aisle_depth + row_index * bay_length
                for bay_index in range(row_bay_total):
                    if requested and placed >= requested:
                        break
                    placed += 1
                    parking_spaces.append(
                        ParkingSpaceDefinition(
                            id=f"PRK-{level_id}-{placed}",
                            label=f"P{placed}",
                            boundary=rectangle(
                                bay_origin_x + bay_index * bay_width, row_y0, bay_width, bay_length
                            ),
                            level_id=level_id,
                            angle_deg=90.0,
                            metadata={"access": "90-degree bay served from the drive aisle"},
                        )
                    )
                if requested and placed >= requested:
                    break

            route_x0 = bay_origin_x + bays_span
            route_width = max_x - route_x0
            route_depth = (
                min_y + aisle_depth + row_count * bay_length - (min_y + aisle_depth)
            )
            if route_width >= self._d.pedestrian_route_width_m:
                spaces.append(
                    SpaceDefinition(
                        id=f"SPC-{level_id}-WALK",
                        name="Pedestrian route",
                        usage=SpaceUsage.CORRIDOR,
                        boundary=rectangle(route_x0, min_y + aisle_depth, route_width, route_depth),
                        level_id=level_id,
                        metadata={"connects": "drive aisle to circulation core"},
                    )
                )
            else:
                warnings.append(
                    f"{level_name}: no pedestrian route wider than "
                    f"{self._d.pedestrian_route_width_m:.2f} m remains beside the parking bays."
                )

            rear_y0 = min_y + aisle_depth + row_count * bay_length
            rear_depth = core.band_y0 - rear_y0
            if rear_depth >= self._d.min_room_dimension_m:
                spaces.append(
                    SpaceDefinition(
                        id=f"SPC-{level_id}-PLOBBY",
                        name="Parking circulation",
                        usage=SpaceUsage.CORRIDOR,
                        boundary=rectangle(min_x, rear_y0, width, rear_depth),
                        level_id=level_id,
                        metadata={"connects": "parking bays to circulation core"},
                    )
                )
        else:
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-OPEN",
                    name="Open piloti",
                    usage=SpaceUsage.OTHER,
                    boundary=rectangle(min_x, min_y, width, usable_depth),
                    level_id=level_id,
                )
            )

        if requested and len(parking_spaces) < requested:
            warnings.append(
                f"{level_name}: {len(parking_spaces)} of {requested} requested parking bays were placed."
            )

        assumptions.append(
            f"Parking bays sized {self._d.parking_bay_width_m:.2f} m x "
            f"{self._d.parking_bay_length_m:.2f} m with a {self._d.parking_aisle_width_m:.2f} m "
            "drive aisle (90-degree bays). Confirm against local parking standards."
        )
        assumptions.append("Parking storey assumed to be at grade, so no vehicle ramp was generated.")

        return FloorPlanDefinition(
            id=f"FLR-{level_id}",
            name=level_name,
            level_id=level_id,
            floor_type=FloorType.PILOTI,
            elevation_m=elevation,
            storey_height_m=storey_height,
            boundary=footprint,
            spaces=spaces,
            parking_spaces=parking_spaces,
            metadata={"parking_requested": requested, "parking_placed": len(parking_spaces)},
        )

    def _build_roof_floor(
        self,
        *,
        level_id: str,
        level_name: str,
        elevation: float,
        storey_height: float,
        footprint: Polygon2D,
        core: _CoreLayout,
    ) -> FloorPlanDefinition:
        min_x, min_y, max_x, _ = footprint.bounds
        width = max_x - min_x
        spaces = [
            SpaceDefinition(
                id=f"SPC-{level_id}-ROOF",
                name="Roof",
                usage=SpaceUsage.ROOF,
                boundary=rectangle(min_x, min_y, width, core.band_y0 - min_y),
                level_id=level_id,
            ),
            SpaceDefinition(
                id=f"SPC-{level_id}-STAIR",
                name="Stair bulkhead",
                usage=SpaceUsage.STAIR,
                boundary=core.stair_boundary,
                level_id=level_id,
                metadata={"vertical_element": True},
            ),
        ]
        lobby_width = core.stair_boundary.bounds[0] - min_x
        if lobby_width >= self._d.min_room_dimension_m:
            spaces.append(
                SpaceDefinition(
                    id=f"SPC-{level_id}-ROOFDECK",
                    name="Roof deck",
                    usage=SpaceUsage.ROOF,
                    boundary=rectangle(min_x, core.band_y0, lobby_width, core.band_y1 - core.band_y0),
                    level_id=level_id,
                )
            )
        return FloorPlanDefinition(
            id=f"FLR-{level_id}",
            name=level_name,
            level_id=level_id,
            floor_type=FloorType.ROOF,
            elevation_m=elevation,
            storey_height_m=storey_height,
            boundary=footprint,
            spaces=spaces,
        )

    # -- walls, doors, windows ---------------------------------------------

    def _build_walls(self, plan: FloorPlanDefinition, height: float) -> list[WallDefinition]:
        """
        Exterior walls follow the footprint. Interior walls are the space edges that
        are not on the perimeter, de-duplicated so a shared partition is stored once.
        """
        walls: list[WallDefinition] = []
        min_x, min_y, max_x, max_y = plan.boundary.bounds
        wall_height = height if height > 0 else plan.storey_height_m

        perimeter = plan.boundary.points
        for index in range(len(perimeter)):
            start = perimeter[index]
            end = perimeter[(index + 1) % len(perimeter)]
            walls.append(
                WallDefinition(
                    id=f"WAL-{plan.level_id}-EXT{index + 1}",
                    start=start,
                    end=end,
                    thickness_m=self._d.exterior_wall_thickness_m,
                    wall_type=WallType.EXTERIOR,
                    level_id=plan.level_id,
                    height_m=wall_height,
                    is_load_bearing=False,
                    metadata={"generated_from": "floor boundary"},
                )
            )

        seen: set[tuple[float, float, float, float]] = set()
        for space in plan.spaces:
            points = space.boundary.points
            is_core = bool(space.metadata.get("vertical_element"))
            for index in range(len(points)):
                start = points[index]
                end = points[(index + 1) % len(points)]
                if _on_perimeter(start, end, min_x, min_y, max_x, max_y):
                    continue
                key = _edge_key(start, end)
                if key in seen:
                    continue
                seen.add(key)
                walls.append(
                    WallDefinition(
                        id=f"WAL-{plan.level_id}-INT{len(seen)}",
                        start=start,
                        end=end,
                        thickness_m=(
                            self._d.core_wall_thickness_m if is_core else self._d.interior_wall_thickness_m
                        ),
                        wall_type=WallType.CORE if is_core else WallType.INTERIOR,
                        level_id=plan.level_id,
                        height_m=wall_height,
                        metadata={"generated_from": f"edge of {space.name}"},
                    )
                )
        return walls

    def _build_doors(self, plan: FloorPlanDefinition) -> list[DoorDefinition]:
        """One door per space on the edge it shares with circulation."""
        circulation = [
            space
            for space in plan.spaces
            if space.usage
            in (SpaceUsage.CORRIDOR, SpaceUsage.LOBBY, SpaceUsage.ENTRANCE, SpaceUsage.DRIVE_AISLE)
        ]
        doors: list[DoorDefinition] = []
        counter = 0
        for space in plan.spaces:
            if space.usage in (
                SpaceUsage.CORRIDOR,
                SpaceUsage.LOBBY,
                SpaceUsage.ENTRANCE,
                SpaceUsage.DRIVE_AISLE,
                SpaceUsage.SHAFT,
                SpaceUsage.ROOF,
            ):
                continue
            for corridor in circulation:
                shared = _shared_edge(space.boundary, corridor.boundary)
                if shared is None:
                    continue
                counter += 1
                doors.append(
                    DoorDefinition(
                        id=f"DOR-{plan.level_id}-{counter}",
                        center=shared.midpoint,
                        width_m=self._d.door_width_m,
                        height_m=self._d.door_height_m,
                        level_id=plan.level_id,
                        connects_space_ids=[space.id, corridor.id],
                        # The axis and extent let the structural coordination pass
                        # slide the opening along the same wall if a column lands on it.
                        metadata={
                            "edge_axis": shared.axis,
                            "edge_low": shared.low,
                            "edge_high": shared.high,
                        },
                    )
                )
                break
        # Building entrance on the street edge of the lowest circulation space.
        min_x, min_y, max_x, _ = plan.boundary.bounds
        for space in circulation:
            s_min_x, s_min_y, s_max_x, _ = space.boundary.bounds
            if abs(s_min_y - min_y) < 1e-6:
                counter += 1
                doors.append(
                    DoorDefinition(
                        id=f"DOR-{plan.level_id}-ENTRY",
                        center=Point2D(x=(s_min_x + s_max_x) / 2.0, y=min_y),
                        width_m=self._d.entrance_door_width_m,
                        height_m=self._d.door_height_m,
                        level_id=plan.level_id,
                        connects_space_ids=[space.id],
                        is_entrance=True,
                        metadata={"edge_axis": "x", "edge_low": s_min_x, "edge_high": s_max_x},
                    )
                )
                break
        return doors

    def _build_windows(self, plan: FloorPlanDefinition) -> list[WindowDefinition]:
        """A window on each perimeter edge of every habitable room."""
        min_x, min_y, max_x, max_y = plan.boundary.bounds
        windows: list[WindowDefinition] = []
        counter = 0
        habitable = {
            SpaceUsage.BEDROOM,
            SpaceUsage.MASTER_BEDROOM,
            SpaceUsage.LIVING,
            SpaceUsage.KITCHEN,
            SpaceUsage.BATHROOM,
        }
        for space in plan.spaces:
            if space.usage not in habitable:
                continue
            points = space.boundary.points
            for index in range(len(points)):
                start = points[index]
                end = points[(index + 1) % len(points)]
                if not _on_perimeter(start, end, min_x, min_y, max_x, max_y):
                    continue
                edge_length = start.distance_to(end)
                window_width = max(0.6, edge_length * self._d.window_width_ratio)
                counter += 1
                windows.append(
                    WindowDefinition(
                        id=f"WIN-{plan.level_id}-{counter}",
                        center=Point2D(x=(start.x + end.x) / 2.0, y=(start.y + end.y) / 2.0),
                        width_m=round(window_width, 3),
                        height_m=self._d.window_height_m,
                        sill_height_m=self._d.window_sill_height_m,
                        level_id=plan.level_id,
                        space_id=space.id,
                    )
                )
        return windows


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def _slug(name: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in name).strip("-").upper()


def _edge_key(start: Point2D, end: Point2D) -> tuple[float, float, float, float]:
    a = (round(start.x, 4), round(start.y, 4))
    b = (round(end.x, 4), round(end.y, 4))
    first, second = sorted((a, b))
    return (first[0], first[1], second[0], second[1])


def _on_perimeter(
    start: Point2D,
    end: Point2D,
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    tolerance: float = 1e-6,
) -> bool:
    if abs(start.x - end.x) < tolerance and (
        abs(start.x - min_x) < tolerance or abs(start.x - max_x) < tolerance
    ):
        return True
    return abs(start.y - end.y) < tolerance and (
        abs(start.y - min_y) < tolerance or abs(start.y - max_y) < tolerance
    )


@dataclass(frozen=True)
class SharedEdge:
    """Contact segment between two axis-aligned rectangles."""

    midpoint: Point2D
    axis: str
    """``"x"`` when the opening slides horizontally, ``"y"`` when it slides vertically."""
    low: float
    high: float


def _shared_edge(
    first: Polygon2D,
    second: Polygon2D,
    *,
    tolerance: float = 1e-6,
    minimum_overlap: float = 0.9,
) -> SharedEdge | None:
    """
    Collinear contact segment between two axis-aligned rectangles, or ``None`` when
    they do not touch over at least ``minimum_overlap`` metres.
    """
    a_min_x, a_min_y, a_max_x, a_max_y = first.bounds
    b_min_x, b_min_y, b_max_x, b_max_y = second.bounds

    for a_edge_x, b_edge_x in ((a_max_x, b_min_x), (a_min_x, b_max_x)):
        if abs(a_edge_x - b_edge_x) < tolerance:
            low = max(a_min_y, b_min_y)
            high = min(a_max_y, b_max_y)
            if high - low >= minimum_overlap:
                return SharedEdge(
                    midpoint=Point2D(x=a_edge_x, y=(low + high) / 2.0),
                    axis="y",
                    low=low,
                    high=high,
                )

    for a_edge_y, b_edge_y in ((a_max_y, b_min_y), (a_min_y, b_max_y)):
        if abs(a_edge_y - b_edge_y) < tolerance:
            low = max(a_min_x, b_min_x)
            high = min(a_max_x, b_max_x)
            if high - low >= minimum_overlap:
                return SharedEdge(
                    midpoint=Point2D(x=(low + high) / 2.0, y=a_edge_y),
                    axis="x",
                    low=low,
                    high=high,
                )
    return None
