#!/usr/bin/env python3
"""Download a model file into the repo's models/ directory.

Usage:
    python scripts/download_model.py --url <MODEL_URL>

This will save the model to `models/object_detector.task` by default.
"""
import argparse
import sys
from pathlib import Path
from urllib.request import urlopen, Request


def download(url: str, out: Path):
    out.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "TangoPoseAnalyze-downloader/1.0"})
    with urlopen(req) as r, open(out, "wb") as f:
        total = r.getheader("Content-Length")
        if total is not None:
            total = int(total)
        downloaded = 0
        chunk_size = 8192
        while True:
            chunk = r.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                perc = downloaded * 100 / total
                print(f"\rDownloaded {downloaded}/{total} bytes ({perc:.1f}%)", end="")
        if total:
            print()


def main(argv=None):
    p = argparse.ArgumentParser(description="Download model into models/object_detector.task")
    p.add_argument("--url", required=True, help="HTTP(S) URL of the model file to download")
    p.add_argument("--out", default="models/object_detector.task", help="Output path (default: models/object_detector.task)")
    args = p.parse_args(argv)
    out = Path(args.out)
    try:
        print(f"Downloading {args.url} → {out}")
        download(args.url, out)
        print("Done.")
    except Exception as e:
        print("Download failed:", e)
        sys.exit(2)


if __name__ == "__main__":
    main()
