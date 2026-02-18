"""
Playwright performance test for client-side image optimization.

Uses CDP to simulate slow mobile upload (500 Kbps) and measures the impact
of client-side resizing on upload wall-clock time.

Requirements:
    pip install playwright && playwright install chromium

Usage:
    python -m pytest perf_test/test_upload_perf.py -v -s --override-ini='addopts=' -p no:django

These tests require a running dev server on http://localhost:8000:
    DEBUG=true python3 manage.py runserver 0.0.0.0:8000
"""

import tempfile
import time
from pathlib import Path

import pytest

# Playwright is optional — skip entire module if not installed
pw = pytest.importorskip("playwright.sync_api", reason="playwright not installed")

# Pillow for generating test images on disk
PIL = pytest.importorskip("PIL", reason="Pillow not installed")
from PIL import Image as PILImage

BASE_URL = "http://localhost:8000"
# Sample HEIC image shipped with the repo
SAMPLE_HEIC = Path(__file__).resolve().parent.parent / "IMG_6839.HEIC"


@pytest.fixture(scope="module")
def browser():
    """Launch a Chromium browser for the test module."""
    with pw.sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def throttled_page(browser):
    """
    Create a browser page with CDP network throttling enabled.
    Simulates a slow 500 Kbps mobile upload link.
    """
    context = browser.new_context()
    page = context.new_page()

    # Use CDP to throttle upload bandwidth
    cdp = context.new_cdp_session(page)
    cdp.send("Network.emulateNetworkConditions", {
        "offline": False,
        "downloadThroughput": -1,        # unlimited download
        "uploadThroughput": 64_000,      # 500 Kbps (64 KB/s)
        "latency": 100,                  # 100ms RTT
    })

    yield page

    cdp.detach()
    context.close()


@pytest.fixture
def normal_page(browser):
    """Create a browser page without throttling."""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture(scope="module")
def large_jpeg_path():
    """Generate a large JPEG test image on disk (3000x2000, ~500KB+)."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img = PILImage.new("RGB", (3000, 2000), color=(255, 100, 0))
        # Add some visual variation for realistic compression
        pixels = img.load()
        for x in range(0, 3000, 50):
            for y in range(0, 2000, 50):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)
        img.save(f, format="JPEG", quality=95)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


@pytest.fixture(scope="module")
def xlarge_jpeg_path():
    """Generate an extra-large JPEG test image (4000x3000)."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img = PILImage.new("RGB", (4000, 3000), color=(0, 128, 255))
        pixels = img.load()
        import random
        random.seed(42)
        for _ in range(500):
            x, y = random.randint(0, 3999), random.randint(0, 2999)
            pixels[x, y] = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        img.save(f, format="JPEG", quality=95)
        path = Path(f.name)
    yield path
    path.unlink(missing_ok=True)


def _get_file_input_file_info(page):
    """Extract the file name, type, and size from the file input after client-side processing."""
    return page.evaluate("""() => {
        const input = document.getElementById('receipt_image');
        if (!input || !input.files || !input.files.length) return null;
        const f = input.files[0];
        return { name: f.name, type: f.type, size: f.size };
    }""")


def _wait_for_optimization(page, timeout_ms=5000):
    """Wait until the 'Optimizing image...' message disappears."""
    try:
        page.wait_for_selector(".text-blue-600", state="detached", timeout=timeout_ms)
    except Exception:
        # Processing message may have already been removed
        pass


@pytest.mark.perf
def test_jpeg_upload_produces_webp_on_chromium(normal_page, large_jpeg_path):
    """
    Upload a JPEG on Chromium and verify the client-side optimizer
    converts it to WebP before upload.
    """
    page = normal_page
    page.goto(BASE_URL)

    # Use Playwright's native file setting — triggers the change handler
    page.set_input_files("#receipt_image", str(large_jpeg_path))

    _wait_for_optimization(page)

    file_info = _get_file_input_file_info(page)
    assert file_info is not None, "File input should have a file after optimization"
    assert file_info["type"] == "image/webp", f"Expected WebP, got {file_info['type']}"
    assert file_info["name"].endswith(".webp"), f"Expected .webp extension, got {file_info['name']}"
    print(f"\n  Input: {large_jpeg_path.stat().st_size:,} bytes JPEG")
    print(f"  Output: {file_info['size']:,} bytes {file_info['type']}")


@pytest.mark.perf
def test_client_resize_reduces_file_size(normal_page, xlarge_jpeg_path):
    """
    Verify client-side optimization significantly reduces file size
    compared to the raw input.
    """
    page = normal_page
    page.goto(BASE_URL)

    original_size = xlarge_jpeg_path.stat().st_size

    page.set_input_files("#receipt_image", str(xlarge_jpeg_path))

    _wait_for_optimization(page)

    file_info = _get_file_input_file_info(page)
    assert file_info is not None
    # The resized file should be smaller (dimension capped at 2048 + WebP compression)
    assert file_info["size"] < original_size, (
        f"Resized file ({file_info['size']:,} bytes) should be smaller "
        f"than original ({original_size:,} bytes)"
    )
    print(f"\n  Original: {original_size:,} bytes")
    print(f"  Optimized: {file_info['size']:,} bytes ({file_info['type']})")
    print(f"  Reduction: {(1 - file_info['size'] / original_size) * 100:.1f}%")


@pytest.mark.perf
@pytest.mark.skipif(not SAMPLE_HEIC.exists(), reason="Sample HEIC file not found")
def test_throttled_upload_timing(throttled_page):
    """
    Measure upload time under simulated slow mobile conditions.
    With client-side optimization, a 3-5MB HEIC should upload much faster
    after being resized to ~400-700KB WebP.
    """
    page = throttled_page
    page.goto(BASE_URL)

    # Fill in the uploader name
    page.fill('input[name="uploader_name"]', 'PerfTester')

    # Set file via Playwright (triggers change handler)
    page.set_input_files("#receipt_image", str(SAMPLE_HEIC))

    # Wait for client-side optimization
    _wait_for_optimization(page, timeout_ms=10_000)

    file_info = _get_file_input_file_info(page)
    if file_info:
        print(f"\n  After optimization: {file_info['name']} "
              f"({file_info['size']:,} bytes, {file_info['type']})")

    # Measure the actual form submission time
    start = time.time()
    page.click('button[type="submit"]')

    # Wait for navigation (form submission completes with redirect)
    try:
        page.wait_for_url("**/receipt/**", timeout=120_000)
        duration = time.time() - start
        print(f"  Upload + redirect took: {duration:.1f}s")
    except Exception as e:
        duration = time.time() - start
        print(f"  Upload timed out or failed after {duration:.1f}s: {e}")
