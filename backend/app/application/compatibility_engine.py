"""Detect edition mismatches and cross-standard conflicts in CodeConfiguration."""

from __future__ import annotations

from app.domain.models.code_engine import CodeConflictReport
from app.domain.models.pem import CodeConfiguration, CompatibilityStatus, Jurisdiction


class CompatibilityEngine:
    _US_EXPECTED = {
        "IBC": "IBC 2024",
        "ASCE 7": "ASCE 7-22",
        "ACI 318": "ACI CODE-318-25",
        "AISC 360": "AISC 360-22",
    }

    def detect_conflicts(self, configuration: CodeConfiguration) -> list[CodeConflictReport]:
        conflicts: list[CodeConflictReport] = []

        if configuration.compatibility_status == CompatibilityStatus.CONFLICT:
            conflicts.append(
                CodeConflictReport(
                    conflict_type="MARKED_CONFLICT",
                    severity="ERROR",
                    message="Code configuration is marked as CONFLICT",
                    affected_standards=[
                        configuration.governing_building_code.family,
                        configuration.loading_standard.family,
                    ],
                    recommendation="Review and resolve code configuration conflicts before design.",
                )
            )

        same_family = (
            configuration.seismic_standard is not None
            and configuration.loading_standard.family == configuration.seismic_standard.family
        )
        # Different standards (e.g. Mabhas 6 loads vs Standard 2800 seismic) legitimately carry different
        # editions; only a loading/seismic pair issued under the same standard family can be mismatched.
        if same_family and configuration.loading_edition != configuration.seismic_edition and configuration.seismic_edition:
            conflicts.append(
                CodeConflictReport(
                    conflict_type="EDITION_MISMATCH",
                    severity="WARNING",
                    message="Loading and seismic standard editions differ",
                    affected_standards=[
                        configuration.loading_standard.edition,
                        configuration.seismic_standard.edition if configuration.seismic_standard else "",
                    ],
                    recommendation="Confirm seismic provisions align with the selected loading standard.",
                )
            )

        if configuration.jurisdiction == Jurisdiction.US:
            conflicts.extend(self._check_us_profile_alignment(configuration))

        return conflicts

    def _check_us_profile_alignment(
        self, configuration: CodeConfiguration
    ) -> list[CodeConflictReport]:
        findings: list[CodeConflictReport] = []
        checks = [
            (configuration.governing_building_code, configuration.governing_code_edition, "IBC"),
            (configuration.loading_standard, configuration.loading_edition, "ASCE 7"),
            (configuration.concrete_standard, configuration.concrete_edition, "ACI 318"),
            (configuration.steel_standard, configuration.steel_edition, "AISC 360"),
        ]
        for standard, edition, family in checks:
            expected = self._US_EXPECTED.get(family)
            if expected and edition != expected and standard.edition != expected:
                findings.append(
                    CodeConflictReport(
                        conflict_type="EDITION_MISMATCH",
                        severity="WARNING",
                        message=f"{family} edition may not align with platform US default profile",
                        affected_standards=[standard.edition, expected],
                        recommendation=(
                            "Confirm selected edition is jurisdictionally adopted for this project."
                        ),
                    )
                )
        return findings
