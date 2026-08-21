"""Injectable platform services for engineering agent handlers."""

from __future__ import annotations

from dataclasses import dataclass

from app.application.analysis_engine_service import AnalysisEngineService
from app.application.cad_generation_service import CadGenerationService
from app.application.code_engine_service import CodeEngineService
from app.application.design_engine_service import DesignEngineService
from app.application.engineering_result_service import EngineeringResultService
from app.application.optimization_engine_service import OptimizationEngineService
from app.application.integration_service import IntegrationService
from app.application.validation_engine_service import ValidationEngineService


@dataclass(frozen=True)
class EngineeringAgentServices:
    validation_engine: ValidationEngineService
    analysis_engine: AnalysisEngineService
    design_engine: DesignEngineService
    optimization_engine: OptimizationEngineService
    integration_service: IntegrationService
    code_engine: CodeEngineService
    engineering_result_service: EngineeringResultService
    cad_generation_service: CadGenerationService
