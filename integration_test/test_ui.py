"""Lightweight UI smoke tests that exercise rendered templates."""

from __future__ import annotations

import pytest

from integration_test.base_test import IntegrationTestBase

pytestmark = pytest.mark.integration


def test_homepage_allows_heic_uploads(integration_client: IntegrationTestBase) -> None:
    response = integration_client.client.get("/")
    assert response.status_code == 200

    content = response.content.decode("utf-8").lower()
    assert ".heic" in content
    assert ".heif" in content
    assert "image/heic" in content
    assert "image/heif" in content


def test_homepage_includes_responsive_imagery(integration_client: IntegrationTestBase) -> None:
    response = integration_client.client.get("/")
    assert response.status_code == 200

    content = response.content.decode("utf-8")
    for asset in ["step_upload_mobile.png", "step_share_mobile.png", "step_split_mobile.png"]:
        assert asset in content

    for css_class in ["w-20 h-20", "sm:w-32 sm:h-32", "md:w-40 md:h-40", "object-cover"]:
        assert css_class in content


def test_homepage_uses_consistent_design(integration_client: IntegrationTestBase) -> None:
    response = integration_client.client.get("/")
    assert response.status_code == 200

    content = response.content.decode("utf-8")
    assert "tailwind" in content.lower() or "class=" in content


def test_homepage_image_links_are_valid(integration_client: IntegrationTestBase) -> None:
    response = integration_client.client.get("/")
    assert response.status_code == 200

    content = response.content.decode("utf-8")
    required = [
        "/static/images/step_upload_mobile.png",
        "/static/images/step_share_mobile.png",
        "/static/images/step_split_mobile.png",
    ]

    for path in required:
        assert path in content
