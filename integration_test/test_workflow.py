"""End-to-end workflow integration tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from integration_test.base_test import IntegrationTestBase

pytestmark = pytest.mark.integration


def test_complete_receipt_workflow(
    integration_client: IntegrationTestBase, heic_fixture_bytes: bytes
) -> None:
    """Exercise the happy path from upload through final claims."""
    upload = integration_client.upload_receipt(
        uploader_name="Integration Tester",
        image_bytes=heic_fixture_bytes,
        filename="IMG_6839.HEIC",
    )
    assert upload["status_code"] == 302
    slug = upload["receipt_slug"]
    assert slug

    assert integration_client.wait_for_processing(slug)

    receipt = integration_client.get_receipt_data(slug)
    assert receipt is not None
    assert receipt["restaurant_name"], "OCR should populate restaurant name"
    assert receipt["items"], "OCR should populate line items"

    # Invalid update keeps receipt unbalanced
    invalid_payload = IntegrationTestBase.TestData.unbalanced_receipt()
    invalid_update = integration_client.update_receipt(slug, invalid_payload)
    assert invalid_update["status_code"] == 200
    assert invalid_update["data"]["is_balanced"] is False

    # Attempting to finalise unbalanced data should fail
    finalize_invalid = integration_client.finalize_receipt(slug)
    assert finalize_invalid["status_code"] == 400

    # Provide balanced payload and finalise successfully
    balanced_payload = IntegrationTestBase.TestData.balanced_receipt()
    update = integration_client.update_receipt(slug, balanced_payload)
    assert update["status_code"] == 200
    assert update["data"]["is_balanced"] is True

    finalize = integration_client.finalize_receipt(slug)
    assert finalize["status_code"] == 200
    share_url = finalize["data"].get("share_url")
    assert share_url

    receipt = integration_client.get_receipt_data(slug)
    assert receipt["is_finalized"] is True

    # Simulate two additional users claiming items
    second_user = integration_client.create_new_session()
    third_user = integration_client.create_new_session()
    assert second_user.set_viewer_name(slug, "Bob")
    assert third_user.set_viewer_name(slug, "Carol")

    receipt = integration_client.get_receipt_data(slug)
    first_item_id = receipt["items"][0]["id"]
    second_item_id = receipt["items"][1]["id"]

    claim_one = second_user.claim_item(slug, first_item_id, quantity=1)
    assert claim_one["status_code"] == 200

    claim_two = third_user.claim_item(slug, second_item_id, quantity=2)
    assert claim_two["status_code"] == 200

    final_state = integration_client.get_receipt_data(slug)
    total = Decimal(str(final_state["total"]))

    claimed = Decimal("0")
    for item in final_state["items"]:
        for claim in item.get("claims", []):
            claimed += Decimal(str(claim["share_amount"]))

    assert claimed <= total
    assert total - claimed >= Decimal("0")


def test_edit_requires_session_owner(integration_client: IntegrationTestBase) -> None:
    """Ensure only the uploading session can edit the receipt."""
    upload = integration_client.upload_receipt("Owner Session")
    slug = upload["receipt_slug"]
    assert slug
    assert integration_client.wait_for_processing(slug)

    payload = IntegrationTestBase.TestData.balanced_receipt()
    update = integration_client.update_receipt(slug, payload)
    assert update["status_code"] == 200

    intruder = integration_client.create_new_session()
    response = intruder.update_receipt(slug, payload)
    assert response["status_code"] == 403


def test_image_removed_after_finalization(integration_client: IntegrationTestBase) -> None:
    """Receipt images should be purged once the receipt is finalised."""

    upload = integration_client.upload_receipt("Image Cleanup Tester")
    slug = upload["receipt_slug"]
    assert slug

    assert integration_client.wait_for_processing(slug)

    before = integration_client.client.get(f"/image/{slug}/")
    assert before.status_code == 200

    payload = IntegrationTestBase.TestData.balanced_receipt()
    update = integration_client.update_receipt(slug, payload)
    assert update["status_code"] == 200

    finalize = integration_client.finalize_receipt(slug)
    assert finalize["status_code"] == 200

    after = integration_client.client.get(f"/image/{slug}/")
    assert after.status_code == 404
