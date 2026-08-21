"""Default integration adapter registry."""

from app.infrastructure.integrations.autocad_adapter import AutocadAdapter
from app.infrastructure.integrations.csi_structural_adapter import (
    EtabsAdapter,
    SafeAdapter,
    Sap2000Adapter,
)

__all__ = ["build_integration_adapters"]


def build_integration_adapters() -> dict[str, object]:
    adapters = [
        EtabsAdapter(),
        Sap2000Adapter(),
        SafeAdapter(),
        AutocadAdapter(),
    ]
    return {adapter.software_name: adapter for adapter in adapters}
