"""
Visual verification test for the aged-metal texture on the demolate logo.

Renders index.html in headless chromium, samples pixel colors from the
central logo area, and asserts the texture reads as "aged worn dark metal
with a hint of rust" (ref2 aesthetic) rather than the current rust-dominated
surface (ref1 aesthetic).

Heuristics derived from the brief:
- Dominant tone is DARK gray/charcoal, NOT orange and NOT bright silver.
- Orange/brown rust pixels cover <= 8% of the logo surface.
- Mean luminance sits in the dark-iron band (roughly 35..110 on 0..255).
- Mean saturation is low (worn metal, not vivid rust).

Run:
    pip install playwright pillow pytest
    playwright install chromium
    pytest tests/test_texture_appearance.py -v
"""

from __future__ import annotations

import colorsys
import http.server
import os
import socket
import socketserver
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_HTML = PROJECT_ROOT / "index.html"
SCREENSHOT_DIR = PROJECT_ROOT / "test-screenshots"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args, **_kwargs):  # silence access log
        return


@pytest.fixture(scope="module")
def static_server():
    """Serve the project root over HTTP so the page can load assets."""
    port = _free_port()
    cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)
    httpd = socketserver.TCPServer(("127.0.0.1", port), _QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/index.html"
    finally:
        httpd.shutdown()
        httpd.server_close()
        os.chdir(cwd)


@pytest.fixture(scope="module")
def rendered_screenshot(static_server):
    """Render the page, wait for the texture to settle, save a screenshot."""
    playwright = pytest.importorskip("playwright.sync_api")
    SCREENSHOT_DIR.mkdir(exist_ok=True)
    out_path = SCREENSHOT_DIR / "texture_check.png"

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        page.goto(static_server, wait_until="networkidle")
        # Let the entry animation finish and the texture render fully.
        page.wait_for_timeout(2500)
        page.screenshot(path=str(out_path), full_page=False)
        browser.close()

    return out_path


def _sample_logo_pixels(image_path: Path):
    """Return list of (r,g,b) tuples for non-background pixels in the
    central logo region of the screenshot."""
    pytest.importorskip("PIL", reason="Pillow required")
    from PIL import Image  # module, not class — Image.open lives on the module

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    # Sample the central 50% box — that's where the logo lives.
    x0, y0 = int(w * 0.25), int(h * 0.25)
    x1, y1 = int(w * 0.75), int(h * 0.75)
    crop = img.crop((x0, y0, x1, y1))

    pixels = []
    for r, g, b in crop.getdata():
        # Skip near-black background (logo metal is always > 25 in at least one channel).
        if r < 18 and g < 18 and b < 18:
            continue
        pixels.append((r, g, b))
    return pixels


def _classify(r: int, g: int, b: int):
    """Return (luminance_0_255, saturation_0_1, hue_deg_0_360)."""
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return l * 255.0, s, h * 360.0


def _is_orange_rust(r: int, g: int, b: int) -> bool:
    """A pixel reads as visible orange/brown rust if it has notable warm
    saturation in the orange hue band."""
    lum, sat, hue = _classify(r, g, b)
    return 10.0 <= hue <= 45.0 and sat >= 0.22 and lum >= 35.0


def test_texture_reads_as_aged_dark_metal(rendered_screenshot):
    """The logo surface should look like ref2 (dark aged iron with subtle
    warmth), not like ref1 (heavy orange rust) and not like ref3 (bright chrome).

    This test currently FAILS against the rust-heavy implementation in
    index.html; it will pass once the texture is re-tuned per the plan.
    """
    pixels = _sample_logo_pixels(rendered_screenshot)
    assert len(pixels) > 5000, (
        f"Logo region had only {len(pixels)} non-background pixels — "
        "screenshot may be blank or the camera framing changed."
    )

    # --- Compute aggregate stats ---
    n = len(pixels)
    sum_r = sum(p[0] for p in pixels)
    sum_g = sum(p[1] for p in pixels)
    sum_b = sum(p[2] for p in pixels)
    mean_r, mean_g, mean_b = sum_r / n, sum_g / n, sum_b / n

    mean_lum, mean_sat, mean_hue = _classify(int(mean_r), int(mean_g), int(mean_b))
    rust_ratio = sum(1 for p in pixels if _is_orange_rust(*p)) / n

    # --- Assertions (each carries a diagnostic message) ---

    # 1. Mean tone must be dark iron, not bright silver, not pitch black.
    assert 35.0 <= mean_lum <= 115.0, (
        f"Mean luminance {mean_lum:.1f} is outside the dark-iron band [35,115]. "
        f"Mean RGB=({mean_r:.0f},{mean_g:.0f},{mean_b:.0f}). "
        "Texture is either too bright (chrome) or too dark (void)."
    )

    # 2. Mean saturation must be low — worn metal is desaturated.
    assert mean_sat <= 0.18, (
        f"Mean saturation {mean_sat:.3f} is too high (>0.18). "
        f"Mean RGB=({mean_r:.0f},{mean_g:.0f},{mean_b:.0f}), hue={mean_hue:.0f}deg. "
        "Surface reads as colorful rather than worn-gray metal."
    )

    # 3. Color cast must be neutral or barely warm — not orange-dominated.
    # If average red exceeds average blue by a wide margin, the surface is
    # tinted orange overall (which is the current 'disgusting' state).
    warm_cast = mean_r - mean_b
    assert warm_cast <= 18.0, (
        f"Warm cast (mean_r - mean_b = {warm_cast:.1f}) exceeds 18. "
        f"Mean RGB=({mean_r:.0f},{mean_g:.0f},{mean_b:.0f}). "
        "Surface is too orange overall — reduce rust coverage / desaturate palette."
    )

    # 4. Visible rust coverage must stay subtle (<=8% per the brief).
    assert rust_ratio <= 0.08, (
        f"Rust pixel ratio {rust_ratio:.1%} exceeds 8% budget. "
        "Tighten the rust mask threshold and/or blend rust as a tint rather "
        "than a full color replacement."
    )
