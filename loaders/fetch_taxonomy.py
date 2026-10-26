"""Download the plant taxonomy for the product lexicon from GBIF.

For each scientific name in products.PRODUCTS this asks the GBIF backbone
for its classification (kingdom down to species, and the subspecies or
variety when the product names one). Cultivar groups are not in GBIF;
their species is looked up instead. It also downloads:
  - for each genus reached, the accepted species that have an English
    common name, so the tree holds relatives such as wild garlic
    (Allium vineale) next to garlic;
  - for each species reached, its accepted subspecies, varieties and forms.
Results are cached as JSON in data/raw/gbif/ for build_sqlite.py.

Usage:
    python loaders/fetch_taxonomy.py
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from products import CULTIVAR_GROUPS, PRODUCTS

API = "https://api.gbif.org/v1"
BACKBONE = "d7dddbf4-2cf0-4f39-9b2a-bb099caae36c"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "gbif"
# Genus names shared by unrelated plants; the family picks the right one.
FAMILY_HINTS = {"Hosta": "Asparagaceae"}
INFRA_RANKS = {"SUBSPECIES": "subsp.", "VARIETY": "var.", "FORM": "f."}


def requested_rank(name):
    if " " not in name:
        return "GENUS"
    for rank, marker in INFRA_RANKS.items():
        if f" {marker} " in name:
            return rank
    return "SPECIES"


def get_json(path, **params):
    url = f"{API}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "Almanac class project"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4:
                raise
            time.sleep(2 ** attempt)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    names = {sci for _, sci, _ in PRODUCTS.values()}
    names = sorted((names - CULTIVAR_GROUPS.keys()) | set(CULTIVAR_GROUPS.values()))
    matches = {}
    for name in names:
        rank = requested_rank(name)
        hints = {"family": FAMILY_HINTS[name]} if name in FAMILY_HINTS else {"strict": "true"}
        m = get_json("species/match", name=name, kingdom="Plantae", rank=rank, **hints)
        # A synonym is fine (its classification is the accepted name's);
        # a match above the requested rank is not.
        if m.get("matchType") == "NONE" or m.get("kingdom") != "Plantae" or m.get("rank") != rank:
            raise SystemExit(f"GBIF has no {rank.lower()} match for {name}: {m}")
        matches[name] = m
        print(f"{name}: {m.get('rank')} {m.get('scientificName')} ({m.get('matchType')})")
    (OUT / "matches.json").write_text(json.dumps(matches, indent=1))

    genera = sorted({m["genusKey"] for m in matches.values() if "genusKey" in m})
    relatives = {}
    for genus_key in genera:
        found, offset = [], 0
        while True:
            page = get_json("species/search", highertaxon_key=genus_key, rank="SPECIES",
                            status="ACCEPTED", datasetKey=BACKBONE, limit=1000, offset=offset)
            for r in page["results"]:
                english = [v["vernacularName"] for v in r.get("vernacularNames", [])
                           if v.get("language") == "eng"]
                if english and r.get("genusKey") == genus_key:
                    found.append({"key": r["key"], "scientificName": r.get("canonicalName") or r["scientificName"],
                                  "common": english[0]})
            offset += len(page["results"])
            if page.get("endOfRecords", True) or not page["results"]:
                break
        relatives[str(genus_key)] = found
        print(f"genus {genus_key}: {len(found)} species with English names")
    (OUT / "relatives.json").write_text(json.dumps(relatives, indent=1))

    species = sorted({m["speciesKey"] for m in matches.values() if "speciesKey" in m})
    infraspecific = {}
    for species_key in species:
        found, offset = [], 0
        while True:
            page = get_json(f"species/{species_key}/children", limit=1000, offset=offset)
            for r in page["results"]:
                marker = INFRA_RANKS.get(r.get("rank"))
                words = (r.get("canonicalName") or "").split()
                if marker and r.get("taxonomicStatus") == "ACCEPTED" and len(words) == 3:
                    found.append({"key": r["key"], "rank": r["rank"].lower(),
                                  "scientificName": f"{words[0]} {words[1]} {marker} {words[2]}"})
            offset += len(page["results"])
            if page.get("endOfRecords", True) or not page["results"]:
                break
        infraspecific[str(species_key)] = found
    (OUT / "infraspecific.json").write_text(json.dumps(infraspecific, indent=1))
    print(f"{sum(len(v) for v in infraspecific.values())} subspecies, varieties and forms "
          f"under {len(species)} species")


if __name__ == "__main__":
    main()
