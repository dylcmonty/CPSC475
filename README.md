# Almanac

**A taxonomy-linked farm record book with historical market pricing.**

Term project for Database Management 475/575 at the University of Akron, Fall 2026.

**Team Lesotho:** Dylan Montgomery (captain, dcm103@uakron.edu) and Andrew Styles (as978@uakron.edu)

## What It Is

Almanac is a web application where growers record what they planted, harvested, sold, or lost. Every entry is tied to a node in a 2,993-node plant taxonomy. The same taxonomy indexes 33,667 real produce auction prices from two Ohio auctions (2019 to 2026), so a grower's records and the region's price history can be queried together:

- What has this crop sold for in this part of the year, across eight seasons?
- What are prices for everything in this plant family? (recursive roll-up)
- Of the crops in this family I could plant in early May, which has held its price best? (decision engine)

## Database at a Glance

| | |
| --- | --- |
| Tables | 12 (8 reference, 4 grower) |
| Foreign keys | 15, including two self-referential hierarchies (`taxon`, `region`) |
| Views | `v_priced_lot`, `v_resolution_coverage` |
| Market lots | 33,667 from 2 sources across 520 sale days, 85.8% matched to a product; 26 quarantined; units standardized (237 spellings to 35) |
| Taxonomy | 2,993 nodes, kingdom to subspecies, variety or cultivar group (GBIF Backbone Taxonomy, plus ICNCP cultivar groups) |
| Products | 95 |
| Farms / regions | 107 Ohio farms / 90 regions (88 counties) |

Stack: PostgreSQL 16 (SQLite 3 for development), Python 3.12, Flask 3, psycopg 3, hand-written parameterized SQL, and Chart.js.

## Repository Layout

```
README.md                         this file
ERD.md                            entity relationship diagram (Mermaid)
almanac/                          the Flask application
  __init__.py                     app factory
  db.py                           connection, query helpers, `flask init-db`
  forms.py, errors.py             input validation; constraint errors as messages
  main.py                         home page, crop search, seasonal price curve
  farms.py                        farm directory, overview, harvest vs. market join
  plots.py, catalog.py, events.py insert / update / delete for grower data
  templates/, static/             Jinja2 pages and stylesheet
db/
  schema.sql                      12 tables, 15 foreign keys, 2 views
  seed.sql                        event kinds (plant, harvest, sale, loss)
loaders/                          download the real data and build data/almanac.sqlite
  fetch_usda.py, fetch_county_line.py, fetch_taxonomy.py, fetch_farms.py
  parse_reports.py, products.py   report parsers; product list and label matching rules
  units.py                        unit standardization
  build_sqlite.py                 parse, check against the schema rules, write the file
scripts/
  import_sqlite.py                copy the loaded SQLite reference data into PostgreSQL
  demo.sh, demo.py                set up, check and launch the class demo
tests/                            end-to-end tests against a real PostgreSQL database
course/
  requirements.md                 summary of the assignment, stages, and grading
  notes.md                        team working notes
stages/
  stage1-group-formation/         Stage1_4781742   .md + .pdf
  stage2-proposal/                Stage2_dcm103    .md + .pdf
  stage3-development-plan/        Stage3_dcm103    .md + .pdf
  stage4-initial-demo/            Stage4_dcm103    .md + .pdf
    presentation/                 slides.pdf, presentation-script and demo-script .md + .pdf, speaker-notes.md
```

Each stage folder holds the submitted report as Markdown (easy to read and diff) and as PDF (the formatted copy).

## Running the App

Requires Python 3.10 or later and PostgreSQL 16. For a step-by-step install on a new machine, see [SETUP.md](SETUP.md).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

createdb almanac
export DATABASE_URL=postgresql:///almanac     # default if unset
flask --app almanac init-db                   # schema + event kinds
python scripts/import_sqlite.py path/to/almanac.sqlite   # reference data
flask --app almanac run --debug               # http://127.0.0.1:5000
```

`import_sqlite.py` copies every table from the SQLite database the data was first loaded into, keeping primary keys, then resets the identity sequences. Set `SECRET_KEY` to a random value in production.

### Real Data

The reference data comes from public sources. The scripts in `loaders/` download it into `data/raw/` and build `data/almanac.sqlite` (both ignored by git). They need `pdftotext` (Ubuntu package `poppler-utils`) for the PDF reports:

| Data | Source |
| --- | --- |
| Auction prices | USDA AMS Market News, Mount Hope Auction report AM_FV160 (esmis.nal.usda.gov archive, 2019 to 2026); County Line Produce Auction market reports (countylineproduceauction.com, 2024 to 2026) |
| Taxonomy | GBIF Backbone Taxonomy (api.gbif.org) |
| Farms | Named Ohio farms, farm markets and orchards in OpenStreetMap (ODbL), with counties from the US Census geocoder |
| Counties | US Census Bureau 2020 county codes |

```bash
python3 loaders/fetch_usda.py
python3 loaders/fetch_county_line.py
python3 loaders/fetch_taxonomy.py
python3 loaders/fetch_farms.py
python3 loaders/build_sqlite.py               # prints counts and every line it could not read
```

### Demo Launcher

`scripts/demo.sh` does the steps above for the class demo. It creates `.venv` on first use.

```bash
scripts/demo.sh setup path/to/almanac.sqlite   # fresh database + real data (asks first)
scripts/demo.sh check                          # preflight only
scripts/demo.sh                                # preflight, start the app, open the browser tabs
scripts/demo.sh reset                          # empty the demo farm after a rehearsal
```

### Pages

| Page | URL | Function |
| --- | --- | --- |
| Home | `/` | Row counts for every table, and auction lot coverage for each source |
| Crop search | `/search?q=` | Searches scientific names, common names and product titles; ranked by auction evidence |
| Price curve | `/taxa/<id>?unit=` | Monthly floor, mean and ceiling across all seasons, one unit at a time, charted with Chart.js |
| Farms | `/farms/`, `/farms/new` | Farm directory search; add a farm |
| Farm overview | `/farms/<id>` | Recent events, plots (edit/delete), crops grown |
| Activity history | `/farms/<id>/events/` | Events filtered by date range, event kind and crop; edit/delete |
| Record an event | `/farms/<id>/events/new` | Insert into `farm_event` |
| Plots | `/farms/<id>/plots/new` | Insert/update/delete `plot` |
| Crop catalog | `/farms/<id>/catalog/` | Search taxa and add; edit notes; remove |
| Harvest vs. market | `/farms/<id>/harvest-prices` | Multi-table join: auction prices within 30 days of each harvest, per unit |

### Tests

```bash
pip install -r requirements-dev.txt
TEST_DATABASE_URL=postgresql:///postgres pytest
```

Each app test creates a fresh `almanac_test` database on that server, loads the schema and a small synthetic fixture, and drives the pages through Flask's test client. The loader tests (`tests/test_loaders.py`) need no database and run on snippets copied from real reports.

## Stage Status

| Stage | Deliverable | Due (week of) | Status |
| --- | --- | --- | --- |
| 1 | Group formation | Sep | Submitted |
| 2 | Project proposal | Sep 22 | Submitted |
| 3 | Development plan | Oct 5 | Submitted |
| 4 | Report + initial demo | Oct 23 / Oct 28 | Report ready; presentation ready |
| 5 | Progress report | Nov 9 | Not started |
| 6 | Final demo | Nov 30 | Not started |
| 7 | Final submission | Dec 7 | Not started |

## Advanced Functions

1. **Recursive taxonomic price roll-up:** a recursive CTE walks any subtree of the taxonomy and aggregates its prices in one statement.
2. **Crop decision engine:** ranks crops for a day-of-year planting window across years by volatility-adjusted price, using a window function, limited to a taxonomic branch.
3. **Taxon resolution ladder:** a four-rung matcher that proposes product matches for unresolved auction labels. It stops when a match is ambiguous instead of guessing, and a person confirms every match.
