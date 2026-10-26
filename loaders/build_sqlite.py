"""Build data/almanac.sqlite from the downloaded sources.

Run the fetch_*.py scripts first. This parses every report, checks each
price row against the same rules as the CHECK constraints in
db/schema.sql (failures go to market_lot_quarantine with the reason),
builds the taxonomy and product lexicon, and writes everything to a
SQLite file with the schema's tables and columns. Load it with:

    ./demo.sh setup data/almanac.sqlite

Usage:
    python loaders/build_sqlite.py [output.sqlite]
"""
import json
import sqlite3
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

import parse_reports
import products
import units

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DEFAULT_OUT = ROOT / "data" / "almanac.sqlite"
NOW = datetime.now().replace(microsecond=0).isoformat(sep=" ")

OBSERVERS = [
    # observer_id, name, domain, granularity, raw folder, parser
    (1, "USDA AMS Market News, Mount Hope Auction", "ams.usda.gov", "product_day",
     "usda_mount_hope", "*.txt", parse_reports.parse_usda),
    (2, "County Line Produce Auction", "countylineproduceauction.com", "product_day",
     "county_line", "*.pdf", parse_reports.parse_county_line),
]

RANKS = ["kingdom", "phylum", "class", "order", "family", "genus", "species"]
INFRA = {"SUBSPECIES", "VARIETY", "FORM"}

TABLES = """
CREATE TABLE observer (observer_id INTEGER PRIMARY KEY, name TEXT, domain TEXT, granularity TEXT);
CREATE TABLE region (region_id INTEGER PRIMARY KEY, parent_region_id INTEGER, name TEXT, kind TEXT);
CREATE TABLE taxon (taxon_id INTEGER PRIMARY KEY, parent_taxon_id INTEGER, path TEXT, depth INTEGER,
                    rank TEXT, scientific_name TEXT, common_name TEXT);
CREATE TABLE product (product_id INTEGER PRIMARY KEY, slug TEXT, title TEXT, taxon_id INTEGER);
CREATE TABLE product_alias (label_norm TEXT PRIMARY KEY, product_id INTEGER, match_rung INTEGER,
                            confirmed_at TEXT);
CREATE TABLE market_lot (lot_id INTEGER PRIMARY KEY, observer_id INTEGER, sale_date TEXT,
                         raw_label TEXT, label_norm TEXT, unit TEXT, quantity NUMERIC,
                         low_cents INTEGER, high_cents INTEGER, avg_cents INTEGER);
CREATE TABLE market_lot_quarantine (quarantine_id INTEGER PRIMARY KEY, observer_id INTEGER,
                         sale_date TEXT, raw_label TEXT, unit TEXT, quantity NUMERIC,
                         low_cents INTEGER, high_cents INTEGER, avg_cents INTEGER,
                         reason TEXT, quarantined_at TEXT);
CREATE TABLE event_kind (event_kind_code TEXT PRIMARY KEY, label TEXT, is_yield INTEGER);
CREATE TABLE farm (farm_id INTEGER PRIMARY KEY, name TEXT, domain TEXT, region_id INTEGER,
                   owner_email TEXT, created_at TEXT);
CREATE TABLE plot (plot_id INTEGER PRIMARY KEY, farm_id INTEGER, name TEXT, area_sq_m NUMERIC);
CREATE TABLE crop_catalog (farm_id INTEGER, taxon_id INTEGER, added_on TEXT, notes TEXT);
CREATE TABLE farm_event (event_id INTEGER PRIMARY KEY, farm_id INTEGER, plot_id INTEGER,
                         taxon_id INTEGER, event_kind_code TEXT, product_id INTEGER,
                         event_date TEXT, quantity NUMERIC, unit TEXT, notes TEXT);
"""


def cents(dollars):
    return int((dollars * 100).to_integral_value())


def check_lot(row):
    """The reason a row breaks market_lot's CHECK constraints, or None."""
    if row["sale_date"] < date(2019, 1, 1):
        return "sale_date before 2019-01-01"
    if row["quantity"] is not None and row["quantity"] <= 0:
        return "quantity must be greater than zero"
    if row["low_cents"] > row["high_cents"]:
        return "low price above high price"
    if not row["low_cents"] <= row["avg_cents"] <= row["high_cents"]:
        return "average price outside the low-high range"
    return None


def raw_label(row):
    name = row["commodity"] + (f" {row['variant']}" if row["variant"] else "")
    return f"{name}, {row['unit']}" if row["unit"] else name


# ---------------------------------------------------------------- taxonomy

def build_taxonomy():
    """Taxon rows keyed by GBIF key, and the GBIF key for each scientific name."""
    matches = json.loads((RAW / "gbif" / "matches.json").read_text())
    relatives = json.loads((RAW / "gbif" / "relatives.json").read_text())
    infraspecific = json.loads((RAW / "gbif" / "infraspecific.json").read_text())

    curated = {}
    for _, sci, common in products.PRODUCTS.values():
        curated.setdefault(sci, common)

    nodes = {}          # gbif key (or cultivar group name) -> dict(parent, rank, name, common)
    key_for = {}        # product scientific name -> key of its taxon
    for name, m in matches.items():
        parent = None
        for rank in RANKS:
            key = m.get(f"{rank}Key")
            if key is None:
                continue
            nodes.setdefault(key, {"parent": parent, "rank": rank, "name": m[rank], "common": None})
            parent = key
            if rank == m["rank"].lower():
                key_for[name] = key
                break
        if m["rank"] in INFRA:
            nodes.setdefault(m["usageKey"], {"parent": m["speciesKey"], "rank": m["rank"].lower(),
                                             "name": name, "common": None})
            key_for[name] = m["usageKey"]

    # Accepted subspecies, varieties and forms of every species in the tree.
    for species_key, children in infraspecific.items():
        if int(species_key) not in nodes:
            continue
        for c in children:
            nodes.setdefault(c["key"], {"parent": int(species_key), "rank": c["rank"],
                                        "name": c["scientificName"], "common": None})

    # Cultivar groups sit directly under their species.
    for group, species in products.CULTIVAR_GROUPS.items():
        nodes[group] = {"parent": key_for[species], "rank": "cultivar group", "name": group, "common": None}
        key_for[group] = group

    for name, key in key_for.items():
        if curated.get(name):
            nodes[key]["common"] = curated[name]

    for genus_key, species in relatives.items():
        genus_key = int(genus_key)
        if genus_key not in nodes:
            continue
        for s in species:
            node = nodes.setdefault(s["key"], {"parent": genus_key, "rank": "species",
                                               "name": s["scientificName"], "common": None})
            node["common"] = node["common"] or s["common"].lower()
    return nodes, key_for


def number_taxa(nodes):
    """Assign taxon ids parent-first and build materialized paths."""
    depth = {}

    def depth_of(key):
        if key not in depth:
            parent = nodes[key]["parent"]
            depth[key] = 0 if parent is None else depth_of(parent) + 1
        return depth[key]

    order = sorted(nodes, key=lambda k: (depth_of(k), nodes[k]["name"], str(k)))
    ids = {key: i for i, key in enumerate(order, start=1)}
    rows, paths = [], {}
    for key in order:
        node = nodes[key]
        parent_id = ids.get(node["parent"])
        paths[key] = f"{paths[node['parent']]}.{ids[key]}" if parent_id else str(ids[key])
        rows.append((ids[key], parent_id, paths[key], depth_of(key), node["rank"],
                     node["name"], node["common"]))
    return rows, ids


# ---------------------------------------------------------------- main

def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript(TABLES)

    db.executemany("INSERT INTO observer VALUES (?, ?, ?, ?)", [o[:4] for o in OBSERVERS])

    # Regions: country, state, the 88 counties.
    counties = json.loads((RAW / "ohio_counties.json").read_text())
    db.execute("INSERT INTO region VALUES (1, NULL, 'United States', 'country')")
    db.execute("INSERT INTO region VALUES (2, 1, 'Ohio', 'state')")
    county_id = {}
    for i, name in enumerate(counties, start=3):
        db.execute("INSERT INTO region VALUES (?, 2, ?, 'county')", (i, name))
        county_id[name] = i

    # Farms, one per distinct name and county; a web domain is kept only once.
    farms = json.loads((RAW / "farms.json").read_text())
    seen, domains = set(), set()
    for farm in sorted(farms, key=lambda f: (f["name"], f["county"])):
        if (farm["name"], farm["county"]) in seen:
            continue
        seen.add((farm["name"], farm["county"]))
        domain = urlparse(farm["website"]).netloc.lower().removeprefix("www.") if farm["website"] else None
        if domain in domains:
            domain = None
        domains.add(domain)
        db.execute("INSERT INTO farm (name, domain, region_id, owner_email, created_at)"
                   " VALUES (?, ?, ?, NULL, ?)", (farm["name"], domain or None,
                                                   county_id[farm["county"]], NOW))

    # Taxonomy and products.
    nodes, key_for = build_taxonomy()
    taxon_rows, taxon_id = number_taxa(nodes)
    db.executemany("INSERT INTO taxon VALUES (?, ?, ?, ?, ?, ?, ?)", taxon_rows)
    product_id = {}
    for i, (slug, (title, sci, _)) in enumerate(products.PRODUCTS.items(), start=1):
        db.execute("INSERT INTO product VALUES (?, ?, ?, ?)", (i, slug, title, taxon_id[key_for[sci]]))
        product_id[slug] = i

    db.executemany("INSERT INTO event_kind VALUES (?, ?, ?)", [
        ("plant", "Planting", 0), ("harvest", "Harvest", 1), ("sale", "Sale", 0), ("loss", "Loss", 0)])

    # Market lots.
    problems, quarantined, aliases = [], Counter(), {}
    lot_count = Counter()
    for observer_id, name, _, _, folder, pattern, parse in OBSERVERS:
        for path in sorted((RAW / folder).glob(pattern)):
            rows, issues = parse(path)
            problems += issues
            for r in rows:
                label = raw_label(r)
                lot = {"sale_date": r["sale_date"], "quantity": r["quantity"],
                       "low_cents": cents(r["low"]), "high_cents": cents(r["high"]),
                       "avg_cents": cents(r["avg"])}
                # USDA puts a different unit on some variety lines ("Bushels").
                texts = (r["variant"], r["unit"]) if observer_id == 1 else (r["unit"], r["variant"])
                unit = next((u for u in map(units.standardize, texts) if u), None)
                values = (observer_id, r["sale_date"].isoformat(), label[:255], unit,
                          r["quantity"] and float(r["quantity"]),
                          lot["low_cents"], lot["high_cents"], lot["avg_cents"])
                reason = check_lot(lot)
                if reason:
                    db.execute("INSERT INTO market_lot_quarantine (observer_id, sale_date, raw_label,"
                               " unit, quantity, low_cents, high_cents, avg_cents, reason,"
                               " quarantined_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               values + (reason, NOW))
                    quarantined[name] += 1
                    continue
                norm = products.normalize(label)[:255]
                db.execute("INSERT INTO market_lot (observer_id, sale_date, raw_label, label_norm,"
                           " unit, quantity, low_cents, high_cents, avg_cents)"
                           " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           values[:3] + (norm,) + values[3:])
                lot_count[name] += 1
                if norm not in aliases:
                    aliases[norm] = products.match(label)

    db.executemany("INSERT INTO product_alias VALUES (?, ?, 0, ?)",
                   [(norm, product_id[slug], NOW) for norm, slug in aliases.items() if slug])
    db.commit()

    resolved = db.execute("SELECT COUNT(*) FROM market_lot l JOIN product_alias a"
                          " ON a.label_norm = l.label_norm").fetchone()[0]
    total = sum(lot_count.values())
    print(f"Wrote {out}")
    for name, count in lot_count.items():
        print(f"  {name}: {count:,} lots, {quarantined[name]} quarantined")
    print(f"  {total:,} lots, {resolved / total:.1%} matched to a product, "
          f"{sum(1 for s in aliases.values() if not s):,} labels unmatched")
    print(f"  {len(taxon_rows):,} taxa, {len(products.PRODUCTS)} products, "
          f"{db.execute('SELECT COUNT(*) FROM farm').fetchone()[0]} farms, {len(counties)} counties")
    if problems:
        print(f"  {len(problems)} report lines or files could not be read:")
        for p in problems:
            print(f"    {p}")


if __name__ == "__main__":
    main()
