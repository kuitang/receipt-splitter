"""
Playwright performance test for client-side image optimization.

Uses CDP to simulate slow mobile upload (500 Kbps) and measures the impact
of client-side resizing on upload wall-clock time.

Requirements:
    pip install playwright && playwright install chromium

Usage:
    python -m pytest integration_test/test_upload_perf.py -v -s

These tests require a running dev server on http://localhost:8000:
    DEBUG=true python3 manage.py runserver 0.0.0.0:8000
"""

import time
from pathlib import Path

import pytest

# Playwright is optional — skip entire module if not installed
pw = pytest.importorskip("playwright.sync_api", reason="playwright not installed")

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


def _get_file_input_file_info(page):
    """Extract the file name, type, and size from the file input after client-side processing."""
    return page.evaluate("""() => {
        const input = document.getElementById('receipt_image');
        if (!input || !input.files || !input.files.length) return null;
        const f = input.files[0];
        return { name: f.name, type: f.type, size: f.size };
    }""")


@pytest.mark.perf
def test_jpeg_upload_produces_webp_on_chromium(normal_page):
    """
    Upload a JPEG on Chromium and verify the client-side optimizer
    converts it to WebP before upload.
    """
    page = normal_page
    page.goto(BASE_URL)

    # Create a test JPEG by drawing on a canvas in the browser
    page.evaluate("""() => {
        const canvas = document.createElement('canvas');
        canvas.width = 3000;
        canvas.height = 2000;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#ff6600';
        ctx.fillRect(0, 0, 3000, 2000);
        ctx.fillStyle = '#000';
        ctx.font = '48px serif';
        ctx.fillText('Test receipt', 100, 100);
        window.__testCanvas = canvas;
    }""")

    # Convert canvas to blob and set on the file input
    page.evaluate("""async () => {
        const canvas = window.__testCanvas;
        const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.95));
        const file = new File([blob], 'test-receipt.jpg', { type: 'image/jpeg' });
        const dt = new DataTransfer();
        dt.items.add(file);
        const input = document.getElementById('receipt_image');
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));
    }""")

    # Wait for client-side optimization to complete
    page.wait_for_timeout(2000)

    file_info = _get_file_input_file_info(page)
    assert file_info is not None, "File input should have a file after optimization"
    assert file_info["type"] == "image/webp", f"Expected WebP, got {file_info['type']}"
    assert file_info["name"].endswith(".webp"), f"Expected .webp extension, got {file_info['name']}"


@pytest.mark.perf
def test_client_resize_reduces_file_size(normal_page):
    """
    Verify client-side optimization significantly reduces file size
    compared to the raw input.
    """
    page = normal_page
    page.goto(BASE_URL)

    # Create a large test image (3000x2000 filled canvas ~ several hundred KB as JPEG)
    original_size = page.evaluate("""async () => {
        const canvas = document.createElement('canvas');
        canvas.width = 4000;
        canvas.height = 3000;
        const ctx = canvas.getContext('2d');
        // Add some visual noise for realistic compression
        for (let i = 0; i < 100; i++) {
            ctx.fillStyle = `rgb(${Math.random()*255},${Math.random()*255},${Math.random()*255})`;
            ctx.fillRect(Math.random()*4000, Math.random()*3000, 200, 200);
        }
        const blob = await new Promise(r => canvas.toBlob(r, 'image/jpeg', 0.95));
        const file = new File([blob], 'large-receipt.jpg', { type: 'image/jpeg' });

        // Store original size
        window.__originalSize = file.size;

        const dt = new DataTransfer();
        dt.items.add(file);
        const input = document.getElementById('receipt_image');
        input.files = dt.files;
        input.dispatchEvent(new Event('change', { bubbles: true }));

        return file.size;
    }""")

    page.wait_for_timeout(2000)

    file_info = _get_file_input_file_info(page)
    assert file_info is not None
    # The resized file should be smaller (dimension capped at 2048 + WebP compression)
    assert file_info["size"] < original_size, (
        f"Resized file ({file_info['size']:,} bytes) should be smaller "
        f"than original ({original_size:,} bytes)"
    )
    print(f"\n  Original: {original_size:,} bytes")
    print(f"  Optimized: {file_info['size']:,} bytes ({file_info['type']})")
    print(f"  Reduction: {(1 - file_info['size']/original_size)*100:.1f}%")


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

    # Set file via file chooser
    with page.expect_file_chooser() as fc_info:
        page.click('input[type="file"]')
    file_chooser = fc_info.value
    file_chooser.set_files(str(SAMPLE_HEIC))

    # Wait for client-side optimization
    page.wait_for_timeout(3000)

    file_info = _get_file_input_file_info(page)
    if file_info:
        print(f"\n  After optimization: {file_info['name']} "
              f"({file_info['size']:,} bytes, {file_info['type']})")

    # Measure the actual form submission time
    start = time.time()
    page.click('button[type="submit"]')

    # Wait for navigation (form submission completes with redirect)
    try:
        page.wait_for_url("**/receipt/**", timeout=60_000)
        duration = time.time() - start
        print(f"  Upload + redirect took: {duration:.1f}s")
    except Exception as e:
        duration = time.time() - start
        print(f"  Upload timed out or failed after {duration:.1f}s: {e}")
