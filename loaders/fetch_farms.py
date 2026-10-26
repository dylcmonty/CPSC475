"""Download Ohio farms and counties.

Farms are named farm stands, farm markets, farms and orchards mapped in
OpenStreetMap (data (c) OpenStreetMap contributors, ODbL). Each one's
county comes from the US Census geocoder. The list of Ohio's 88
counties comes from the Census Bureau's 2020 county code file. Results
are cached as JSON in data/raw/ for build_sqlite.py.

Usage:
    python loaders/fetch_farms.py
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
OVERPASS = "https://overpass-api.de/api/interpreter"
QUERY = """
[out:json][timeout:240];
area["ISO3166-2"="US-OH"]->.oh;
(
  nwr(area.oh)["shop"="farm"]["name"];
  nwr(area.oh)["place"="farm"]["name"];
  nwr(area.oh)["landuse"="orchard"]["name"];
);
out tags center;
"""
GEOCODER = ("https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
            "?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current"
            "&layers=Counties&format=json")
COUNTIES = "https://www2.census.gov/geo/docs/reference/codes2020/cou/st39_oh_cou2020.txt"


def fetch(url, data=None, tries=6):
    request = urllib.request.Request(url, data=data, headers={"User-Agent": "Almanac class project"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))     # Overpass answers 502 when busy


def main():
    with urllib.request.urlopen(COUNTIES, timeout=60) as response:
        lines = response.read().decode().splitlines()[1:]
    names = sorted(line.split("|")[4].removesuffix(" County") for line in lines if line.strip())
    (OUT / "ohio_counties.json").write_text(json.dumps(names, indent=1))
    print(f"{len(names)} Ohio counties")

    elements = fetch(OVERPASS, data=urllib.parse.urlencode({"data": QUERY}).encode())["elements"]
    farms = []
    for e in elements:
        point = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
        if point["lat"] is None:
            continue
        result = fetch(GEOCODER.format(lat=point["lat"], lon=point["lon"]))
        county = result["result"]["geographies"].get("Counties") or []
        if not county or county[0].get("STATE") != "39":
            continue                           # outside Ohio once geocoded
        tags = e["tags"]
        farms.append({
            "osm": f"{e['type']}/{e['id']}",
            "name": tags["name"],
            "county": county[0]["BASENAME"],
            "website": tags.get("website") or tags.get("contact:website"),
        })
        time.sleep(0.1)
    (OUT / "farms.json").write_text(json.dumps(farms, indent=1))
    print(f"{len(farms)} farms from OpenStreetMap")


if __name__ == "__main__":
    main()
