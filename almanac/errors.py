"""Turn database constraint violations into messages for the user.

The rules themselves live in db/schema.sql. This module only explains
them, keyed by the constraint name PostgreSQL reports.
"""
import psycopg

CONSTRAINT_MESSAGES = {
    "plot_name_unique": "This farm already has a plot with that name.",
    "plot_area_positive": "A plot's area must be greater than zero.",
    "farm_event_quantity_nonneg": "Quantity cannot be negative.",
    "farm_event_unit_required": "An event with a quantity must also have a unit.",
    "farm_event_taxon_fk": "That crop has recorded events and cannot be removed.",
    "crop_catalog_taxon_fk": "That crop is in a farm's catalog and cannot be removed.",
    "farm_domain_unique": "Another farm already uses that web domain.",
    "farm_owner_email_unique": "Another farm already uses that owner email.",
}


def describe(error: psycopg.Error) -> str:
    """Return a readable message for a database error."""
    constraint = getattr(error.diag, "constraint_name", None)
    if constraint in CONSTRAINT_MESSAGES:
        return CONSTRAINT_MESSAGES[constraint]
    if isinstance(error, psycopg.errors.ForeignKeyViolation):
        return "That record refers to something that does not exist, or is still in use."
    if isinstance(error, psycopg.errors.CheckViolation):
        return f"The value breaks a data rule ({constraint})."
    if isinstance(error, psycopg.errors.UniqueViolation):
        return "That record already exists."
    if isinstance(error, psycopg.errors.NotNullViolation):
        return f"{error.diag.column_name} is required."
    return "The database rejected the change."
