"""Download every USDA AMS Mount Hope, Ohio auction report (AM_FV160).

The ESMIS archive at esmis.nal.usda.gov lists each weekly release with a
plain-text copy. Files are saved to data/raw/usda_mount_hope/ under the
archive's release id; ones already downloaded are skipped.

Usage:
    python loaders/fetch_usda.py
"""
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://esmis.nal.usda.gov"
LISTING = BASE + "/publication/mount-hope-ohio-auction?page={page}"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "usda_mount_hope"
# The newest report; the archive above lags behind it.
CURRENT = "https://www.ams.usda.gov/mnreports/am_fv160.txt"
LINK = re.compile(r'href="(/sites/default/release-files/pn89d6592/([^/]+)/[^/]+/AM_FV160\.TXT)"', re.I)


def get(url, tries=5):
    """Fetch a URL, retrying server errors; the archive often returns 502."""
    request = urllib.request.Request(url, headers={"User-Agent": "Almanac class project (University of Akron)"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as err:
            if isinstance(err, urllib.error.HTTPError) and err.code < 500:
                raise
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    page, saved, skipped, missing = 0, 0, 0, 0
    seen = set()
    while True:
        links = LINK.findall(get(LISTING.format(page=page)).decode("utf-8", "replace"))
        # Past the last page the archive repeats a page instead of ending.
        if not links or all(release in seen for _, release in links):
            break
        seen.update(release for _, release in links)
        for path, release in links:
            target = OUT / f"{release}.txt"
            if target.exists():
                skipped += 1
                continue
            try:
                target.write_bytes(get(BASE + path))
                saved += 1
            except urllib.error.HTTPError as err:
                print(f"  {release}: {err.code}, skipped")
                missing += 1
            time.sleep(0.3)
        print(f"page {page}: {len(links)} releases")
        page += 1

    current = get(CURRENT)
    stamp = re.search(rb"Prices[^\n]*?(\w+ \d{1,2}, \d{4})", current)
    name = "current-" + (stamp.group(1).decode().replace(" ", "-").replace(",", "") if stamp else "latest")
    (OUT / f"{name}.txt").write_bytes(current)
    print(f"Saved {saved} new reports, {skipped} already here, {missing} missing upstream, in {OUT}")


if __name__ == "__main__":
    main()
