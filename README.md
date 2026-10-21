# Almanac

**A taxonomy-linked farm record book with historical market pricing.**

Term project for Database Management 475/575 at the University of Akron, Fall 2026.

**Team Lesotho:** Dylan Montgomery (captain, dcm103@uakron.edu) and Andrew Styles (as978@uakron.edu)

## What It Is

Almanac is a web application where growers record what they planted, harvested, sold, or lost. Every entry is tied to a node in a 4,118-node plant taxonomy. The same taxonomy indexes 47,516 real produce auction prices from four Ohio market report sources (2019 to 2026), so a grower's records and the region's price history can be queried together:

- What has this crop sold for in this part of the year, across seven seasons?
- What are prices for everything in this plant family? (recursive roll-up)
- Of the crops in this family I could plant in early May, which has held its price best? (decision engine)

## Database at a Glance

| | |
| --- | --- |
| Tables | 12 (8 reference, 4 grower) |
| Foreign keys | 15, including two self-referential hierarchies (`taxon`, `region`) |
| Views | `v_priced_lot`, `v_resolution_coverage` |
| Market lots | 47,516 from 4 sources across 560 trading days, 93.2% matched to a product |
| Taxonomy | 4,118 nodes, 12 levels |
| Products | 217 |
| Farms / regions | 238 Ohio farms / 2,818 regions |

Stack: PostgreSQL 16 (SQLite 3 for development), Python 3.12, Flask 3, psycopg 3, hand-written parameterized SQL, and Chart.js.

## Repository Layout

```
README.md                         this file
course/
  requirements.md                 summary of the assignment, stages, and grading
  notes.md                        team working notes
stages/
  stage1-group-formation/         Stage1_4781742   .md + .pdf
  stage2-proposal/                Stage2_dcm103    .md + .pdf
  stage3-development-plan/        Stage3_dcm103    .md + .pdf
  stage4-initial-demo/            Stage4_dcm103    .md + .pdf
```

Each stage folder holds the submitted report as Markdown (easy to read and diff) and as PDF (the formatted copy).

## Stage Status

| Stage | Deliverable | Due (week of) | Status |
| --- | --- | --- | --- |
| 1 | Group formation | Sep | Submitted |
| 2 | Project proposal | Sep 22 | Submitted |
| 3 | Development plan | Oct 5 | Submitted |
| 4 | Initial demo + report | Oct 19 / Oct 26 | Report drafted |
| 5 | Progress report | Nov 9 | — |
| 6 | Final demo | Nov 30 | — |
| 7 | Final submission | Dec 7 | — |

## Advanced Functions

1. **Recursive taxonomic price roll-up:** a recursive CTE walks any subtree of the taxonomy and aggregates its prices in one statement.
2. **Crop decision engine:** ranks crops for a day-of-year planting window across years by volatility-adjusted price, using a window function, limited to a taxonomic branch.
3. **Taxon resolution ladder:** a four-rung matcher that proposes product matches for unresolved auction labels. It stops when a match is ambiguous instead of guessing, and a person confirms every match.
