"""Tests of the data loaders: report parsing, label matching, units.

These need no database. The report snippets are copied from real
reports, including their typos.
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "loaders"))

import build_sqlite  # noqa: E402
import parse_reports  # noqa: E402
import products  # noqa: E402
import units  # noqa: E402

USDA_2019 = """\
PHILADELPHIA 06-JUNE-2019
AM_FV160
PRICES TO GROWERS FOR WEDNESDAY 05-JUNE-2019

                               Volume         Prices       Weighted
                                           Low      High     Average

---Strawberries: 8-quart          123     20.00     37.00     32.70
---PEPPERS, BELL: pecks            301      1.00     12.50      6.32
   Bushels                         169      6.00     21.00     12.92
---CUCUMBERS: 24 count             260      2.00     14.00      9 80
"""

USDA_2026 = """\
Prices for Wednesday, September 2, 2026
---CANTALOUPES: each                               520                1.75     3.50            2.56
   Aphrodite type, each                           1085                1.50     4.50            3.50
"""

COUNTY_LINE = """\
                        County Line Produce Auction Market Report
                                       APRIL 28, 2025
              Product               Size       Quantity       Low          High           Average

                                           PRODUCE
APPLES Lodi                   peck                    19      $     5.00   $       5.50   $        5.39
BEANS                         peck                    44      $    14.00   $      26.00   $       19.15
 yellow                       peck                    21      $    17.00   $      25.00   $       23.71
                              bushel                  15      $     8.00   $      11.00   $        8.80
 APPLES
  Cortland                             peck           28      $      8.50   $       9.00   $       8.64
LEEKS                                                   40       $     0.20 $          0.20 $        0.20
"""


def test_usda_rows_dates_and_units(tmp_path):
    report = tmp_path / "r.txt"
    report.write_text(USDA_2019)
    rows, problems = parse_reports.parse_usda(report)
    assert {r["sale_date"] for r in rows} == {date(2019, 6, 5)}
    berries, peppers, bushels = rows
    assert berries["commodity"] == "Strawberries" and berries["avg"] == Decimal("32.70")
    assert peppers["unit"] == "pecks" and bushels["variant"] == "Bushels"
    # "9 80" is a typo in the source; the line is reported, not guessed.
    assert len(problems) == 1 and "9 80" in problems[0]


def test_usda_newer_date_format(tmp_path):
    report = tmp_path / "r.txt"
    report.write_text(USDA_2026)
    rows, _ = parse_reports.parse_usda(report)
    assert rows[0]["sale_date"] == date(2026, 9, 2)
    assert rows[1]["variant"] == "Aphrodite type, each"


def test_usda_impossible_date_is_skipped(tmp_path):
    report = tmp_path / "r.txt"
    report.write_text("PRICES TO GROWERS FOR MONDAY 74-SEPTEMBER-2021.\n---BEETS: pecks  83  4.00  8.00  5.00\n")
    rows, problems = parse_reports.parse_usda(report)
    assert rows == [] and "no readable sale date" in problems[0]


def test_county_line_layout(monkeypatch):
    monkeypatch.setattr(parse_reports, "pdf_text", lambda path: COUNTY_LINE)
    rows, problems = parse_reports.parse_county_line(Path("April-28-2025.pdf"))
    assert problems == []
    assert {r["sale_date"] for r in rows} == {date(2025, 4, 28)}
    got = [(r["commodity"], r["variant"], r["unit"]) for r in rows]
    assert got == [
        ("APPLES", "Lodi", "peck"),
        ("BEANS", None, "peck"),
        ("BEANS", "yellow", "peck"),
        ("BEANS", "yellow", "bushel"),     # same product, another size
        ("APPLES", "Cortland", "peck"),    # indented header, then varieties
        ("LEEKS", None, None),             # Size column left blank
    ]


def test_label_matching():
    match = products.match
    assert match("ONIONS, bushel") == "onions"
    assert match("ONIONS green, bunch") == "green-onions"
    assert match("SQAUSH ACORN, each") == "acorn-squash"          # typo in the report
    assert match("APPLES Honey Crisp, peck") == "apples"
    assert match("TOMATO PLANT, pot") == "tomato-plants"
    assert match("BERRIES strawberries, pot") is None             # a plant, not fruit
    assert match("HANGING BASKET 10, hanging basket") is None     # mixed planting
    assert match("HONEY BEAR, 8 oz") is None
    assert match("PEACHES, 1/2 bushel") == "peaches"


def test_unit_standardization():
    std = units.standardize
    assert std("1/2 bushel cartons") == std("half bushel") == std("1/2 bushel ctns") == "1/2 bushel"
    assert std("10# box") == std("10 lb. cartons") == std("10-lb cartons") == "10 lb"
    assert std("per melon") == std("per head") == std("Each") == "each"
    assert std("pecl") == std("Pecks") == "peck"
    assert std("hangning basket") == "hanging basket"
    assert std("12/1 pint flats") == "12 pint flat"
    assert std("Red") is None and std("") is None


def test_lot_checks_match_the_schema():
    ok = {"sale_date": date(2025, 7, 1), "quantity": Decimal(5),
          "low_cents": 100, "high_cents": 200, "avg_cents": 150}
    assert build_sqlite.check_lot(ok) is None
    assert "outside" in build_sqlite.check_lot({**ok, "avg_cents": 1950})
    assert "low price above" in build_sqlite.check_lot({**ok, "low_cents": 300, "avg_cents": 300})
    assert "greater than zero" in build_sqlite.check_lot({**ok, "quantity": Decimal(0)})
