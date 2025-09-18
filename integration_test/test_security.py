"""Security-focused integration tests covering upload and input hardening."""

from __future__ import annotations

from typing import Iterable

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from integration_test.base_test import IntegrationTestBase

pytestmark = pytest.mark.integration


def _first_items(values: Iterable[str], count: int = 2) -> Iterable[str]:
    """Yield only the first ``count`` entries from ``values``."""

    for idx, value in enumerate(values):
        if idx >= count:
            break
        yield value


def test_input_validation_blocks_malicious_payloads(
    integration_client: IntegrationTestBase,
) -> None:
    """Uploads should sanitise or reject XSS/SQL injection attempts."""

    for payload in _first_items(IntegrationTestBase.TestData.xss_payloads()):
        response = integration_client.upload_receipt(
            uploader_name=payload,
            image_bytes=integration_client.create_test_image(50),
        )

        if response["status_code"] == 302:
            slug = response["receipt_slug"]
            assert slug
            assert integration_client.wait_for_processing(slug)
            data = integration_client.get_receipt_data(slug)
            assert "<script" not in (data or {}).get("uploader_name", "")
        else:
            assert response["status_code"] == 400

    upload = integration_client.upload_receipt("Input Validation Tester")
    slug = upload["receipt_slug"]
    assert slug
    assert integration_client.wait_for_processing(slug)

    for payload in _first_items(IntegrationTestBase.TestData.sql_injection_payloads()):
        payload_data = IntegrationTestBase.TestData.balanced_receipt()
        payload_data["restaurant_name"] = payload
        update = integration_client.update_receipt(slug, payload_data)
        assert update["status_code"] in {200, 400}


def test_file_upload_security_enforced(integration_client: IntegrationTestBase) -> None:
    """The upload endpoint should reject oversized or spoofed files."""

    oversized = IntegrationTestBase.TestData.oversized_data(11)
    response = integration_client.upload_receipt(
        "File Size Tester",
        image_bytes=oversized,
        filename="too_big.jpg",
    )
    assert response["status_code"] == 413

    php_payload = IntegrationTestBase.TestData.malicious_file_contents()["php_shell"]
    response = integration_client.upload_receipt(
        "PHP Payload",
        image_bytes=php_payload,
        filename="malicious.php",
    )
    assert response["status_code"] == 400

    fake_image = SimpleUploadedFile(
        "fake.jpg",
        php_payload,
        content_type="image/jpeg",
    )
    spoofed = integration_client.client.post(
        "/upload/",
        {"uploader_name": "Spoof Test", "receipt_image": fake_image},
    )
    assert spoofed.status_code == 400


def test_security_validation_rejects_non_images(
    integration_client: IntegrationTestBase,
) -> None:
    """libmagic-backed validation should refuse non-image payloads."""

    malicious_files = [
        (b"<script>alert(1)</script>", "xss.html"),
        (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>", "fake.pdf"),
    ]

    for content, filename in malicious_files:
        response = integration_client.upload_receipt(
            uploader_name=f"Malicious {filename}",
            image_bytes=content,
            filename=filename,
        )
        assert response["status_code"] == 400

    valid = integration_client.upload_receipt(
        uploader_name="Valid Magic Test",
        image_bytes=integration_client.create_test_image(500),
        filename="receipt.jpg",
    )
    assert valid["status_code"] in {302, 429}


@pytest.mark.skip(reason="Rate limiting disabled under test settings")
def test_upload_rate_limiting_is_enforced(
    integration_client: IntegrationTestBase,
) -> None:
    """Placeholder to document legacy rate limiting expectations."""

    successes = 0
    for index in range(20):
        response = integration_client.upload_receipt(
            uploader_name=f"Rate Test {index}",
            image_bytes=integration_client.create_test_image(100),
        )
        if response["status_code"] == 302:
            successes += 1
        elif response["status_code"] == 429:
            break

    assert successes > 0
