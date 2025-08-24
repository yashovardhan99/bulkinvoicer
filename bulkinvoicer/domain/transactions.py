"""Transaction helpers for building client transaction timelines."""

from __future__ import annotations

import datetime
import polars as pl


def build_client_transactions_df(
    start_date: datetime.date | None,
    end_date: datetime.date | None,
    df_invoices_close: pl.DataFrame,
    df_receipts_close: pl.DataFrame,
):
    """Build a transactions DataFrame for clients."""
    df_transactions = (
        pl.concat(
            [
                df_invoices_close.select(
                    "sort_date",
                    pl.col("date"),
                    pl.col("client"),
                    pl.lit("Invoice").alias("type"),
                    pl.col("number").alias("reference"),
                    pl.col("total").alias("amount"),
                ),
                df_receipts_close.select(
                    "sort_date",
                    pl.col("date"),
                    pl.col("client"),
                    pl.lit("Receipt").alias("type"),
                    pl.col("number").alias("reference"),
                    pl.col("amount").neg(),
                ),
            ]
        )
        .sort("sort_date")
        .with_columns(pl.col("amount").cum_sum().over("client").alias("balance"))
        .filter(pl.col("sort_date").is_between(start_date, end_date))
    )

    return df_transactions
