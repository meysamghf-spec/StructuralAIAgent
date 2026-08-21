"""Failure propagation, CSI unavailable, payment security, and idempotency tests."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.application.exceptions import DuplicatePaymentTransactionError, InvalidWebhookSignatureError
from app.application.service_factory import (
    build_analysis_engine_service,
    build_design_engine_service,
    build_digital_payment_agent,
    get_crypto_payment_gateway,
)
from app.domain.models.analysis import AnalysisRequest
from app.domain.models.csi_extraction import CsiExtractionStatus
from app.domain.models.design import DesignRequest
from app.domain.models.integration import IntegrationOperationStatus, IntegrationSoftware
from app.domain.models.payments import PaymentStatus
from app.infrastructure.integrations.csi_result_extractor import extract_csi_results
from tests.integration.helpers import (
    create_project,
    populate_standard_pem,
    unavailable_csi_adapter,
)
from tests.test_csi_result_extractor import _MockAnalyze, _MockSapModel


@pytest.fixture(autouse=True)
def _reset_payment_gateway() -> None:
    gateway = get_crypto_payment_gateway()
    gateway._invoices.clear()
    gateway._transactions.clear()


@pytest.fixture
def payment_agent(db_session):
    return build_digital_payment_agent()


def test_scenario_f_csi_not_installed_reports_unavailable(db_session) -> None:
    adapter = unavailable_csi_adapter()
    result = adapter.extract_results(
        uuid4(),
        parameters={"pem_snapshot_id": str(uuid4()), "pem_version": 1},
    )
    assert result.status in {
        IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
        IntegrationOperationStatus.NOT_INSTALLED,
        IntegrationOperationStatus.NOT_ACCESSIBLE,
    }
    assert "parsed_results" not in result.metadata or not result.metadata.get("parsed_results")


def test_scenario_f_unanalyzed_model_not_analyzed(db_session) -> None:
    class _UnanalyzedSapModel:
        Analyze = _MockAnalyze(analyzed=False)
        Results = None

    raw, summary = extract_csi_results(
        _UnanalyzedSapModel(),
        software=IntegrationSoftware.ETABS,
    )
    assert summary.overall_status == CsiExtractionStatus.NOT_ANALYZED
    assert "member_forces" not in raw


def test_scenario_f_solver_analysis_without_csi_does_not_fabricate_results(db_session) -> None:
    project = create_project("Scenario F analysis")
    populate_standard_pem(project.id)
    result = build_analysis_engine_service().run_analysis(
        AnalysisRequest(
            project_id=project.id,
            analysis_type="STATIC",
            parameters={"solver": "ETABS"},
        )
    )
    assert result.outputs.get("engineering_results_available") is False
    assert result.status.value in {"REQUIRES_LOCAL_SOFTWARE", "FAILED", "SUCCESS"}


def test_failure_design_without_frame_forces_does_not_claim_pass(db_session) -> None:
    project = create_project("Failure design")
    populate_standard_pem(project.id)
    design = build_design_engine_service().run_design(
        DesignRequest(project_id=project.id, design_type="CONCRETE_BEAM"),
    )
    assert design.status.value == "REQUIRES_ANALYSIS"
    assert design.outputs.get("routine_connected") is not True


def test_failure_mock_execution_results_rejected(db_session) -> None:
    from app.application.service_factory import build_engineering_result_service, build_pem_model_service
    from app.domain.models.engineering_results import EngineeringResultIngestionRequest

    project = create_project("Mock rejection")
    version, snapshot_id = populate_standard_pem(project.id)
    result_set = build_engineering_result_service().ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project.id,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results={
                "member_forces": [{"id": "mbr-1", "values": [1.0], "load_case": "lc-dead"}],
            },
            provenance={"source_software": "ETABS", "execution_mode": "mock"},
        )
    )
    assert result_set.engineering_results_available is False
    assert result_set.validation_status.value == "INVALID"


def test_scenario_g_payment_upgrade_lifecycle(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="lifecycle-user",
        upgrade_product_id="pro-workspace",
        currency="USDT",
        network="ethereum",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=payment.payment_address,
        amount=payment.crypto_amount,
        transaction_hash="0xlifecycle",
        confirmations=3,
    )
    result = payment_agent.reconcile_payment(payment.id, account_id="lifecycle-user")
    assert result["payment"]["status"] == PaymentStatus.PAID.value
    assert result["upgrade_activated"] is True
    entitlements = payment_agent.list_account_entitlements("lifecycle-user")
    assert any(item.upgrade_product_id == "pro-workspace" for item in entitlements)


def test_scenario_h_underpayment_does_not_activate(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="underpaid-user",
        upgrade_product_id="pro-workspace",
        currency="BTC",
        network="bitcoin",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=payment.payment_address,
        amount=payment.crypto_amount * 0.5,
        transaction_hash="0xunder",
        confirmations=3,
    )
    result = payment_agent.reconcile_payment(payment.id, account_id="underpaid-user")
    assert result["payment"]["status"] == PaymentStatus.UNDERPAID.value
    assert result["upgrade_activated"] is False


def test_scenario_h_forged_webhook_rejected(payment_agent) -> None:
    payload = json.dumps({"invoice_id": "fake", "transaction_hash": "0xbad"}).encode()
    with pytest.raises(InvalidWebhookSignatureError):
        payment_agent.process_provider_webhook(payload, "bad-signature")


def test_scenario_h_duplicate_transaction_blocked(payment_agent) -> None:
    first = payment_agent.create_upgrade_invoice(
        account_id="dup-a",
        upgrade_product_id="pro-workspace",
        currency="ETH",
        network="ethereum",
    )
    second = payment_agent.create_upgrade_invoice(
        account_id="dup-b",
        upgrade_product_id="pro-workspace",
        currency="ETH",
        network="ethereum",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=first.payment_address,
        amount=first.crypto_amount,
        transaction_hash="0xduplicate",
        confirmations=3,
    )
    payment_agent.reconcile_payment(first.id, account_id="dup-a")
    with pytest.raises(DuplicatePaymentTransactionError):
        payment_agent.submit_transaction_for_verification(
            second.id,
            account_id="dup-b",
            transaction_hash="0xduplicate",
        )


def test_idempotency_invoice_creation(payment_agent) -> None:
    first = payment_agent.create_upgrade_invoice(
        account_id="idem-user",
        upgrade_product_id="solver-plus",
        currency="BTC",
        network="bitcoin",
        idempotency_key="same-invoice-key",
    )
    second = payment_agent.create_upgrade_invoice(
        account_id="idem-user",
        upgrade_product_id="solver-plus",
        currency="BTC",
        network="bitcoin",
        idempotency_key="same-invoice-key",
    )
    assert first.id == second.id


def test_idempotency_webhook_and_concurrent_reconcile(payment_agent) -> None:
    payment = payment_agent.create_upgrade_invoice(
        account_id="concurrent-user",
        upgrade_product_id="pro-workspace",
        currency="ETH",
        network="ethereum",
    )
    gateway = get_crypto_payment_gateway()
    gateway.simulate_payment(
        payment_address=payment.payment_address,
        amount=payment.crypto_amount,
        transaction_hash="0xconcurrent",
        confirmations=3,
    )

    def _reconcile():
        return payment_agent.reconcile_payment(payment.id, account_id="concurrent-user")

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _reconcile(), range(4)))

    assert len(payment_agent.list_account_entitlements("concurrent-user")) == 1
    assert sum(1 for item in results if item.get("upgrade_activated")) >= 1

    payload = {
        "invoice_id": payment.invoice_id,
        "transaction_hash": "0xconcurrent",
        "network": "ethereum",
    }
    body = json.dumps(payload, sort_keys=True).encode()
    signature = gateway.sign_webhook_payload(payload)
    webhook_once = payment_agent.process_provider_webhook(body, signature)
    webhook_twice = payment_agent.process_provider_webhook(body, signature)
    assert webhook_once.get("upgrade_activated") is True
    assert webhook_twice.get("upgrade_activated") is True
    assert len(payment_agent.list_account_entitlements("concurrent-user")) == 1


def test_api_payment_unauthorized_lookup(api_client: TestClient) -> None:
    owner_headers = {"X-Actor-Id": "owner-user"}
    other_headers = {"X-Actor-Id": "other-user"}
    created = api_client.post(
        "/api/v1/payments/invoices",
        json={
            "upgrade_product_id": "pro-workspace",
            "currency": "BTC",
            "network": "bitcoin",
        },
        headers=owner_headers,
    )
    payment_id = created.json()["payment"]["id"]
    denied = api_client.get(f"/api/v1/payments/invoices/{payment_id}", headers=other_headers)
    assert denied.status_code == 403


def test_api_error_envelope_has_no_stack_trace(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/projects/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert "traceback" not in json.dumps(body).lower()
    assert "error" in body
