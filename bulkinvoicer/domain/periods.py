"""Period utilities: slicing frames and rendering period text."""

from __future__ import annotations

import datetime
import logging
import polars as pl

logger = logging.getLogger(__name__)


def get_reporting_period_text(
    date_format: str, start_date: datetime.date | None, end_date: datetime.date | None
) -> str | None:
    """Generate reporting period text based on start and end dates."""
    reporting_period_text = None
    if start_date and end_date:
        if start_date > end_date:
            logger.error(
                f"Start date {start_date} is after end date {end_date}. "
                "Please check the configuration."
            )
            raise ValueError(
                f"Start date {start_date} cannot be after end date {end_date}."
            )

        reporting_period_text = f"Period: {start_date.strftime(date_format)} - {end_date.strftime(date_format)}"
    elif start_date:
        reporting_period_text = f"Period: Starting {start_date.strftime(date_format)}"
    elif end_date:
        reporting_period_text = f"Period: Ending {end_date.strftime(date_format)}"

    return reporting_period_text


def slice_period_frames(
    df_invoices: pl.DataFrame,
    df_receipts: pl.DataFrame,
    start_date: datetime.date | None,
    end_date: datetime.date | None,
) -> dict[str, pl.DataFrame]:
    """Create reporting period specific frames."""
    inv_report = df_invoices
    rec_report = df_receipts
    inv_open = df_invoices
    rec_open = df_receipts
    inv_close = df_invoices
    rec_close = df_receipts

    if start_date:
        inv_report = inv_report.filter(pl.col("sort_date") >= start_date)
        rec_report = rec_report.filter(pl.col("sort_date") >= start_date)
        inv_open = df_invoices.filter(pl.col("sort_date") < start_date)
        rec_open = df_receipts.filter(pl.col("sort_date") < start_date)
    else:
        inv_open = df_invoices.filter(False)
        rec_open = df_receipts.filter(False)

    if end_date:
        inv_report = inv_report.filter(pl.col("sort_date") <= end_date)
        rec_report = rec_report.filter(pl.col("sort_date") <= end_date)
        inv_close = df_invoices.filter(pl.col("sort_date") <= end_date)
        rec_close = df_receipts.filter(pl.col("sort_date") <= end_date)

    return {
        "invoices_report": inv_report.sort("number"),
        "receipts_report": rec_report.sort("number"),
        "invoices_open": inv_open,
        "receipts_open": rec_open,
        "invoices_close": inv_close,
        "receipts_close": rec_close,
    }
