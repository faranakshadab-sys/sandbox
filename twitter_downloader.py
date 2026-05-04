#!/usr/bin/env python3
import subprocess
import json
import sys
from pathlib import Path
from typing import List, Optional

OUTPUT_FILE = Path("twitter_download_links.txt")


def normalize_tweet_url(url: str) -> str:
    """
    Normalize x.com URLs to twitter.com for yt-dlp compatibility.
    """
    url = url.strip()
    if url.startswith("https://x.com/"):
        url = url.replace("https://x.com/", "https://twitter.com/", 1)
    elif url.startswith("http://x.com/"):
        url = url.replace("http://x.com/", "https://twitter.com/", 1)
    return url


def run_yt_dlp_json(args: List[str]) -> Optional[dict]:
    """
    Run yt-dlp with JSON output and return parsed JSON or None on failure.
    """
    cmd = ["yt-dlp", "-J"] + args
    try:
        print(f"[DEBUG] Running: {' '.join(cmd)}", file=sys.stderr)
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        print("[ERROR] yt-dlp failed.", file=sys.stderr)
        print("[ERROR] Command:", " ".join(cmd), file=sys.stderr)
        print("[ERROR] Stderr:", e.stderr, file=sys.stderr)
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        print("[ERROR] Failed to parse yt-dlp JSON:", str(e), file=sys.stderr)
        return None


def pick_best_format(data: dict) -> Optional[str]:
    """
    Given yt-dlp JSON data, try to pick the highest quality video URL.
    """
    # 1. If 'url' present at root (simple case)
    if "url" in data and isinstance(data["url"], str):
        return data["url"]

    formats = data.get("formats") or []
    if not formats:
        print("[WARN] No formats found in yt-dlp JSON.", file=sys.stderr)
        return None

    def sort_key(f):
        height = f.get("height") or 0
        tbr = f.get("tbr") or 0
        return (height, tbr)

    best_format = max(formats, key=sort_key)
    url = best_format.get("url")
    if not url:
        print("[WARN] Best format has no 'url' field.", file=sys.stderr)
        return None

    return url


def get_video_url(tweet_url: str) -> Optional[str]:
    """
    Returns the highest-quality video download URL for a given Tweet/X URL.
    Tries a couple of strategies with yt-dlp.
    """
    normalized_url = normalize_tweet_url(tweet_url)
    print(f"[INFO] Normalized URL: {normalized_url}")

    # Strategy 1: Let yt-dlp pick best format itself
    data = run_yt_dlp_json(["-f", "best", normalized_url])
    if data:
        url = pick_best_format(data)
        if url:
            return url
        else:
            print("[INFO] Strategy 1 (best) failed to find URL.", file=sys.stderr)

    # Strategy 2: Try explicit video+audio selection
    data = run_yt_dlp_json(["-f", "bv*+ba/b", normalized_url])
    if data:
        url = pick_best_format(data)
        if url:
            return url
        else:
            print("[INFO] Strategy 2 (bv*+ba/b) failed to find URL.", file=sys.stderr)

    print("[ERROR] No downloadable video URL found for this tweet.", file=sys.stderr)
    return None


def load_tweet_urls_from_args() -> List[str]:
    """
    Read tweet URLs either from command line args or stdin.
    """
    if len(sys.argv) > 1:
        return sys.argv[1:]

    return [line.strip() for line in sys.stdin if line.strip()]


def main():
    tweet_urls = load_tweet_urls_from_args()
    if not tweet_urls:
        print("Usage:", file=sys.stderr)
        print("  python get_twitter_video_links.py <tweet_url_1> <tweet_url_2> ...", file=sys.stderr)
        print("or pass URLs via stdin, one per line.", file=sys.stderr)
        sys.exit(1)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []

    for tweet_url in tweet_urls:
        print(f"[INFO] Processing: {tweet_url}")
        video_url = get_video_url(tweet_url)
        if video_url:
            line = f"{tweet_url}\t{video_url}"
            lines.append(line)
            print(f"[OK] Found download URL: {video_url}")
        else:
            print(f"[FAIL] No video URL found for {tweet_url}", file=sys.stderr)
    old_content = OUTPUT_FILE.read_text()
    OUTPUT_FILE.write_text(
        f'{old_content},{",".join(lines)}', encoding="utf-8")
    print(f"\n[INFO] Saved {len(lines)} link(s) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
