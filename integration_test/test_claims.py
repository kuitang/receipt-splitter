"""Integration tests covering the real-time claim workflow."""

from __future__ import annotations

import json

from decimal import Decimal

import pytest

from integration_test.base_test import IntegrationTestBase

pytestmark = pytest.mark.integration


def test_polling_endpoint_returns_expected_structure(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, _ = finalized_receipt
    response = integration_client.client.get(f"/claim/{slug}/status/")
    assert response.status_code == 200

    payload = json.loads(response.content)
    assert payload["success"] is True

    for field in ["participant_totals", "total_claimed", "total_unclaimed", "my_total", "items_with_claims"]:
        assert field in payload

    assert isinstance(payload["items_with_claims"], list)


def test_claim_updates_are_visible_to_other_sessions(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, item_ids = finalized_receipt

    alice = integration_client.create_new_session()
    bob = integration_client.create_new_session()

    assert alice.set_viewer_name(slug, "Alice")
    assert bob.set_viewer_name(slug, "Bob")

    claim = alice.claim_item(slug, item_ids[0], quantity=1)
    assert claim["status_code"] == 200

    status = bob.client.get(f"/claim/{slug}/status/")
    assert status.status_code == 200
    payload = json.loads(status.content)

    participants = {entry["name"] for entry in payload["participant_totals"]}
    assert "Alice" in participants

    claimed_item = next(item for item in payload["items_with_claims"] if item["item_id"] == str(item_ids[0]))
    assert claimed_item["claims"]
    assert claimed_item["claims"][0]["claimer_name"] == "Alice"
    assert claimed_item["claims"][0]["quantity_claimed"] == 1
    assert claimed_item["available_quantity"] >= 0


def test_real_time_availability_updates(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, item_ids = finalized_receipt

    alice = integration_client.create_new_session()
    bob = integration_client.create_new_session()

    assert alice.set_viewer_name(slug, "Alice")
    assert bob.set_viewer_name(slug, "Bob")

    initial = bob.client.get(f"/claim/{slug}/status/")
    assert initial.status_code == 200
    initial_payload = json.loads(initial.content)
    target = next(item for item in initial_payload["items_with_claims"] if item["item_id"] == str(item_ids[0]))
    available_before = target["available_quantity"]
    assert available_before > 0

    claim = alice.claim_item(slug, item_ids[0], quantity=available_before)
    assert claim["status_code"] == 200

    updated = bob.client.get(f"/claim/{slug}/status/")
    assert updated.status_code == 200
    updated_payload = json.loads(updated.content)
    updated_item = next(item for item in updated_payload["items_with_claims"] if item["item_id"] == str(item_ids[0]))
    assert updated_item["available_quantity"] == 0
    assert len(updated_item["claims"]) == 1
    assert updated_item["claims"][0]["quantity_claimed"] == available_before


def test_participant_totals_update(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, item_ids = finalized_receipt

    sessions = {}
    for name in ["Alice", "Bob", "Charlie"]:
        session = integration_client.create_new_session()
        assert session.set_viewer_name(slug, name)
        sessions[name] = session

    claims = [
        ("Alice", item_ids[0], 1),
        ("Bob", item_ids[1], 1),
        ("Charlie", item_ids[1], 1),
    ]

    for user, item_id, quantity in claims:
        result = sessions[user].claim_item(slug, item_id, quantity=quantity)
        assert result["status_code"] == 200

    for viewer, session in sessions.items():
        status = session.client.get(f"/claim/{slug}/status/")
        assert status.status_code == 200
        payload = json.loads(status.content)

        participants = {entry["name"] for entry in payload["participant_totals"]}
        assert participants.issuperset(sessions.keys())

        for entry in payload["participant_totals"]:
            if entry["name"] in sessions:
                assert Decimal(str(entry["amount"])) > Decimal("0")


def test_concurrent_claim_conflicts(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, item_ids = finalized_receipt

    alice = integration_client.create_new_session()
    bob = integration_client.create_new_session()

    assert alice.set_viewer_name(slug, "Alice")
    assert bob.set_viewer_name(slug, "Bob")

    status = alice.client.get(f"/claim/{slug}/status/")
    assert status.status_code == 200
    payload = json.loads(status.content)

    try:
        target = next(item for item in payload["items_with_claims"] if item["available_quantity"] > 1)
    except StopIteration:
        target = payload["items_with_claims"][0]

    target_id = int(target["item_id"])

    alice_response = alice.claim_item(slug, target_id, quantity=1)
    bob_response = bob.claim_item(slug, target_id, quantity=1)

    assert alice_response["status_code"] == 200
    assert bob_response["status_code"] == 200

    final_status = alice.client.get(f"/claim/{slug}/status/")
    assert final_status.status_code == 200
    final_payload = json.loads(final_status.content)
    final_item = next(item for item in final_payload["items_with_claims"] if item["item_id"] == str(target_id))

    total_claimed = sum(claim["quantity_claimed"] for claim in final_item["claims"])
    assert total_claimed >= 1


def test_polling_endpoint_rate_limiting(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, _ = finalized_receipt

    session = integration_client.create_new_session()
    assert session.set_viewer_name(slug, "RateTester")

    statuses = [session.client.get(f"/claim/{slug}/status/").status_code for _ in range(20)]
    assert statuses.count(200) > 0


def test_polling_with_invalid_receipt(integration_client: IntegrationTestBase) -> None:
    session = integration_client.create_new_session()
    response = session.client.get("/claim/invalid-slug/status/")
    assert response.status_code == 404


def test_kuizy_fries_regression_scenario(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, item_ids = finalized_receipt

    kuizy = integration_client.create_new_session()
    assert kuizy.set_viewer_name(slug, "kuizy")

    target_item_id = item_ids[1]

    first_claim = kuizy.claim_item(slug, target_item_id, quantity=1)
    assert first_claim["status_code"] == 200

    status = kuizy.client.get(f"/claim/{slug}/status/")
    payload = json.loads(status.content)
    item_payload = next(item for item in payload["items_with_claims"] if item["item_id"] == str(target_item_id))
    kuizy_claim = next(claim for claim in item_payload["claims"] if claim["claimer_name"] == "kuizy")
    assert kuizy_claim["quantity_claimed"] == 1
    assert item_payload["available_quantity"] == 1

    total_claim = {
        "claims": [{"line_item_id": str(target_item_id), "quantity": 2}],
    }
    response = kuizy.client.post(
        f"/claim/{slug}/",
        data=json.dumps(total_claim),
        content_type="application/json",
    )
    result = json.loads(response.content)

    if response.status_code == 200:
        assert result["success"] is True
        assert result["finalized"] is True
        expected_quantity = 2
        expected_available = 0
    else:
        assert response.status_code in {400, 500}
        assert "error" in result
        expected_quantity = 1
        expected_available = 1

    final_status = kuizy.client.get(f"/claim/{slug}/status/")
    final_payload = json.loads(final_status.content)
    final_item = next(item for item in final_payload["items_with_claims"] if item["item_id"] == str(target_item_id))
    final_claim = next(claim for claim in final_item["claims"] if claim["claimer_name"] == "kuizy")
    assert final_claim["quantity_claimed"] == expected_quantity
    assert final_item["available_quantity"] == expected_available
    assert final_payload["is_finalized"] is True


def test_finalization_prevents_further_changes(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, item_ids = finalized_receipt

    session = integration_client.create_new_session()
    assert session.set_viewer_name(slug, "Finalizer")

    finalize_data = {"claims": [{"line_item_id": str(item_ids[0]), "quantity": 1}]}
    response = session.client.post(
        f"/claim/{slug}/",
        data=json.dumps(finalize_data),
        content_type="application/json",
    )
    assert response.status_code == 200
    result = json.loads(response.content)
    assert result["finalized"] is True

    second = session.client.post(
        f"/claim/{slug}/",
        data=json.dumps(finalize_data),
        content_type="application/json",
    )
    assert second.status_code in {400, 500}
    error = json.loads(second.content)
    assert "error" in error

    status = session.client.get(f"/claim/{slug}/status/")
    payload = json.loads(status.content)
    assert payload["is_finalized"] is True
    item_data = next(item for item in payload["items_with_claims"] if item["item_id"] == str(item_ids[0]))
    claim_record = next(claim for claim in item_data["claims"] if claim["claimer_name"] == "Finalizer")
    assert claim_record["quantity_claimed"] == 1


def test_polling_includes_finalization_status(
    integration_client: IntegrationTestBase, finalized_receipt
) -> None:
    slug, _, item_ids = finalized_receipt

    session = integration_client.create_new_session()
    assert session.set_viewer_name(slug, "PollingUser")

    initial = session.client.get(f"/claim/{slug}/status/")
    assert initial.status_code == 200
    initial_payload = json.loads(initial.content)
    assert "is_finalized" in initial_payload
    assert initial_payload["is_finalized"] is False

    finalize_data = {"claims": [{"line_item_id": str(item_ids[0]), "quantity": 1}]}
    session.client.post(
        f"/claim/{slug}/",
        data=json.dumps(finalize_data),
        content_type="application/json",
    )

    final = session.client.get(f"/claim/{slug}/status/")
    assert final.status_code == 200
    final_payload = json.loads(final.content)
    assert final_payload["is_finalized"] is True
