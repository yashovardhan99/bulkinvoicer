"""Payment matching helpers.

This module contains functions to match receipts to invoices on a per-client
basis while keeping the logic simple and easy to test.
"""

from __future__ import annotations

from typing import Any
import logging
import polars as pl

from ..utils import match_payments

logger = logging.getLogger(__name__)


def match_payments_by_client(
    df_invoices: pl.DataFrame, df_receipts: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Match payments to invoices on a per-client basis.

    Returns updated copies of invoices and receipts with balance and match info.
    """
    # Early exits
    if df_invoices.is_empty() and df_receipts.is_empty():
        logger.warning("No invoices or receipts to match.")
        return (df_invoices, df_receipts)
    if df_receipts.is_empty():
        # No receipts: all invoices remain unpaid
        return (df_invoices.with_columns(pl.col("total").alias("balance")), df_receipts)

    logger.info("Matching payments to invoices.")

    matched: list[dict[str, Any]] = []
    unpaid: list[dict[str, Any]] = []

    clients = df_receipts.select("client").unique().to_series()

    for client_id in clients:
        inv = (
            df_invoices.filter(pl.col("client") == client_id)
            .sort("sort_date")  # stable FIFO
            .select("number", "total")  # only what match_payments needs
            .to_dicts()
        )
        rec = (
            df_receipts.filter(pl.col("client") == client_id)
            .sort("sort_date")  # stable FIFO
            .select("number", "amount")  # only what match_payments needs
            .to_dicts()
        )

        m_payments, u_invoices = match_payments(inv, rec)
        matched.extend(m_payments)
        unpaid.extend(u_invoices)

    # Build frames to join back
    df_matched = (
        pl.from_dicts(matched)
        if matched
        else pl.DataFrame(schema={"receipt": pl.Utf8, "invoices": pl.List})
    )
    df_unpaid_invoices = pl.from_dicts(
        unpaid, schema={"number": pl.Utf8, "balance": pl.Decimal}
    )

    # Join back to original frames
    df_receipts_out = df_receipts.join(
        df_matched, left_on="number", right_on="receipt", how="left"
    )
    df_invoices_out = df_invoices.join(df_unpaid_invoices, on="number", how="left")

    logger.info("Payments matched to invoices.")
    return (df_invoices_out, df_receipts_out)
