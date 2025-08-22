"""Utility functions for bulkinvoicer."""

from collections.abc import Mapping, Sequence
from decimal import Decimal
from functools import cache
import logging
from typing import Any
import qrcode

logger = logging.getLogger(__name__)


def match_payments(
    invoices: Sequence[Mapping[str, Any]], receipts: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Match payments from receipts to invoices.

    Returns two lists:
        - matched_payments: List of receipts with matched invoices.
        - unmatched_invoices: List of invoices that were not fully paid.
    """
    if not invoices and not receipts:
        logger.warning("No invoices or receipts to match.")
        return ([], [])

    unmatched_invoices = []
    matched_payments = []

    for invoice in invoices:
        invoice_number = invoice.get("number")
        if not invoice_number:
            logger.warning("Invoice without number found. Skipping.")
            continue

        invoice_amount = invoice.get("total", 0)
        unmatched_invoices.append(
            {
                "number": invoice_number,
                "balance": invoice_amount,
            }
        )

    for receipt in receipts:
        receipt_number = receipt.get("number")
        receipt_amount = receipt.get("amount", 0)
        receipt_balance = receipt_amount

        matches = []

        while receipt_balance > 0 and unmatched_invoices:
            invoice = unmatched_invoices[0]
            invoice_number = invoice["number"]
            invoice_balance = invoice["balance"]

            if receipt_balance >= invoice_balance:
                matches.append({"invoice": invoice_number, "amount": invoice_balance})
                receipt_balance -= invoice_balance
                unmatched_invoices.pop(0)
            else:
                matches.append({"invoice": invoice_number, "amount": receipt_balance})
                invoice["balance"] -= receipt_balance
                receipt_balance = 0

        if receipt_balance > 0:
            matches.append({"invoice": None, "amount": receipt_balance})

        matched_payments.append(
            {
                "receipt": receipt_number,
                "invoices": matches,
            }
        )

    return (matched_payments, unmatched_invoices)


def format_currency(value: Decimal, currency: str = "INR") -> str:
    """Format a Decimal value as currency."""
    if value is None:
        return format_currency(Decimal(), currency)
    if not isinstance(value, Decimal):
        raise TypeError("Value must be a Decimal instance.")

    currency_symbol = {
        "INR": "₹",
        "USD": "$",
    }.get(currency)

    if currency_symbol:
        return f"{currency_symbol}{value:>12,}"
    else:
        return f"{value:>12,} {currency}"


@cache
def get_qrcode_image(data: str) -> qrcode.image.base.BaseImage:
    """Generate a QR code image for the given data."""
    qr = qrcode.QRCode()
    qr.add_data(data)
    img = qr.make_image()
    return img
