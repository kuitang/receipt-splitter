"""Pytest fixtures for integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Generator, Tuple

import pytest

from integration_test.base_test import IntegrationTestBase
from integration_test.mock_ocr import patch_ocr_for_tests


@pytest.fixture(scope="session", autouse=True)
def patch_mock_ocr() -> Generator[None, None, None]:
    """Ensure the mocked OCR pipeline is active for the full test session."""
    patches = patch_ocr_for_tests()
    for patch in patches:
        patch.start()
    try:
        yield
    finally:
        for patch in reversed(patches):
            patch.stop()


@pytest.fixture
def integration_client(db) -> IntegrationTestBase:
    """Return a fresh integration test client for each test."""
    return IntegrationTestBase()


@pytest.fixture(scope="session")
def heic_fixture_bytes() -> bytes:
    """Provide the sample HEIC image shipped with the repository."""
    image_path = Path(__file__).resolve().parent.parent / "IMG_6839.HEIC"
    return image_path.read_bytes()


@pytest.fixture
def finalized_receipt(integration_client: IntegrationTestBase, db) -> Tuple[str, dict, list[int]]:
    """Create, balance, and finalize a receipt for claim-related tests."""
    slug, receipt_data, item_ids = _create_finalized_receipt(integration_client)
    return slug, receipt_data, item_ids


def _create_finalized_receipt(client: IntegrationTestBase) -> Tuple[str, dict, list[int]]:
    upload = client.upload_receipt("TestUploader")
    assert upload["status_code"] == 302, "Receipt upload should redirect"

    slug = upload["receipt_slug"]
    assert slug, "Slug should be returned after upload"

    assert client.wait_for_processing(slug), "Processing should complete for uploaded receipt"

    test_data = IntegrationTestBase.TestData.balanced_receipt()
    update = client.update_receipt(slug, test_data)
    assert update["status_code"] == 200, f"Expected 200, got {update['status_code']}"

    finalize = client.finalize_receipt(slug)
    assert finalize["status_code"] == 200, f"Expected 200, got {finalize['status_code']}"

    receipt_data = client.get_receipt_data(slug)
    assert receipt_data, "Receipt data should be retrievable after finalization"

    item_ids = [item["id"] for item in receipt_data["items"]]
    return slug, receipt_data, item_ids
