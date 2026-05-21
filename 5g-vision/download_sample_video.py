import urllib.request
import os
import sys

OUTPUT_FILE = "site_camera_01.mp4"

# Verified-live public-domain MP4s (checked 2026-04-17).
CANDIDATE_URLS = [
    "https://www.w3schools.com/html/mov_bbb.mp4",                          # ~770 KB, always live
    "https://media.w3schools.com/mov/mov_bbb.mp4",                         # mirror
    "https://www.learningcontainer.com/wp-content/uploads/2020/05/sample-mp4-file.mp4",
]

def download_video(url: str, dest: str) -> bool:
    print(f"Trying: {url}")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response, open(dest, "wb") as f:
            total = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            chunk = 65536
            while True:
                block = response.read(chunk)
                if not block:
                    break
                f.write(block)
                downloaded += len(block)
                if total:
                    print(f"  {downloaded / total * 100:.1f}%", end="\r")
        print(f"\nSaved '{dest}' ({downloaded / 1024 / 1024:.1f} MB).")
        return True
    except Exception as exc:
        print(f"  Failed: {exc}")
        if os.path.exists(dest):
            os.remove(dest)
        return False

if __name__ == "__main__":
    if os.path.exists(OUTPUT_FILE):
        print(f"'{OUTPUT_FILE}' already exists, skipping download.")
        sys.exit(0)
    for url in CANDIDATE_URLS:
        if download_video(url, OUTPUT_FILE):
            sys.exit(0)
    print("All candidate URLs failed. Check your internet connection.")
    sys.exit(1)
