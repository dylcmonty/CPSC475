"""Download County Line Produce Auction market reports (PDF).

The auction posts one PDF per sale day on a page per season at
countylineproduceauction.com/reports/<year>. Files are saved to
data/raw/county_line/; ones already downloaded are skipped. The sale
date is read from inside each PDF when the data is built, not from
the file name.

Usage:
    python loaders/fetch_county_line.py
"""
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

PAGE = "https://www.countylineproduceauction.com/reports/{year}"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "county_line"
PDF_LINK = re.compile(r'href="(https://[^"]+\.pdf)"', re.I)
FIRST_YEAR = 2024


def get(url, tries=4):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Almanac class project)"})
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
    saved = skipped = 0
    for year in range(FIRST_YEAR, date.today().year + 1):
        try:
            html = get(PAGE.format(year=year)).decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            print(f"{year}: no report page ({err.code})")
            continue
        links = sorted(set(PDF_LINK.findall(html)))
        for url in links:
            name = urllib.parse.unquote(url.rsplit("/", 1)[1])
            target = OUT / name.replace(" ", "_").replace(",", "")
            if target.exists():
                skipped += 1
                continue
            target.write_bytes(get(url))
            saved += 1
            time.sleep(0.2)
        print(f"{year}: {len(links)} reports")
    print(f"Saved {saved} new reports, {skipped} already here, in {OUT}")


if __name__ == "__main__":
    main()
