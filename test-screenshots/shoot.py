#!/usr/bin/env python3
"""Headless screenshot of index.html for visual texture verification."""
import sys
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
INDEX = HERE.parent / "index.html"

async def main(out_name: str):
    out_path = HERE / out_name
    url = f"file://{INDEX}"
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        page = await ctx.new_page()
        await page.goto(url)
        # Wait long enough for fonts, scene, textures, bloom warm-up.
        await page.wait_for_timeout(2500)
        await page.screenshot(path=str(out_path), full_page=False)
        await browser.close()
    print(f"saved {out_path}")

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "shot.png"
    asyncio.run(main(name))
