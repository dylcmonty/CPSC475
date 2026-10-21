"""Parsing and validating submitted form fields.

Each helper reads one field, converts it to the type the database
expects, and raises FormError with a message the user can act on.
Blank optional fields become None so they are stored as NULL.
"""
from datetime import date
from decimal import Decimal, InvalidOperation


class FormError(ValueError):
    pass


def text(form, name, label, max_len, required=False):
    value = form.get(name, "").strip()
    if not value:
        if required:
            raise FormError(f"{label} is required.")
        return None
    if len(value) > max_len:
        raise FormError(f"{label} must be at most {max_len} characters.")
    return value


def integer(form, name, label, required=False):
    value = form.get(name, "").strip()
    if not value:
        if required:
            raise FormError(f"{label} is required.")
        return None
    try:
        return int(value)
    except ValueError:
        raise FormError(f"{label} must be a whole number.") from None


def decimal(form, name, label, required=False):
    value = form.get(name, "").strip()
    if not value:
        if required:
            raise FormError(f"{label} is required.")
        return None
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise FormError(f"{label} must be a number.") from None
    if not number.is_finite() or abs(number) >= Decimal("1e8"):
        raise FormError(f"{label} is out of range.")
    return number


def iso_date(form, name, label, required=False):
    value = form.get(name, "").strip()
    if not value:
        if required:
            raise FormError(f"{label} is required.")
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise FormError(f"{label} must be a date (YYYY-MM-DD).") from None
