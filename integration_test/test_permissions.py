"""Integration tests verifying session and permissions behaviour."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from integration_test.base_test import IntegrationTestBase

pytestmark = pytest.mark.integration


def test_claims_blocked_before_finalization(
    integration_client: IntegrationTestBase,
) -> None:
    uploader = integration_client.create_new_session()
    upload = uploader.upload_receipt("Uploader")
    slug = upload["receipt_slug"]
    assert slug
    assert uploader.wait_for_processing(slug)

    receipt = uploader.get_receipt_data(slug)
    item_id = receipt["items"][0]["id"]

    claim = uploader.claim_item(slug, item_id, quantity=1)
    assert claim["status_code"] == 400

    viewer = integration_client.create_new_session()
    assert viewer.set_viewer_name(slug, "Viewer")
    viewer_claim = viewer.claim_item(slug, item_id, quantity=1)
    assert viewer_claim["status_code"] == 400


def test_name_based_claim_calculations(integration_client: IntegrationTestBase) -> None:
    uploader = integration_client.create_new_session()
    upload = uploader.upload_receipt("Restaurant Owner")
    slug = upload["receipt_slug"]
    assert slug
    assert uploader.wait_for_processing(slug)

    test_data = IntegrationTestBase.TestData.balanced_receipt()
    test_data.update(
        {
            "restaurant_name": "The Gin Mill",
            "subtotal": "64.00",
            "tax": "0.00",
            "tip": "0.00",
            "total": "64.00",
            "items": [
                {"name": "PALOMA", "quantity": 1, "unit_price": "17.68", "total_price": "17.68"},
                {"name": "HAPPY HOUR BEER", "quantity": 1, "unit_price": "5.20", "total_price": "5.20"},
                {"name": "WELL TEQUILA", "quantity": 1, "unit_price": "5.20", "total_price": "5.20"},
                {"name": "BURGER", "quantity": 1, "unit_price": "15.00", "total_price": "15.00"},
                {"name": "FRIES", "quantity": 1, "unit_price": "8.00", "total_price": "8.00"},
                {"name": "SALAD", "quantity": 1, "unit_price": "12.92", "total_price": "12.92"},
            ],
        }
    )

    uploader.update_receipt(slug, test_data)
    uploader.finalize_receipt(slug)

    kui = integration_client.create_new_session()
    assert kui.set_viewer_name(slug, "Kui")

    receipt_data = kui.get_receipt_data(slug)
    paloma_id = next(item["id"] for item in receipt_data["items"] if item["name"] == "PALOMA")
    claim = kui.claim_item(slug, paloma_id, quantity=1)
    assert claim["status_code"] == 200
    kui_total = Decimal(str(claim["data"]["my_total"]))
    assert kui_total == Decimal("17.68")

    kui5 = integration_client.create_new_session()
    assert kui5.set_viewer_name(slug, "Kui 5")

    bulk_claim = {
        "claims": [
            {"line_item_id": next(item["id"] for item in receipt_data["items"] if item["name"] == "HAPPY HOUR BEER"), "quantity": 1},
            {"line_item_id": next(item["id"] for item in receipt_data["items"] if item["name"] == "WELL TEQUILA"), "quantity": 1},
        ]
    }

    response = kui5.client.post(
        f"/claim/{slug}/",
        data=json.dumps(bulk_claim),
        content_type="application/json",
    )
    assert response.status_code == 200

    final_state = kui.get_receipt_data(slug)
    kui_claims = [
        Decimal(str(claim_entry["share_amount"]))
        for item in final_state["items"]
        for claim_entry in item.get("claims", [])
        if claim_entry["claimer_name"] == "Kui"
    ]
    kui5_claims = [
        Decimal(str(claim_entry["share_amount"]))
        for item in final_state["items"]
        for claim_entry in item.get("claims", [])
        if claim_entry["claimer_name"] == "Kui 5"
    ]

    assert sum(kui_claims) == Decimal("17.68")
    assert sum(kui5_claims) == Decimal("10.40")


def test_uploader_permissions_survive_name_change(
    integration_client: IntegrationTestBase,
) -> None:
    uploader = integration_client.create_new_session()
    upload = uploader.upload_receipt("Original Uploader")
    slug = upload["receipt_slug"]
    assert slug
    assert uploader.wait_for_processing(slug)

    payload = IntegrationTestBase.TestData.balanced_receipt()
    update = uploader.update_receipt(slug, payload)
    assert update["status_code"] == 200

    receipt_data = uploader.get_receipt_data(slug)
    session = uploader.client.session
    receipt_id = str(receipt_data["id"])
    if "receipts" in session and receipt_id in session["receipts"]:
        session["receipts"][receipt_id]["viewer_name"] = "Original Uploader 2"
        session.save()

    payload["restaurant_name"] = "Updated Restaurant"
    update = uploader.update_receipt(slug, payload)
    assert update["status_code"] == 200

    intruder = integration_client.create_new_session()
    response = intruder.update_receipt(slug, payload)
    assert response["status_code"] == 403

    finalize = uploader.finalize_receipt(slug)
    assert finalize["status_code"] == 200


def test_session_isolation_and_finalization_redirect(
    integration_client: IntegrationTestBase,
) -> None:
    owner = integration_client.create_new_session()
    upload = owner.upload_receipt("Owner")
    slug = upload["receipt_slug"]
    assert slug
    assert owner.wait_for_processing(slug)

    payload = IntegrationTestBase.TestData.balanced_receipt()
    intruder = integration_client.create_new_session()

    unauthorized_update = intruder.update_receipt(slug, payload)
    assert unauthorized_update["status_code"] == 403

    unauthorized_finalize = intruder.finalize_receipt(slug)
    assert unauthorized_finalize["status_code"] == 403

    authorized_update = owner.update_receipt(slug, payload)
    assert authorized_update["status_code"] == 200

    finalize = owner.finalize_receipt(slug)
    assert finalize["status_code"] == 200

    response = owner.client.get(f"/edit/{slug}/")
    assert response.status_code == 302


def test_session_hijacking_blocked(integration_client: IntegrationTestBase) -> None:
    owner = integration_client.create_new_session()
    upload = owner.upload_receipt("Owner Second")
    slug = upload["receipt_slug"]
    assert slug
    assert owner.wait_for_processing(slug)

    intruder = integration_client.create_new_session()
    session = intruder.client.session
    session["receipt_id"] = slug
    session.save()

    payload = IntegrationTestBase.TestData.balanced_receipt()
    response = intruder.update_receipt(slug, payload)
    assert response["status_code"] == 403


def test_concurrent_edit_protection(integration_client: IntegrationTestBase) -> None:
    owner = integration_client.create_new_session()
    upload = owner.upload_receipt("Owner Third")
    slug = upload["receipt_slug"]
    assert slug
    assert owner.wait_for_processing(slug)

    authorized_results = []
    for _ in range(3):
        payload = IntegrationTestBase.TestData.balanced_receipt()
        response = owner.update_receipt(slug, payload)
        authorized_results.append(response["status_code"])

    assert authorized_results.count(200) == 3

    intruder = integration_client.create_new_session()

    owner_payload = IntegrationTestBase.TestData.balanced_receipt()
    owner_payload["restaurant_name"] = "User A Edit"

    intruder_payload = IntegrationTestBase.TestData.balanced_receipt()
    intruder_payload["restaurant_name"] = "User B Edit"

    owner_result = owner.update_receipt(slug, owner_payload)
    intruder_result = intruder.update_receipt(slug, intruder_payload)

    assert owner_result["status_code"] == 200
    assert intruder_result["status_code"] == 403
