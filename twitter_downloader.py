#!/usr/bin/env python3
import os
import subprocess
import json
import sys
from pathlib import Path
from typing import List

OUTPUT_FILE = Path("twitter_download_links.txt")


def get_video_url(tweet_url: str) -> str | None:
    """
    Returns the highest-quality video download URL for a given Tweet/X URL
    using yt-dlp in JSON mode.
    """
    try:
        # Run yt-dlp to get metadata as JSON
        # --no-warnings to keep output clean
        result = subprocess.run(
            [
                "yt-dlp",
                "-J",              # JSON output
                "-f", "bv*+ba/b",  # best video+audio, fallback to best
                tweet_url,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print(
            f"[ERROR] yt-dlp failed for {tweet_url}: {e.stderr}", file=sys.stderr)
        return None

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"[ERROR] Failed to parse JSON for {tweet_url}", file=sys.stderr)
        return None

    # Strategy:
    # 1. If 'url' present at root, use it
    # 2. Else, pick the best format (highest resolution) from 'formats'
    if "url" in data and isinstance(data["url"], str):
        return data["url"]

    formats = data.get("formats") or []
    if not formats:
        print(f"[WARN] No formats found for {tweet_url}", file=sys.stderr)
        return None

    # Sort by resolution/quality: prefer higher height, then higher bitrate
    def sort_key(f):
        # f.get("height") can be None, default to 0
        height = f.get("height") or 0
        # approximate bitrate
        tbr = f.get("tbr") or 0
        return (height, tbr)

    best_format = max(formats, key=sort_key)
    url = best_format.get("url")
    if not url:
        print(
            f"[WARN] Best format has no URL for {tweet_url}", file=sys.stderr)
        return None

    return url


def load_tweet_urls_from_args() -> List[str]:
    """
    Read tweet URLs either from command line args or stdin.
    - If args provided: use them.
    - Else: read lines from stdin (useful in CI).
    """
    if len(sys.argv) > 1:
        return sys.argv[1:]

    # Read from stdin
    urls = [line.strip() for line in sys.stdin if line.strip()]
    return urls


def main():
    tweet_urls = load_tweet_urls_from_args()
    if not tweet_urls:
        print("Usage:", file=sys.stderr)
        print("  python get_twitter_video_links.py <tweet_url_1> <tweet_url_2> ...", file=sys.stderr)
        print("or pass URLs via stdin, one per line.", file=sys.stderr)
        sys.exit(1)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Collect lines to write: "tweet_url<TAB>download_url"
    lines: List[str] = []

    for tweet_url in tweet_urls:
        print(f"[INFO] Processing: {tweet_url}")
        video_url = get_video_url(tweet_url)
        if video_url:
            line = f"{tweet_url}\t{video_url}"
            lines.append(line)
            print(f"[OK] Found: {video_url}")
        else:
            print(
                f"[FAIL] No video URL found for {tweet_url}", file=sys.stderr)

    # Write/overwrite the output file
    old_content = OUTPUT_FILE.read_text()
    OUTPUT_FILE.write_text(
        f'{old_content}\n{"\n".join(lines)}', encoding="utf-8")

    print(f"\n[INFO] Saved {len(lines)} link(s) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
