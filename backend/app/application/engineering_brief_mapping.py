"""Map a structured engineering brief onto the current PEM.

Only fields the PEM can store are written. A brief note without a number does
not become a load, a material strength, or a foundation size. An existing
member model is not replaced.
"""

from __future__ import annotations

from typing import Any

from app.domain.models.pem import (
    CodeConfigurationStatus,
    ProjectEngineeringModel,
    UnitConfiguration,
    UnitConfigurationStatus,
    UnitSystem,
)
from app.domain.models.pem_structural import (
    ConcreteMaterial,
    FoundationSection,
    GridDefinition,
    InputOrigin,
    InputProvenance,
    LevelDefinition,
    LoadCase,
    LoadCategory,
    LoadDefinition,
    LoadDistribution,
    SteelMaterial,
    new_structural_id,
)

_BRIEF_ORIGINS = frozenset(
    {"USER_PROVIDED", "ASSUMED", "DERIVED", "CALCULATED", "UNAVAILABLE"}
)


def normalize_engineering_brief(parameters: dict[str, Any] | None, fields: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    """Classify each brief field. A blank value is UNAVAILABLE."""
    raw = parameters.get("engineering_brief") if isinstance(parameters, dict) else None
    source = raw if isinstance(raw, dict) else {}
    recorded: list[dict[str, Any]] = []
    for key, label in fields:
        value, origin = _value_and_origin(source.get(key))
        if _blank(value):
            recorded.append({"field": key, "label": label, "value": None, "origin": "UNAVAILABLE"})
            continue
        if origin not in _BRIEF_ORIGINS or origin == "UNAVAILABLE":
            origin = "USER_PROVIDED"
        recorded.append({"field": key, "label": label, "value": value, "origin": origin})
    unavailable = [item["label"] for item in recorded if item["origin"] == "UNAVAILABLE"]
    return {
        "fields": recorded,
        "values": {
            item["field"]: item["value"] for item in recorded if item["origin"] != "UNAVAILABLE"
        },
        "unavailable": unavailable,
    }


def map_brief_onto_pem(
    pem: ProjectEngineeringModel,
    brief: dict[str, Any],
) -> tuple[ProjectEngineeringModel, list[dict[str, Any]]]:
    """Return a PEM copy and one record per brief field that was considered."""
    updated = pem.model_copy(deep=True)
    members_exist = len(updated.structural_model.members.members) > 0
    by_field = {item["field"]: item for item in brief.get("fields", [])}
    records: list[dict[str, Any]] = []

    records.append(_map_stories(updated, by_field, members_exist))
    records.append(_map_grid(updated, by_field, members_exist))
    records.append(_map_structural_system(updated, by_field))
    records.append(_map_material(updated, by_field, members_exist))
    records.append(_map_member_assumptions(updated, by_field))
    records.append(_map_loads(updated, by_field, members_exist))
    records.append(_map_design_code(updated, by_field))
    records.append(_map_units(updated, by_field, members_exist))
    records.append(_map_text_only(updated, by_field, "seismic_assumptions", "seismic load"))
    records.append(_map_text_only(updated, by_field, "wind_assumptions", "wind load"))
    records.append(_map_foundation(updated, by_field, members_exist))
    for key in (
        "project_type",
        "location",
        "engineer_notes",
        "plot_length_m",
        "plot_width_m",
        "frontage_m",
        "residential_floor_count",
        "parking_space_count",
        "apartments_per_floor",
        "bedrooms_per_apartment",
        "has_piloti",
    ):
        records.append(_record_requirement(updated, by_field, key))
    updated.requirements = {
        **updated.requirements,
        "engineering_brief": brief.get("fields", []),
    }
    return updated, [item for item in records if item is not None]


def mapping_changes_pem(records: list[dict[str, Any]]) -> bool:
    return any(item.get("status") in {"MAPPED", "RECORDED"} for item in records)


def _map_stories(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    members_exist: bool,
) -> dict[str, Any]:
    stories = fields.get("number_of_stories") or _absent("number_of_stories")
    heights = fields.get("story_heights") or _absent("story_heights")
    if stories["origin"] == "UNAVAILABLE" and heights["origin"] == "UNAVAILABLE":
        return _unavailable("number_of_stories", "Number of stories and story heights were not provided.")
    if members_exist or pem.structural_model.geometry.levels:
        _remember(pem, "number_of_stories", stories, "Existing levels were left unchanged.")
        _remember(pem, "story_heights", heights, "Existing levels were left unchanged.")
        return _preserved(
            "story_heights",
            "Story count and heights were not written over existing levels or members.",
        )
    height_values = _numbers(heights["value"]) if heights["origin"] != "UNAVAILABLE" else []
    count = _integer(stories["value"]) if stories["origin"] != "UNAVAILABLE" else None
    if not height_values:
        _remember(
            pem,
            "number_of_stories",
            stories,
            "Levels were not created because story heights were not provided.",
        )
        return _unavailable(
            "story_heights",
            "Story heights were not provided, so no levels were created.",
        )
    if count is not None and count != len(height_values):
        _remember(pem, "story_heights", heights, "Heights were not applied because the story count does not match.")
        return _unavailable(
            "story_heights",
            "Story count and story heights do not describe the same number of stories.",
        )
    elevation = 0.0
    for index, height in enumerate(height_values, start=1):
        elevation += height
        pem.structural_model.geometry.levels.append(
            LevelDefinition(
                id=new_structural_id("level"),
                name=f"Level {index}",
                elevation=round(elevation, 4),
                sort_order=index,
                metadata={"origin": heights["origin"], "story_height": height},
            )
        )
    _remember(pem, "story_heights", heights, "Levels created from the brief story heights.")
    _remember(pem, "number_of_stories", stories, "Story count recorded with the created levels.")
    return {
        "field": "story_heights",
        "status": "MAPPED",
        "origin": heights["origin"],
        "reason": f"Created {len(height_values)} levels from the brief story heights.",
    }


def _map_grid(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    members_exist: bool,
) -> dict[str, Any]:
    grid = fields.get("grid") or _absent("grid")
    spans = fields.get("spans") or _absent("spans")
    if grid["origin"] == "UNAVAILABLE" and spans["origin"] == "UNAVAILABLE":
        return _unavailable("spans", "Grid and spans were not provided.")
    if members_exist or pem.structural_model.geometry.grids:
        _remember(pem, "grid", grid, "Existing grids were left unchanged.")
        _remember(pem, "spans", spans, "Existing grids were left unchanged.")
        return _preserved("spans", "Grid and spans were not written over existing grids or members.")
    span_values = _numbers(spans["value"]) if spans["origin"] != "UNAVAILABLE" else []
    if not span_values:
        _remember(pem, "grid", grid, "A grid name without span lengths was not turned into grid geometry.")
        return _unavailable("spans", "Span lengths were not numeric, so no grid was created.")
    name = str(grid["value"]).strip() if grid["origin"] != "UNAVAILABLE" and grid["value"] else "Brief grid"
    pem.structural_model.geometry.grids.append(
        GridDefinition(
            id=new_structural_id("grid"),
            name=name,
            spacing_x=span_values[0],
            spacing_y=span_values[1] if len(span_values) > 1 else None,
            metadata={"origin": spans["origin"], "spans": span_values},
        )
    )
    _remember(pem, "spans", spans, "Grid created from the brief spans.")
    _remember(pem, "grid", grid, "Grid name recorded with the created grid.")
    return {
        "field": "spans",
        "status": "MAPPED",
        "origin": spans["origin"],
        "reason": "Created one grid from the brief spans.",
    }


def _map_structural_system(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    item = fields.get("structural_system") or _absent("structural_system")
    if item["origin"] == "UNAVAILABLE":
        return _unavailable("structural_system", "Structural system was not provided.")
    if pem.structural_system.get("system"):
        _remember(pem, "structural_system", item, "The current structural system label was left unchanged.")
        return _preserved("structural_system", "A structural system is already recorded on the PEM.")
    pem.structural_system = {
        **pem.structural_system,
        "system": item["value"],
        "origin": item["origin"],
    }
    _remember(pem, "structural_system", item, "Recorded on the PEM structural system.")
    return {
        "field": "structural_system",
        "status": "MAPPED",
        "origin": item["origin"],
        "reason": "Structural system was recorded on the PEM.",
    }


def _map_material(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    members_exist: bool,
) -> dict[str, Any]:
    item = fields.get("material") or _absent("material")
    if item["origin"] == "UNAVAILABLE":
        return _unavailable("material", "Material was not provided.")
    library = pem.structural_model.materials
    if members_exist or library.concrete or library.steel:
        _remember(pem, "material", item, "Existing materials were left unchanged.")
        return _preserved("material", "Existing materials were not replaced.")
    value = item["value"]
    if isinstance(value, dict) and _number(value.get("compressive_strength")) is not None:
        library.concrete.append(
            ConcreteMaterial(
                id=new_structural_id("concrete"),
                name=str(value.get("name") or "Brief concrete"),
                compressive_strength=float(value["compressive_strength"]),
                metadata={"origin": item["origin"]},
            )
        )
        return {"field": "material", "status": "MAPPED", "origin": item["origin"], "reason": "Concrete material recorded from the brief."}
    if isinstance(value, dict) and _number(value.get("yield_strength")) is not None:
        library.steel.append(
            SteelMaterial(
                id=new_structural_id("steel"),
                name=str(value.get("name") or "Brief steel"),
                yield_strength=float(value["yield_strength"]),
                metadata={"origin": item["origin"]},
            )
        )
        return {"field": "material", "status": "MAPPED", "origin": item["origin"], "reason": "Steel material recorded from the brief."}
    _remember(
        pem,
        "material",
        item,
        "A material name without a strength was not stored as a material record.",
    )
    return _unavailable("material", "Material strength was not provided, so no material record was created.")


def _map_member_assumptions(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    item = fields.get("member_assumptions") or _absent("member_assumptions")
    if item["origin"] == "UNAVAILABLE":
        return _unavailable("member_assumptions", "Member assumptions were not provided.")
    _remember(
        pem,
        "member_assumptions",
        item,
        "Recorded as provenance. No member section was created from this note.",
    )
    return {
        "field": "member_assumptions",
        "status": "RECORDED",
        "origin": item["origin"],
        "reason": "Member assumptions are provenance only. No section was invented.",
    }


def _map_loads(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    members_exist: bool,
) -> dict[str, Any]:
    item = fields.get("loads") or _absent("loads")
    if item["origin"] == "UNAVAILABLE":
        return _unavailable("loads", "Loads were not provided.")
    if members_exist or pem.structural_model.load_cases:
        _remember(pem, "loads", item, "Existing load cases were left unchanged.")
        return _preserved("loads", "Existing loads were not replaced.")
    value = item["value"]
    magnitude = _number(value.get("magnitude")) if isinstance(value, dict) else None
    unit = value.get("unit") if isinstance(value, dict) else None
    if magnitude is None or not isinstance(unit, str) or not unit.strip():
        _remember(pem, "loads", item, "Load text was not converted into a numeric load.")
        return _unavailable("loads", "No numeric load magnitude and unit were provided.")
    case_id = new_structural_id("case")
    pem.structural_model.load_cases.append(
        LoadCase(
            id=case_id,
            name=str(value.get("name") or "Brief load"),
            category=LoadCategory.OTHER,
            description="Mapped from the engineering brief.",
            loads=[
                LoadDefinition(
                    id=new_structural_id("load"),
                    name=str(value.get("name") or "Brief load"),
                    load_case_id=case_id,
                    category=LoadCategory.OTHER,
                    distribution=LoadDistribution.NODAL,
                    magnitude=magnitude,
                    unit=unit.strip(),
                    metadata={"origin": item["origin"]},
                )
            ],
            metadata={"origin": item["origin"]},
        )
    )
    return {"field": "loads", "status": "MAPPED", "origin": item["origin"], "reason": "One load case was created from the brief magnitude."}


def _map_design_code(pem: ProjectEngineeringModel, fields: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = fields.get("design_code") or _absent("design_code")
    if item["origin"] == "UNAVAILABLE":
        return _unavailable("design_code", "Design code was not provided.")
    text = str(item["value"]).upper()
    if "ACI" in text and "318" in text:
        pem.code_configuration.concrete_edition = "ACI CODE-318-25"
        pem.code_configuration.status = CodeConfigurationStatus.USER_CONFIRMED
        pem.code_configuration.metadata.source = item["origin"]
        pem.code_configuration.metadata.derivation = "Engineering brief design code"
        _remember(pem, "design_code", item, "Concrete edition set to ACI CODE-318-25.")
        return {"field": "design_code", "status": "MAPPED", "origin": item["origin"], "reason": "Concrete code set to ACI 318-25."}
    if "AISC" in text and "360" in text:
        pem.code_configuration.steel_edition = "AISC 360-22"
        pem.code_configuration.status = CodeConfigurationStatus.USER_CONFIRMED
        pem.code_configuration.metadata.source = item["origin"]
        pem.code_configuration.metadata.derivation = "Engineering brief design code"
        _remember(pem, "design_code", item, "Steel edition set to AISC 360-22.")
        return {"field": "design_code", "status": "MAPPED", "origin": item["origin"], "reason": "Steel code set to AISC 360-22."}
    _remember(pem, "design_code", item, "This code is not a configured standard in the PEM.")
    return _unavailable("design_code", f"'{item['value']}' is not a PEM code edition that this workflow can store.")


def _map_units(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    members_exist: bool,
) -> dict[str, Any]:
    item = fields.get("units") or _absent("units")
    if item["origin"] == "UNAVAILABLE":
        return _unavailable("units", "Units were not provided.")
    token = str(item["value"]).strip().upper().replace("-", "_").replace(" ", "_")
    if token in {"SI", "SI_METRIC", "METRIC"}:
        pem.unit_configuration = UnitConfiguration(
            system=UnitSystem.SI_METRIC,
            length_unit="m",
            force_unit="kN",
            moment_unit="kN·m",
            stress_unit="MPa",
            area_unit="m2",
            volume_unit="m3",
            configured_by="engineering_brief",
            status=UnitConfigurationStatus.USER_CONFIRMED,
        )
        note = "SI units recorded."
        if members_exist:
            note += " Existing member geometry numbers were not converted."
        _remember(pem, "units", item, note)
        return {"field": "units", "status": "MAPPED", "origin": item["origin"], "reason": note}
    if token in {"US", "US_CUSTOMARY", "IMPERIAL"}:
        pem.unit_configuration = UnitConfiguration(
            system=UnitSystem.US_CUSTOMARY,
            length_unit="ft",
            force_unit="kip",
            moment_unit="kip-ft",
            stress_unit="ksi",
            area_unit="in2",
            volume_unit="ft3",
            configured_by="engineering_brief",
            status=UnitConfigurationStatus.USER_CONFIRMED,
        )
        note = "US customary units recorded."
        if members_exist:
            note += " Existing member geometry numbers were not converted."
        _remember(pem, "units", item, note)
        return {"field": "units", "status": "MAPPED", "origin": item["origin"], "reason": note}
    _remember(pem, "units", item, "Unit system was not recognized.")
    return _unavailable("units", f"'{item['value']}' is not a supported unit system.")


def _map_text_only(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    key: str,
    load_name: str,
) -> dict[str, Any]:
    item = fields.get(key) or _absent(key)
    if item["origin"] == "UNAVAILABLE":
        return _unavailable(key, f"{key.replace('_', ' ')} were not provided.")
    _remember(pem, key, item, f"This note was not converted into a {load_name}.")
    return _unavailable(key, f"The PEM has no numeric {load_name} in this note, so none was created.")


def _map_foundation(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    members_exist: bool,
) -> dict[str, Any]:
    item = fields.get("foundation_assumptions") or _absent("foundation_assumptions")
    if item["origin"] == "UNAVAILABLE":
        return _unavailable("foundation_assumptions", "Foundation assumptions were not provided.")
    sections = pem.structural_model.sections.foundations
    if members_exist or sections or pem.structural_model.footings:
        _remember(pem, "foundation_assumptions", item, "Existing foundations were left unchanged.")
        return _preserved("foundation_assumptions", "Existing foundations were not replaced.")
    value = item["value"]
    foundation_type = value.get("foundation_type") if isinstance(value, dict) else None
    if not isinstance(foundation_type, str) or not foundation_type.strip():
        _remember(pem, "foundation_assumptions", item, "Foundation text was not converted into a foundation section.")
        return _unavailable(
            "foundation_assumptions",
            "No foundation type was provided, so no foundation section was created.",
        )
    sections.append(
        FoundationSection(
            id=new_structural_id("foundation"),
            name=str(value.get("name") or foundation_type),
            foundation_type=foundation_type.strip(),
            width=_number(value.get("width")),
            length=_number(value.get("length")),
            depth=_number(value.get("depth")),
            metadata={"origin": item["origin"]},
        )
    )
    return {
        "field": "foundation_assumptions",
        "status": "MAPPED",
        "origin": item["origin"],
        "reason": "Foundation section recorded from the brief.",
    }


def _record_requirement(
    pem: ProjectEngineeringModel,
    fields: dict[str, dict[str, Any]],
    key: str,
) -> dict[str, Any] | None:
    item = fields.get(key)
    if item is None or item["origin"] == "UNAVAILABLE":
        return None
    _remember(pem, key, item, "Stored with the brief. It did not change structural members.")
    return {
        "field": key,
        "status": "RECORDED",
        "origin": item["origin"],
        "reason": "Stored on the PEM brief record.",
    }


def _remember(pem: ProjectEngineeringModel, field: str, item: dict[str, Any], note: str) -> None:
    if item.get("origin") == "UNAVAILABLE" or item.get("value") is None:
        return
    pem.structural_model.input_provenance.append(
        InputProvenance(
            field=field,
            value=_provenance_value(item["value"]),
            origin=_input_origin(str(item["origin"])),
            note=note,
        )
    )


def _input_origin(origin: str) -> InputOrigin:
    try:
        return InputOrigin(origin)
    except ValueError:
        return InputOrigin.USER_PROVIDED


def _provenance_value(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in value.items())
    return str(value)


def _value_and_origin(entry: Any) -> tuple[Any, str]:
    if isinstance(entry, dict) and "origin" in entry:
        return entry.get("value"), str(entry.get("origin") or "UNAVAILABLE")
    if _blank(entry):
        return None, "UNAVAILABLE"
    return entry, "USER_PROVIDED"


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _numbers(value: Any) -> list[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    if isinstance(value, list):
        numbers = [_number(item) for item in value]
        return [item for item in numbers if item is not None]
    if isinstance(value, str):
        pieces = value.replace("m", " ").replace("×", ",").replace("x", ",").split(",")
        numbers = [_number(item) for item in pieces]
        return [item for item in numbers if item is not None]
    return []


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = "".join(character for character in value if character.isdigit() or character in ".-")
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    if number is None:
        return None
    return int(number)


def _absent(field: str) -> dict[str, Any]:
    return {"field": field, "value": None, "origin": "UNAVAILABLE"}


def _unavailable(field: str, reason: str) -> dict[str, Any]:
    return {"field": field, "status": "UNAVAILABLE", "origin": "UNAVAILABLE", "reason": reason}


def _preserved(field: str, reason: str) -> dict[str, Any]:
    return {"field": field, "status": "PRESERVED", "origin": "UNAVAILABLE", "reason": reason}
