"""Home page, combined catalog search, and the per-crop price curve."""
from flask import Blueprint, abort, render_template, request

from .db import query, query_one

bp = Blueprint("main", __name__)

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

TABLE_COUNTS_SQL = """
SELECT 'market_lot' AS table_name, COUNT(*) AS rows FROM market_lot
UNION ALL SELECT 'market_lot_quarantine', COUNT(*) FROM market_lot_quarantine
UNION ALL SELECT 'taxon', COUNT(*) FROM taxon
UNION ALL SELECT 'product', COUNT(*) FROM product
UNION ALL SELECT 'product_alias', COUNT(*) FROM product_alias
UNION ALL SELECT 'observer', COUNT(*) FROM observer
UNION ALL SELECT 'farm', COUNT(*) FROM farm
UNION ALL SELECT 'region', COUNT(*) FROM region
UNION ALL SELECT 'plot', COUNT(*) FROM plot
UNION ALL SELECT 'crop_catalog', COUNT(*) FROM crop_catalog
UNION ALL SELECT 'farm_event', COUNT(*) FROM farm_event
"""

COVERAGE_SQL = """
SELECT source, total_lots, resolved_lots, pct_resolved
FROM v_resolution_coverage
ORDER BY source
"""

LOT_RANGE_SQL = """
SELECT MIN(sale_date) AS first_sale, MAX(sale_date) AS last_sale,
       COUNT(DISTINCT sale_date) AS trading_days
FROM market_lot
"""

CATALOG_SEARCH_SQL = """
SELECT t.taxon_id, t.rank, t.scientific_name, t.common_name,
       COUNT(v.lot_id) AS lots
FROM taxon t
LEFT JOIN v_priced_lot v ON v.taxon_id = t.taxon_id
WHERE t.scientific_name ILIKE %(pattern)s
   OR t.common_name     ILIKE %(pattern)s
   OR EXISTS (SELECT 1 FROM product p
              WHERE p.taxon_id = t.taxon_id
                AND p.title ILIKE %(pattern)s)
GROUP BY t.taxon_id, t.rank, t.scientific_name, t.common_name, t.depth
ORDER BY lots DESC, t.depth, t.scientific_name
LIMIT 50
"""

TAXON_SQL = """
SELECT t.taxon_id, t.rank, t.scientific_name, t.common_name, t.path,
       parent.taxon_id AS parent_id, parent.scientific_name AS parent_name
FROM taxon t
LEFT JOIN taxon parent ON parent.taxon_id = t.parent_taxon_id
WHERE t.taxon_id = %(taxon_id)s
"""

TAXON_PRODUCTS_SQL = """
SELECT p.product_id, p.title, COUNT(v.lot_id) AS lots
FROM product p
LEFT JOIN v_priced_lot v ON v.product_id = p.product_id
WHERE p.taxon_id = %(taxon_id)s
GROUP BY p.product_id, p.title
ORDER BY lots DESC, p.title
"""

# Prices are only comparable within one unit (a peck is not a bushel),
# so the curve is drawn for one unit at a time, the most common by default.
TAXON_UNITS_SQL = """
SELECT v.unit, COUNT(*) AS lots
FROM v_priced_lot v
WHERE v.taxon_id = %(taxon_id)s
GROUP BY v.unit
ORDER BY lots DESC, v.unit
"""

PRICE_CURVE_SQL = """
SELECT EXTRACT(MONTH FROM v.sale_date)::INT           AS month,
       COUNT(*)                                       AS lots,
       COUNT(DISTINCT EXTRACT(YEAR FROM v.sale_date)) AS seasons,
       MIN(v.low_price)                               AS floor_price,
       ROUND(AVG(v.avg_price), 2)                     AS mean_price,
       MAX(v.high_price)                              AS ceiling_price
FROM v_priced_lot v
WHERE v.taxon_id = %(taxon_id)s
  AND v.unit IS NOT DISTINCT FROM CAST(%(unit)s AS VARCHAR)
GROUP BY EXTRACT(MONTH FROM v.sale_date)
ORDER BY month
"""

# Lots with no unit in the report are offered as this choice.
UNSPECIFIED = "unspecified"


def like_pattern(term):
    """Wrap user text in % wildcards, escaping LIKE's own wildcards."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def as_float(value):
    """Decimal to float for the chart; missing prices stay None."""
    return None if value is None else float(value)


@bp.route("/")
def home():
    return render_template(
        "home.html",
        counts=query(TABLE_COUNTS_SQL),
        coverage=query(COVERAGE_SQL),
        lot_range=query_one(LOT_RANGE_SQL),
    )


@bp.route("/search")
def search():
    term = request.args.get("q", "").strip()
    results = []
    if term:
        results = query(CATALOG_SEARCH_SQL, {"pattern": like_pattern(term)})
    return render_template("search.html", term=term, results=results)


@bp.route("/taxa/<int:taxon_id>")
def taxon_detail(taxon_id):
    taxon = query_one(TAXON_SQL, {"taxon_id": taxon_id})
    if taxon is None:
        abort(404)
    units = query(TAXON_UNITS_SQL, {"taxon_id": taxon_id})
    unit_names = [row["unit"] or UNSPECIFIED for row in units]
    unit = request.args.get("unit")
    if unit not in unit_names:
        unit = unit_names[0] if unit_names else None
    curve = query(PRICE_CURVE_SQL, {"taxon_id": taxon_id,
                                    "unit": None if unit == UNSPECIFIED else unit})
    chart = {
        "labels": [MONTH_NAMES[row["month"] - 1] for row in curve],
        "floor": [as_float(row["floor_price"]) for row in curve],
        "mean": [as_float(row["mean_price"]) for row in curve],
        "ceiling": [as_float(row["ceiling_price"]) for row in curve],
    }
    return render_template(
        "taxon.html",
        taxon=taxon,
        products=query(TAXON_PRODUCTS_SQL, {"taxon_id": taxon_id}),
        curve=curve,
        chart=chart,
        units=units,
        unit=unit,
        unspecified=UNSPECIFIED,
        month_names=MONTH_NAMES,
    )

