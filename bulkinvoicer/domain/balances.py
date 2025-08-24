"""Monthly balance computations and date-period normalization."""

from __future__ import annotations

import datetime
import logging
import polars as pl

logger = logging.getLogger(__name__)


def normalize_date_period(
    start_date: datetime.date | None, end_date: datetime.date | None
) -> tuple[datetime.date, datetime.date]:
    """Normalize start and end dates to ensure a maximum of 12 months period."""
    if not end_date:
        end_date = datetime.datetime.now().date()
    end_year, end_month = end_date.year, end_date.month
    if end_month == 12:
        expected_start_date = datetime.datetime(end_year, 1, 1).date()
    else:
        expected_start_date = datetime.datetime(end_year - 1, end_month + 1, 1).date()

    if not start_date:
        start_date = expected_start_date
    else:
        # If the start date is more than a year before the end date, adjust it
        if start_date < expected_start_date:
            logger.warning(
                "The truncated date range is more than a year. "
                "Periodic summary will be limited to last 12 months."
            )
            start_date = expected_start_date
    return start_date, end_date


def compute_monthly_client_balances(
    start_date: datetime.date,
    end_date: datetime.date,
    df_invoices_close: pl.DataFrame,
    df_receipts_close: pl.DataFrame,
    df_clients_close: pl.DataFrame,
) -> pl.DataFrame:
    """Compute monthly balances for clients."""
    logger.info(f"Generating periodic summary from {start_date} to {end_date}.")

    df_date_range = (
        pl.date_range(start=start_date, end=end_date, interval="1d", eager=True)
        .to_frame("sort_date")
        .group_by_dynamic("sort_date", every="1mo", start_by="window")
        .agg()
    )

    df_date_client_range = df_date_range.join(
        df_clients_close,
        how="cross",
    )

    df_invoice_monthly = (
        df_invoices_close.sort("sort_date")
        .group_by_dynamic("sort_date", every="1mo", group_by="client")
        .agg(pl.col("total").sum(), pl.first("client_display_name"))
        .join(
            df_date_client_range,
            on=["sort_date", "client"],
            how="full",
            coalesce=True,
        )
        .fill_null(0)
    )

    df_receipts_monthly = (
        df_receipts_close.sort("sort_date")
        .group_by_dynamic("sort_date", every="1mo", group_by="client")
        .agg(pl.col("amount").sum(), pl.first("client_display_name"))
        .join(
            df_date_client_range,
            on=["sort_date", "client"],
            how="full",
            coalesce=True,
        )
        .fill_null(0)
    )

    df_balance = (
        df_invoice_monthly.join(
            df_receipts_monthly,
            on=["client", "sort_date"],
            coalesce=True,
            how="full",
        )
        .fill_null(0)
        .sort("sort_date")
        .select(
            "client",
            pl.coalesce("client_display_name", "client_display_name_right").alias(
                "client_display_name"
            ),
            "sort_date",
            pl.col("total").alias("invoiced"),
            pl.col("amount").alias("received"),
            (pl.col("total") - pl.col("amount"))
            .cum_sum()
            .over("client")
            .alias("balance"),
        )
        .with_columns(
            open=pl.col("balance").shift(1, fill_value=0).over("client"),
        )
        .filter(pl.col("sort_date").is_between(start_date, end_date))
        .select(
            "client",
            "client_display_name",
            "sort_date",
            "open",
            "invoiced",
            "received",
            "balance",
        )
    )

    return df_balance


def summarize_balance_data(df_balance: pl.DataFrame) -> pl.DataFrame:
    """Summarize balance data by month-end."""
    df_balance_aggregated = (
        df_balance.drop("client", "client_display_name")
        .group_by("sort_date")
        .agg(pl.all().sum())
        .with_columns(
            pl.col("sort_date").dt.month_end().alias("close_date"),
        )
        .filter((pl.col("invoiced") != 0) | (pl.col("received") != 0))
        .sort("sort_date")
    )

    return df_balance_aggregated
