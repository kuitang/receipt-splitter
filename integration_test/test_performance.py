"""Performance-related integration tests."""

import json
import time

import pytest

from integration_test.base_test import IntegrationTestBase

pytestmark = pytest.mark.integration


def test_large_receipt_performance(integration_client: IntegrationTestBase) -> None:
    upload = integration_client.upload_receipt("Performance Tester")
    slug = upload["receipt_slug"]
    assert slug
    assert integration_client.wait_for_processing(slug)

    payload = IntegrationTestBase.TestData.large_receipt(50)

    start = time.time()
    update = integration_client.update_receipt(slug, payload)
    update_duration = time.time() - start
    assert update["status_code"] == 200
    assert update_duration < 5

    receipt = integration_client.get_receipt_data(slug)
    assert receipt
    assert len(receipt["items"]) == 50
    integration_client.assert_receipt_balanced(receipt)

    finalize = integration_client.finalize_receipt(slug)
    assert finalize["status_code"] == 200

    assert integration_client.set_viewer_name(slug, "Performance Tester")
    receipt = integration_client.get_receipt_data(slug)

    claim_payload = {
        "claims": [
            {"line_item_id": str(item["id"]), "quantity": 1}
            for item in receipt["items"][:10]
        ]
    }

    claim_start = time.time()
    response = integration_client.client.post(
        f"/claim/{slug}/",
        data=json.dumps(claim_payload),
        content_type="application/json",
    )
    claim_duration = time.time() - claim_start
    assert response.status_code == 200
    result = json.loads(response.content)
    assert result["success"] is True
    assert claim_duration < 10
