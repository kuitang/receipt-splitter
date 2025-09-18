"""Integration tests covering receipt validation behaviour."""

import pytest

from integration_test.base_test import IntegrationTestBase

pytestmark = pytest.mark.integration


def test_balance_validation(integration_client: IntegrationTestBase) -> None:
    upload = integration_client.upload_receipt("Validation Tester")
    slug = upload["receipt_slug"]
    assert slug
    assert integration_client.wait_for_processing(slug)

    cases = [
        ("balanced receipt", IntegrationTestBase.TestData.balanced_receipt(), True),
        ("unbalanced totals", IntegrationTestBase.TestData.unbalanced_receipt(), False),
        ("negative tip allowed", IntegrationTestBase.TestData.receipt_with_negative_tip(), True),
    ]

    for label, payload, should_balance in cases:
        response = integration_client.update_receipt(slug, payload)
        assert response["status_code"] == 200, label
        is_balanced = response["data"]["is_balanced"]
        if should_balance:
            assert is_balanced is True
        else:
            assert is_balanced is False
