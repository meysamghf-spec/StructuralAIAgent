"""Centralized CodeEngine — plugin registry, configuration validation, deterministic checks."""

from __future__ import annotations

from typing import Any

from app.application.compatibility_engine import CompatibilityEngine
from app.application.exceptions import CodePluginNotFoundError
from app.domain.contracts.code_plugin import StandardPlugin
from app.domain.models.code_engine import (
    CodeCheckResult,
    CodeConfigurationValidationResult,
    CodeDefaultsResult,
    ProvisionReference,
    StandardInfo,
)
from app.domain.models.pem import (
    CodeConfiguration,
    Jurisdiction,
    create_iran_default_code_configuration,
    create_software_default_code_configuration,
)


class CodeEngineService:
    def __init__(
        self,
        *,
        plugins: dict[str, StandardPlugin],
        compatibility_engine: CompatibilityEngine | None = None,
    ) -> None:
        self._plugins = plugins
        self._compatibility = compatibility_engine or CompatibilityEngine()

    def list_available_standards(self) -> list[StandardInfo]:
        return sorted(
            (plugin.get_info() for plugin in self._plugins.values()),
            key=lambda item: item.plugin_id,
        )

    def get_defaults(self, jurisdiction: Jurisdiction = Jurisdiction.IRAN) -> CodeDefaultsResult:
        if jurisdiction == Jurisdiction.IRAN:
            return CodeDefaultsResult(jurisdiction=jurisdiction, configuration=create_iran_default_code_configuration())
        if jurisdiction != Jurisdiction.US:
            config = create_software_default_code_configuration()
            config.jurisdiction = jurisdiction
            return CodeDefaultsResult(jurisdiction=jurisdiction, configuration=config)
        return CodeDefaultsResult(
            jurisdiction=Jurisdiction.US,
            configuration=create_software_default_code_configuration(),
        )

    def validate_configuration(
        self, configuration: CodeConfiguration
    ) -> CodeConfigurationValidationResult:
        conflicts = self._compatibility.detect_conflicts(configuration)
        warnings = [
            "Code configuration uses SOFTWARE_DEFAULT profile; confirm jurisdictionally adopted codes."
        ] if configuration.profile_type.value == "SOFTWARE_DEFAULT" else []

        has_errors = any(item.severity == "ERROR" for item in conflicts)
        return CodeConfigurationValidationResult(
            is_valid=not has_errors,
            configuration=configuration,
            conflicts=conflicts,
            warnings=warnings,
        )

    def detect_conflicts(self, configuration: CodeConfiguration):
        return self._compatibility.detect_conflicts(configuration)

    def get_provision(self, plugin_id: str, section_ref: str) -> ProvisionReference:
        plugin = self._get_plugin(plugin_id)
        return plugin.get_provision(section_ref)

    def run_check(
        self,
        plugin_id: str,
        check_id: str,
        inputs: dict[str, Any],
        *,
        code_configuration: CodeConfiguration,
    ) -> CodeCheckResult:
        plugin = self._get_plugin(plugin_id)
        return plugin.run_check(
            check_id,
            inputs,
            code_configuration=code_configuration,
        )

    def _get_plugin(self, plugin_id: str) -> StandardPlugin:
        plugin = self._plugins.get(plugin_id)
        if plugin is None:
            raise CodePluginNotFoundError(plugin_id=plugin_id)
        return plugin
