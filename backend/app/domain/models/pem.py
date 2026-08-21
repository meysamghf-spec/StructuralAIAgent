"""ProjectEngineeringModel (PEM) domain structures — Single Source of Truth schema."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.models.pem_structural import StructuralModel, create_empty_structural_model


class Jurisdiction(StrEnum):
    US = "US"
    IRAN = "IRAN"
    EU = "EU"


class ProfileType(StrEnum):
    SOFTWARE_DEFAULT = "SOFTWARE_DEFAULT"
    PROJECT_SELECTED = "PROJECT_SELECTED"
    JURISDICTIONALLY_ADOPTED = "JURISDICTIONALLY_ADOPTED"
    SUPPLEMENTARY = "SUPPLEMENTARY"
    HISTORICAL_LEGACY = "HISTORICAL_LEGACY"


class CodeConfigurationStatus(StrEnum):
    SOFTWARE_DEFAULT = "SOFTWARE_DEFAULT"
    USER_CONFIRMED = "USER_CONFIRMED"
    MODIFIED_PENDING_VALIDATION = "MODIFIED_PENDING_VALIDATION"
    HISTORICAL = "HISTORICAL"


class CompatibilityStatus(StrEnum):
    COMPATIBLE = "COMPATIBLE"
    EDITION_MISMATCH = "EDITION_MISMATCH"
    CONFLICT = "CONFLICT"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class PublicationStatus(StrEnum):
    PUBLISHED = "PUBLISHED"
    ADOPTED = "ADOPTED"
    FUTURE = "FUTURE"
    DEPRECATED = "DEPRECATED"


class UnitSystem(StrEnum):
    US_CUSTOMARY = "US_CUSTOMARY"
    SI_METRIC = "SI_METRIC"


class UnitConfigurationStatus(StrEnum):
    DEFAULT = "DEFAULT"
    USER_CONFIRMED = "USER_CONFIRMED"
    MODIFIED_PENDING_VALIDATION = "MODIFIED_PENDING_VALIDATION"


class ParameterMetadata(BaseModel):
    """Metadata for engineering parameters (minimal M2 subset)."""

    name: str | None = None
    source: str | None = None
    author: str | None = None
    derivation: str | None = None


class StandardReference(BaseModel):
    family: str
    edition: str
    full_designation: str
    publication_status: PublicationStatus = PublicationStatus.PUBLISHED
    plugin_id: str | None = None


class CodeConfiguration(BaseModel):
    """First-class PEM entity — project-scoped design code profile."""

    profile_type: ProfileType = ProfileType.SOFTWARE_DEFAULT
    jurisdiction: Jurisdiction = Jurisdiction.US
    project_location: str | None = None
    governing_building_code: StandardReference
    governing_code_edition: str
    loading_standard: StandardReference
    loading_edition: str
    seismic_standard: StandardReference | None = None
    seismic_edition: str | None = None
    concrete_standard: StandardReference
    concrete_edition: str
    steel_standard: StandardReference
    steel_edition: str
    foundation_standards: list[StandardReference] = Field(default_factory=list)
    supplementary_standards: list[StandardReference] = Field(default_factory=list)
    compatibility_status: CompatibilityStatus = CompatibilityStatus.COMPATIBLE
    configured_by: str = "system"
    configured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: CodeConfigurationStatus = CodeConfigurationStatus.SOFTWARE_DEFAULT
    metadata: ParameterMetadata = Field(default_factory=ParameterMetadata)


class UnitConfiguration(BaseModel):
    """First-class PEM entity — project-scoped unit system."""

    system: UnitSystem = UnitSystem.US_CUSTOMARY
    length_unit: str = "ft"
    force_unit: str = "kip"
    moment_unit: str = "kip-ft"
    stress_unit: str = "ksi"
    area_unit: str = "in2"
    volume_unit: str = "ft3"
    configured_by: str = "system"
    configured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: UnitConfigurationStatus = UnitConfigurationStatus.DEFAULT
    metadata: ParameterMetadata = Field(default_factory=ParameterMetadata)


class ProjectMetadata(BaseModel):
    name: str
    description: str | None = None


class PemSnapshotMeta(BaseModel):
    """Metadata for a persisted PEM snapshot row (not the full document)."""

    id: UUID
    project_id: UUID
    version: int
    is_current: bool


class ProjectEngineeringModel(BaseModel):
    """
    Single Source of Truth for project engineering data.

    M2 stores code_configuration and unit_configuration as first-class structures.
    Additional PEM sections are reserved for future milestones.
    """

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    metadata: ProjectMetadata
    code_configuration: CodeConfiguration
    unit_configuration: UnitConfiguration
    requirements: dict[str, Any] = Field(default_factory=dict)
    architecture: dict[str, Any] = Field(default_factory=dict)
    structural_system: dict[str, Any] = Field(default_factory=dict)
    analysis_models: list[Any] = Field(default_factory=list)
    design_results: list[Any] = Field(default_factory=list)
    validation_results: list[Any] = Field(default_factory=list)
    decisions: list[Any] = Field(default_factory=list)
    assumptions: list[Any] = Field(default_factory=list)
    structural_model: StructuralModel = Field(default_factory=create_empty_structural_model)


def create_software_default_code_configuration() -> CodeConfiguration:
    """Software Default Code Profile (AG-30) — not jurisdictionally adopted."""
    asce = StandardReference(
        family="ASCE 7",
        edition="ASCE 7-22",
        full_designation=(
            "ASCE/SEI 7-22 Minimum Design Loads and Associated Criteria "
            "for Buildings and Other Structures"
        ),
    )
    return CodeConfiguration(
        profile_type=ProfileType.SOFTWARE_DEFAULT,
        jurisdiction=Jurisdiction.US,
        governing_building_code=StandardReference(
            family="IBC",
            edition="IBC 2024",
            full_designation="2024 International Building Code",
        ),
        governing_code_edition="2024",
        loading_standard=asce,
        loading_edition="ASCE 7-22",
        seismic_standard=asce,
        seismic_edition="ASCE 7-22",
        concrete_standard=StandardReference(
            family="ACI 318",
            edition="ACI CODE-318-25",
            full_designation=(
                "ACI CODE-318-25 Building Code for Structural Concrete "
                "— Code Requirements and Commentary"
            ),
        ),
        concrete_edition="ACI CODE-318-25",
        steel_standard=StandardReference(
            family="AISC 360",
            edition="AISC 360-22",
            full_designation="ANSI/AISC 360-22 Specification for Structural Steel Buildings",
        ),
        steel_edition="AISC 360-22",
        status=CodeConfigurationStatus.SOFTWARE_DEFAULT,
        metadata=ParameterMetadata(
            name="software_default_code_profile",
            source="SOFTWARE_DEFAULT",
            derivation="Platform default US code profile (Section M.3)",
        ),
    )


def create_us_customary_unit_configuration() -> UnitConfiguration:
    """Default US Customary unit system (Section M.2)."""
    return UnitConfiguration(
        system=UnitSystem.US_CUSTOMARY,
        metadata=ParameterMetadata(
            name="default_unit_system",
            source="SOFTWARE_DEFAULT",
            derivation="Platform default US Customary units (Section M.2)",
        ),
    )


def create_initial_pem(project_id: UUID, name: str, description: str | None = None) -> ProjectEngineeringModel:
    """Build an initial PEM with software-default code and unit configurations."""
    return ProjectEngineeringModel(
        project_id=project_id,
        metadata=ProjectMetadata(name=name, description=description),
        code_configuration=create_software_default_code_configuration(),
        unit_configuration=create_us_customary_unit_configuration(),
    )
