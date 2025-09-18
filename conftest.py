import os
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test.utils import get_runner, setup_test_environment, teardown_test_environment


def pytest_configure():
    os.environ.setdefault("SECRET_KEY", "test-secret")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "test_settings")
    os.environ.setdefault("USE_ASYNC_PROCESSING", "false")


def pytest_sessionstart(session):
    django.setup()
    setup_test_environment()
    test_runner_class = get_runner(settings)
    session._django_runner = test_runner_class(verbosity=1, interactive=False)
    session._django_db_cfg = session._django_runner.setup_databases()


def pytest_sessionfinish(session, exitstatus):
    runner = getattr(session, "_django_runner", None)
    db_cfg = getattr(session, "_django_db_cfg", None)
    if runner and db_cfg:
        runner.teardown_databases(db_cfg)
    teardown_test_environment()


def _sniff_mime_from_signature(file_content: bytes) -> str:
    signatures = (
        (b"\xff\xd8\xff", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "image/png"),
    )

    for magic_bytes, mime in signatures:
        if file_content.startswith(magic_bytes):
            return mime

    if file_content.startswith(b"RIFF") and file_content[8:12] == b"WEBP":
        return "image/webp"

    if b"ftyp" in file_content[:16]:
        box_type = file_content[file_content.find(b"ftyp") + 4:file_content.find(b"ftyp") + 8]
        if box_type in {b"heic", b"heix", b"hevc", b"mif1", b"heif"}:
            return "image/heic" if box_type in {b"heic", b"heix", b"hevc"} else "image/heif"

    raise ValidationError("Unable to determine file type.")


@pytest.fixture(autouse=True)
def _ensure_mime_detection(monkeypatch):
    from receipts import validators

    if validators.magic is not None:
        return

    def _detect(cls, file_content: bytes) -> str:
        return _sniff_mime_from_signature(file_content)

    monkeypatch.setattr(
        validators.FileUploadValidator,
        "_detect_mime_type",
        classmethod(_detect),
    )


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = Path(str(item.fspath))
        if "integration_test" in path.parts:
            item.add_marker("integration")
        else:
            item.add_marker("backend")
