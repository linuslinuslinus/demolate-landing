"""
Structural & budget tests for the rust-iron texture variant deliverable.

Verifies the plan's acceptance criteria that don't require pixel sampling:
- All 5 variant files exist
- Each variant file is <= 200 KB
- Each variant file is self-contained (no external PolyHaven texture fetches)
- done.json is valid JSON with the expected schema
- index.html matches the promoted variant (V4 per done.json)
- Variant label was removed from the promoted index.html
- Each variant renders without uncaught JS errors (Playwright smoke test)

Run:
    pytest tests/test_variants_and_budget.py -v
"""

from __future__ import annotations

import http.server
import json
import os
import socket
import socketserver
import threading
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VARIANT_FILES = [PROJECT_ROOT / f"index-v{i}.html" for i in range(1, 6)]
INDEX = PROJECT_ROOT / "index.html"
DONE = PROJECT_ROOT / "done.json"
SIZE_BUDGET_BYTES = 200_000


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args, **_kwargs):
        return


@pytest.fixture(scope="module")
def server_base():
    port = _free_port()
    cwd = os.getcwd()
    os.chdir(PROJECT_ROOT)
    httpd = socketserver.TCPServer(("127.0.0.1", port), _QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()
        os.chdir(cwd)


# ---------- Structural checks ----------

def test_all_five_variant_files_exist():
    missing = [p.name for p in VARIANT_FILES if not p.exists()]
    assert not missing, f"Missing variant files: {missing}"


@pytest.mark.parametrize("variant_path", VARIANT_FILES, ids=lambda p: p.name)
def test_variant_within_size_budget(variant_path: Path):
    size = variant_path.stat().st_size
    assert size <= SIZE_BUDGET_BYTES, (
        f"{variant_path.name} is {size} bytes, exceeds {SIZE_BUDGET_BYTES} byte budget"
    )


@pytest.mark.parametrize("variant_path", VARIANT_FILES, ids=lambda p: p.name)
def test_variant_has_no_external_texture_fetch(variant_path: Path):
    """Variants must use procedural canvas textures — no PolyHaven CDN calls
    or any other external image texture loads."""
    text = variant_path.read_text()
    # PolyHaven was the previous external source.
    assert "polyhaven" not in text.lower(), (
        f"{variant_path.name} still references polyhaven texture URLs"
    )
    # TextureLoader fetches images by URL — the variants must use CanvasTexture only.
    assert "TextureLoader" not in text, (
        f"{variant_path.name} still uses THREE.TextureLoader (should be CanvasTexture only)"
    )
    assert "CanvasTexture" in text, (
        f"{variant_path.name} does not appear to use THREE.CanvasTexture"
    )


@pytest.mark.parametrize("variant_path", VARIANT_FILES, ids=lambda p: p.name)
def test_variant_has_makeRustIronTexture(variant_path: Path):
    text = variant_path.read_text()
    assert "makeRustIronTexture" in text, (
        f"{variant_path.name} missing makeRustIronTexture entry point"
    )


@pytest.mark.parametrize("variant_path", VARIANT_FILES, ids=lambda p: p.name)
def test_variant_does_not_set_needsUpdate_in_animation_loop(variant_path: Path):
    """Static procedural textures should not be regenerated per frame."""
    text = variant_path.read_text()
    # Cheap heuristic: there shouldn't be any 'needsUpdate = true' on map/aoMap/roughnessMap.
    # (A single needsUpdate after init is theoretically ok, but our variants don't need any.)
    forbidden = ["map.needsUpdate", "roughnessMap.needsUpdate", "aoMap.needsUpdate"]
    hits = [s for s in forbidden if s in text]
    assert not hits, (
        f"{variant_path.name} mutates texture.needsUpdate at runtime: {hits}"
    )


# ---------- done.json schema ----------

def test_done_json_valid():
    assert DONE.exists(), "done.json missing"
    data = json.loads(DONE.read_text())
    assert "winner" in data and data["winner"], "done.json missing winner"
    assert "variants" in data and len(data["variants"]) == 5, (
        "done.json should list 5 variants"
    )
    files = {v["file"] for v in data["variants"]}
    expected = {f"index-v{i}.html" for i in range(1, 6)}
    assert files == expected, f"done.json variant files mismatch: {files} vs {expected}"


# ---------- Promotion check: index.html matches the declared winner ----------

def test_index_matches_promoted_winner():
    data = json.loads(DONE.read_text())
    winner_path = PROJECT_ROOT / data["winner"]
    assert winner_path.exists(), f"declared winner {data['winner']} not found"

    # The promoted index.html should contain the same makeRustIronTexture body
    # as the winning variant. We compare the function definition region as a
    # stable substring rather than the full file (label/watermark differs).
    winner_text = winner_path.read_text()
    index_text = INDEX.read_text()

    # Extract the makeRustIronTexture function from the winner and check it's in index.
    start = winner_text.find("function makeRustIronTexture")
    assert start >= 0, "winner has no makeRustIronTexture function"
    # Grab a healthy chunk (first 600 chars) of the function as a fingerprint.
    fingerprint = winner_text[start : start + 600]
    assert fingerprint in index_text, (
        "index.html does not contain the promoted winner's makeRustIronTexture body"
    )


def test_index_has_no_variant_label():
    """The variant watermark (e.g. 'V4') should be stripped from the promoted index."""
    index_text = INDEX.read_text()
    # The plan specified a fixed-position label in the bottom-right.
    # We check that none of the V1..V5 variant labels survive as a positioned label.
    # Look for the label DOM pattern that the variants use.
    suspicious = []
    for tag in ("'V1'", "'V2'", "'V3'", "'V4'", "'V5'", '"V1"', '"V2"', '"V3"', '"V4"', '"V5"'):
        # Allow incidental mentions but flag if it appears near 'position' or 'fixed'.
        idx = index_text.find(tag)
        if idx >= 0:
            window = index_text[max(0, idx - 200) : idx + 200]
            if "position" in window or "fixed" in window or "bottom" in window:
                suspicious.append(tag)
    assert not suspicious, (
        f"index.html still appears to render a variant label watermark: {suspicious}"
    )


# ---------- Runtime smoke: each variant loads without console errors ----------

@pytest.mark.parametrize("variant_path", VARIANT_FILES, ids=lambda p: p.name)
def test_variant_renders_without_console_errors(server_base, variant_path: Path):
    playwright = pytest.importorskip("playwright.sync_api")

    url = f"{server_base}/{variant_path.name}"
    errors: list[str] = []

    with playwright.sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1024, "height": 640})
        page = context.new_page()
        page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
        page.on(
            "console",
            lambda msg: errors.append(f"console.{msg.type}: {msg.text}")
            if msg.type == "error"
            else None,
        )
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(1500)
        browser.close()

    # Ignore noisy 404s for things like favicon that aren't variant bugs.
    real_errors = [
        e for e in errors if "favicon" not in e.lower() and "404" not in e
    ]
    assert not real_errors, f"{variant_path.name} had errors:\n" + "\n".join(real_errors)
