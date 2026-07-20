#!/usr/bin/env python3
"""
Pixabay Audio Downloader

Downloads audio files from Pixabay by scraping CDN links with Playwright.
Works around Cloudflare bot protection that blocks simple HTTP requests.

Usage:
    python pixabay_download.py --url <pixabay-page-url> --output <file.mp3>
    python pixabay_download.py --registry <registry-dir> --episode <episode-dir> --try-download
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path


def extract_pixabay_cdn(page_url, timeout=30):
    """
    Use Playwright to load a Pixabay page and extract the CDN audio URL.
    Returns the CDN URL string, or None if extraction fails.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Error: Playwright not installed. Run: pip install playwright && playwright install chromium")
        return None

    cdn_url = None
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        )
        page = context.new_page()
        try:
            page.goto(page_url, wait_until="load", timeout=timeout * 1000)
            page.wait_for_timeout(2000)
            html = page.content()
            matches = list(
                set(re.findall(r'https?://cdn\.pixabay\.com/[^\s"\'<>]+', html))
            )
            audio_exts = (".mp3", ".wav", ".ogg", ".flac")
            audio_matches = [m for m in matches if any(ext in m.lower() for ext in audio_exts)]
            if audio_matches:
                cdn_url = audio_matches[0]
        except Exception as e:
            print(f"Playwright error: {e}")
        finally:
            browser.close()

    return cdn_url


def download_file(url, dest, timeout=60):
    """Download a file from URL to dest path. Returns (ok, message)."""
    dest = Path(dest)
    if dest.exists():
        return True, "already exists"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                f.write(response.read())
        return True, f"downloaded ({dest.stat().st_size} bytes)"
    except Exception as e:
        return False, f"download failed: {e}"


def download_from_pixabay(page_url, dest, timeout=30):
    """Full pipeline: extract CDN link from Pixabay page, then download it."""
    print(f"Extracting CDN link from {page_url} ...")
    cdn_url = extract_pixabay_cdn(page_url, timeout=timeout)
    if not cdn_url:
        return False, "failed to extract Pixabay CDN link"
    print(f"CDN link: {cdn_url[:100]}...")
    return download_file(cdn_url, dest, timeout=timeout)


def load_registry(registry_dir):
    """Load all metadata JSON files from bgm/, ambient/, sfx/ subdirectories."""
    registry_dir = Path(registry_dir)
    registry = {"bgm": [], "ambient": [], "sfx": []}
    for category in registry:
        cat_dir = registry_dir / category
        if not cat_dir.exists():
            continue
        for json_file in sorted(cat_dir.glob("*.json")):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                registry[category].append(data)
    return registry


def generate_plan(episode_path, registry, scenes=None):
    """Generate a download plan for the episode."""
    episode_dir = Path(episode_path)
    audio_dir = episode_dir / "materials" / "audio"
    sfx_dir = episode_dir / "materials" / "sfx"
    bgm_dir = episode_dir / "materials" / "bgm"

    audio_dir.mkdir(parents=True, exist_ok=True)
    sfx_dir.mkdir(parents=True, exist_ok=True)
    bgm_dir.mkdir(parents=True, exist_ok=True)

    if scenes:
        scene_set = set(s.strip() for s in scenes.split(","))
        filtered = {"bgm": [], "ambient": [], "sfx": []}
        for category, items in registry.items():
            for item in items:
                item_scenes = set(item.get("suggested_scenes", []))
                if item_scenes & scene_set:
                    filtered[category].append(item)
        registry = filtered

    plan = []
    for category, items in registry.items():
        for item in items:
            if category == "bgm":
                dest = bgm_dir / item["local_filename"]
            elif category == "ambient":
                dest = audio_dir / item["local_filename"]
            else:
                dest = sfx_dir / item["local_filename"]

            exists = dest.exists()
            primary_source = item.get("sources", [{}])[0]
            plan.append({
                "name": item["name"],
                "category": category,
                "local_path": str(dest),
                "exists": exists,
                "source_url": primary_source.get("url", ""),
                "platform": primary_source.get("platform", ""),
            })
    return plan


def main():
    parser = argparse.ArgumentParser(description="Pixabay audio downloader")
    parser.add_argument("--url", help="Single Pixabay page URL to download from")
    parser.add_argument("--output", help="Output file path for single download")
    parser.add_argument("--registry", help="Path to audio-registry directory")
    parser.add_argument("--episode", help="Path to episode directory for batch download")
    parser.add_argument("--scene", help="Comma-separated scene names to filter by")
    parser.add_argument("--try-download", action="store_true", help="Attempt automatic downloads")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds")
    args = parser.parse_args()

    # Single download mode
    if args.url:
        if not args.output:
            print("Error: --output is required when using --url")
            sys.exit(1)
        ok, msg = download_from_pixabay(args.url, args.output, timeout=args.timeout)
        print(msg)
        sys.exit(0 if ok else 1)

    # Batch mode
    if args.registry and args.episode:
        if not Path(args.registry).exists():
            print(f"Error: Registry path does not exist: {args.registry}")
            sys.exit(1)
        if not Path(args.episode).exists():
            print(f"Error: Episode path does not exist: {args.episode}")
            sys.exit(1)

        registry = load_registry(args.registry)
        plan = generate_plan(args.episode, registry, scenes=args.scene)

        print(f"Plan: {len(plan)} assets")
        missing = sum(1 for p in plan if not p["exists"])
        print(f"  Missing: {missing}")
        print(f"  Present: {len(plan) - missing}")

        if args.try_download and missing > 0:
            print("\nAttempting downloads...")
            for p in plan:
                if p["exists"]:
                    continue
                if p["platform"].lower() == "pixabay" and "pixabay.com" in p["source_url"]:
                    ok, msg = download_from_pixabay(p["source_url"], p["local_path"], timeout=args.timeout)
                else:
                    ok, msg = False, "unsupported platform -- manual download required"
                status = "OK" if ok else "SKIP"
                print(f"  [{status}] {p['name']}: {msg}")
        return

    print("Error: Either use --url + --output for single download, or --registry + --episode for batch.")
    sys.exit(1)


if __name__ == "__main__":
    main()
