"""The farm event log: activity history plus insert, update and delete."""
from datetime import date

import psycopg
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import errors, forms
from .db import execute, query, query_one
from .farms import load_farm

bp = Blueprint("events", __name__, url_prefix="/farms/<int:farm_id>/events")

# A blank date filter means "no limit"; these bounds cover every event.
EARLIEST = date(1900, 1, 1)
LATEST = date(2999, 12, 31)

ACTIVITY_SQL = """
SELECT e.event_id, e.event_date, k.label AS event_kind,
       t.common_name, t.scientific_name,
       pl.name AS plot, p.title AS product,
       e.quantity, e.unit, e.notes
FROM farm_event e
JOIN event_kind k     ON k.event_kind_code = e.event_kind_code
JOIN taxon t          ON t.taxon_id = e.taxon_id
LEFT JOIN plot pl     ON pl.plot_id = e.plot_id
LEFT JOIN product p   ON p.product_id = e.product_id
WHERE e.farm_id = %(farm_id)s
  AND e.event_date BETWEEN %(date_from)s AND %(date_to)s
  AND (CAST(%(kind)s AS VARCHAR) IS NULL OR e.event_kind_code = %(kind)s)
  AND (CAST(%(taxon_id)s AS INTEGER) IS NULL OR e.taxon_id = %(taxon_id)s)
ORDER BY e.event_date DESC, e.event_id DESC
"""

EVENT_SQL = """
SELECT event_id, plot_id, taxon_id, event_kind_code, product_id,
       event_date, quantity, unit, notes
FROM farm_event
WHERE event_id = %(event_id)s AND farm_id = %(farm_id)s
"""

INSERT_EVENT_SQL = """
INSERT INTO farm_event
    (farm_id, plot_id, taxon_id, event_kind_code, product_id,
     event_date, quantity, unit, notes)
VALUES
    (%(farm_id)s, %(plot_id)s, %(taxon_id)s, %(kind)s, %(product_id)s,
     %(event_date)s, %(quantity)s, %(unit)s, %(notes)s)
RETURNING event_id
"""

UPDATE_EVENT_SQL = """
UPDATE farm_event
SET plot_id = %(plot_id)s, taxon_id = %(taxon_id)s,
    event_kind_code = %(kind)s, product_id = %(product_id)s,
    event_date = %(event_date)s, quantity = %(quantity)s,
    unit = %(unit)s, notes = %(notes)s
WHERE event_id = %(event_id)s AND farm_id = %(farm_id)s
"""

DELETE_EVENT_SQL = """
DELETE FROM farm_event
WHERE event_id = %(event_id)s AND farm_id = %(farm_id)s
"""

KINDS_SQL = "SELECT event_kind_code, label FROM event_kind ORDER BY label"

PLOT_CHOICES_SQL = """
SELECT plot_id, name FROM plot WHERE farm_id = %(farm_id)s ORDER BY name
"""

# Crops offered on the event form: the farm's catalog, plus the event's
# current crop when editing, in case it was since removed from the catalog.
CROP_CHOICES_SQL = """
SELECT t.taxon_id, COALESCE(t.common_name, t.scientific_name) AS label,
       t.scientific_name
FROM taxon t
WHERE t.taxon_id IN (SELECT taxon_id FROM crop_catalog WHERE farm_id = %(farm_id)s)
   OR t.taxon_id = %(current_taxon_id)s
ORDER BY label
"""

PRODUCT_CHOICES_SQL = """
SELECT p.product_id, p.title
FROM product p
WHERE p.taxon_id IN (SELECT taxon_id FROM crop_catalog WHERE farm_id = %(farm_id)s)
   OR p.product_id = %(current_product_id)s
ORDER BY p.title
"""


def form_choices(farm_id, event=None):
    """Option lists for the event form."""
    return {
        "kinds": query(KINDS_SQL),
        "plots": query(PLOT_CHOICES_SQL, {"farm_id": farm_id}),
        "crops": query(CROP_CHOICES_SQL, {
            "farm_id": farm_id,
            "current_taxon_id": event["taxon_id"] if event else None,
        }),
        "products": query(PRODUCT_CHOICES_SQL, {
            "farm_id": farm_id,
            "current_product_id": event["product_id"] if event else None,
        }),
    }


def read_event_form(form, farm_id):
    values = {
        "farm_id": farm_id,
        "kind": forms.text(form, "event_kind_code", "Event kind", 20, required=True),
        "taxon_id": forms.integer(form, "taxon_id", "Crop", required=True),
        "plot_id": forms.integer(form, "plot_id", "Plot"),
        "product_id": forms.integer(form, "product_id", "Product"),
        "event_date": forms.iso_date(form, "event_date", "Date", required=True),
        "quantity": forms.decimal(form, "quantity", "Quantity"),
        "unit": forms.text(form, "unit", "Unit", 40),
        "notes": forms.text(form, "notes", "Notes", 1000),
    }
    # The foreign key only checks that the plot exists, not whose it is.
    if values["plot_id"] is not None:
        farm_plots = {p["plot_id"] for p in query(PLOT_CHOICES_SQL, {"farm_id": farm_id})}
        if values["plot_id"] not in farm_plots:
            raise forms.FormError("That plot does not belong to this farm.")
    return values


@bp.route("/")
def event_list(farm_id):
    farm = load_farm(farm_id)
    args = request.args
    try:
        filters = {
            "farm_id": farm_id,
            "date_from": forms.iso_date(args, "from", "From date") or EARLIEST,
            "date_to": forms.iso_date(args, "to", "To date") or LATEST,
            "kind": forms.text(args, "kind", "Event kind", 20),
            "taxon_id": forms.integer(args, "taxon_id", "Crop"),
        }
        events = query(ACTIVITY_SQL, filters)
    except forms.FormError as err:
        flash(str(err), "error")
        events = []
    return render_template(
        "events/list.html",
        farm=farm,
        events=events,
        args=args,
        kinds=query(KINDS_SQL),
        crops=query(CROP_CHOICES_SQL, {"farm_id": farm_id, "current_taxon_id": None}),
    )


@bp.route("/new", methods=["GET", "POST"])
def event_new(farm_id):
    farm = load_farm(farm_id)
    if request.method == "POST":
        try:
            execute(INSERT_EVENT_SQL, read_event_form(request.form, farm_id))
            flash("Event recorded.")
            return redirect(url_for("events.event_list", farm_id=farm_id))
        except forms.FormError as err:
            flash(str(err), "error")
        except psycopg.Error as err:
            flash(errors.describe(err), "error")
    form = request.form if request.method == "POST" else {"event_date": date.today().isoformat()}
    return render_template(
        "events/form.html", farm=farm, event=None, form=form, **form_choices(farm_id)
    )


@bp.route("/<int:event_id>/edit", methods=["GET", "POST"])
def event_edit(farm_id, event_id):
    farm = load_farm(farm_id)
    event = query_one(EVENT_SQL, {"farm_id": farm_id, "event_id": event_id})
    if event is None:
        abort(404)
    if request.method == "POST":
        try:
            values = read_event_form(request.form, farm_id)
            execute(UPDATE_EVENT_SQL, {"event_id": event_id, **values})
            flash("Event updated.")
            return redirect(url_for("events.event_list", farm_id=farm_id))
        except forms.FormError as err:
            flash(str(err), "error")
        except psycopg.Error as err:
            flash(errors.describe(err), "error")
    form = request.form if request.method == "POST" else event
    return render_template(
        "events/form.html", farm=farm, event=event, form=form, **form_choices(farm_id, event)
    )


@bp.route("/<int:event_id>/delete", methods=["POST"])
def event_delete(farm_id, event_id):
    if execute(DELETE_EVENT_SQL, {"farm_id": farm_id, "event_id": event_id}):
        flash("Event deleted.")
    return redirect(url_for("events.event_list", farm_id=farm_id))
