"""Default integration adapter registry."""

from app.infrastructure.integrations.autocad_stub_adapter import AutocadStubAdapter
from app.infrastructure.integrations.structural_stub_adapters import (
    EtabsStubAdapter,
    SafeStubAdapter,
    Sap2000StubAdapter,
)

__all__ = ["build_integration_adapters"]


def build_integration_adapters() -> dict[str, object]:
    adapters = [
        EtabsStubAdapter(),
        Sap2000StubAdapter(),
        SafeStubAdapter(),
        AutocadStubAdapter(),
    ]
    return {adapter.software_name: adapter for adapter in adapters}
