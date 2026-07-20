---
name: pixabay-downloader
description: Download audio files from Pixabay page URLs by extracting CDN links via Playwright browser automation. Use when the user needs to download royalty-free music or sound effects from Pixabay, especially when direct HTTP scraping is blocked by Cloudflare. Supports batch downloads from metadata JSON files or single URL downloads.
---

# Pixabay Audio Downloader

Download audio from Pixabay pages even when Cloudflare blocks simple HTTP requests.

## How It Works

Pixabay serves audio through CDN links embedded in page HTML. Simple `requests`/`urllib` scraping fails because Pixabay uses Cloudflare bot protection. This skill uses Playwright with stealth settings to load the real page in a headless browser and extract the actual audio CDN URL.

## Workflow

1. **Single download**: Run `scripts/pixabay_download.py --url <pixabay-page-url> --output <path>`
2. **Batch download from registry**: Point `scripts/pixabay_download.py` at a JSON metadata directory and episode path.

## Script Usage

```bash
# Download a single Pixabay track
python scripts/pixabay_download.py --url "https://pixabay.com/music/beats-lofi-instrumental-409202/" --output ./room_theme.mp3

# Batch download from dula-assets audio-registry to an episode
python scripts/pixabay_download.py --registry ./audio-registry --episode ./episodes/my_episode --try-download
```

## Requirements

- Python 3.8+
- `playwright` Python package (`pip install playwright`)
- Playwright browsers installed (`playwright install chromium`)

## Notes

- CDN links extracted from Pixabay are direct file URLs and can be downloaded with standard `urllib`.
- Some Pixabay URLs (especially SFX search pages) do not contain direct audio links; the script reports these as requiring manual download.
- Freesound and other platforms are not supported by the scraper and require manual download.
