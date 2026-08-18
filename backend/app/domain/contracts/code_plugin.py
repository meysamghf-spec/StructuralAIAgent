"""StandardPlugin contract for modular CodeEngine plugins."""

from __future__ import annotations

from typing import Any, Protocol

from app.domain.models.code_engine import (
    CodeCheckResult,
    ProvisionReference,
    StandardInfo,
    StandardRole,
)
from app.domain.models.pem import CodeConfiguration


class StandardPlugin(Protocol):
    @property
    def plugin_id(self) -> str: ...

    @property
    def family(self) -> str: ...

    @property
    def edition(self) -> str: ...

    @property
    def roles(self) -> list[StandardRole]: ...

    def get_info(self) -> StandardInfo: ...

    def get_provision(self, section_ref: str) -> ProvisionReference: ...

    def run_check(
        self,
        check_id: str,
        inputs: dict[str, Any],
        *,
        code_configuration: CodeConfiguration,
    ) -> CodeCheckResult: ...

    def get_compatible_with(self, other_plugin_id: str) -> bool: ...
