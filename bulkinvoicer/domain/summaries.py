"""Client summaries and status breakdown helpers."""

from __future__ import annotations
from datetime import datetime
from typing import Any

import polars as pl


def build_client_summaries(
    df_clients: pl.DataFrame,
    df_invoices_open: pl.DataFrame,
    df_invoices_close: pl.DataFrame,
    df_receipts_open: pl.DataFrame,
    df_receipts_close: pl.DataFrame,
) -> pl.DataFrame:
    """Build a DataFrame summarizing client data."""
    # Group all invoices and receipts by client

    df_invoices_open_grouped = (
        df_invoices_open.group_by("client")
        .agg(
            pl.count("number").alias("invoice_count_open"),
            pl.sum("total").alias("invoice_total_open"),
        )
        .with_columns(pl.col("invoice_total_open").cast(pl.Decimal))
    )

    df_invoices_close_grouped = (
        df_invoices_close.group_by("client")
        .agg(
            pl.count("number").alias("invoice_count_close"),
            pl.sum("total").alias("invoice_total_close"),
        )
        .with_columns(pl.col("invoice_total_close").cast(pl.Decimal))
    )

    df_receipts_open_grouped = (
        df_receipts_open.group_by("client")
        .agg(
            pl.count("number").alias("receipt_count_open"),
            pl.sum("amount").alias("receipt_total_open"),
        )
        .with_columns(pl.col("receipt_total_open").cast(pl.Decimal))
    )

    df_receipts_close_grouped = (
        df_receipts_close.group_by("client")
        .agg(
            pl.count("number").alias("receipt_count_close"),
            pl.sum("amount").alias("receipt_total_close"),
        )
        .with_columns(pl.col("receipt_total_close").cast(pl.Decimal))
    )

    # Combine all grouped data into a single DataFrame

    df_combined = (
        df_clients.join(df_invoices_open_grouped, on="client", how="left")
        .join(df_invoices_close_grouped, on="client", how="left")
        .join(df_receipts_open_grouped, on="client", how="left")
        .join(df_receipts_close_grouped, on="client", how="left")
        .fill_null(0)
        .select(
            pl.col("client"),
            pl.coalesce(pl.col("display name"), pl.col("client")).alias(
                "client_display_name"
            ),
            pl.col("address").alias("client_address"),
            pl.col("phone").alias("client_phone"),
            pl.col("email").alias("client_email"),
            invoice_count=(
                pl.col("invoice_count_close") - pl.col("invoice_count_open")
            ),
            receipt_count=(
                pl.col("receipt_count_close") - pl.col("receipt_count_open")
            ),
            invoice_total=(
                pl.col("invoice_total_close") - pl.col("invoice_total_open")
            ),
            receipt_total=(
                pl.col("receipt_total_close") - pl.col("receipt_total_open")
            ),
            opening_balance=(
                pl.col("invoice_total_open") - pl.col("receipt_total_open")
            ),
            closing_balance=(
                pl.col("invoice_total_close") - pl.col("receipt_total_close")
            ),
        )
        .sort("closing_balance", "invoice_total", descending=True)
    )

    return df_combined


def build_status_breakdown(df_client_summaries: pl.DataFrame) -> pl.DataFrame:
    """Build a status breakdown DataFrame from client summaries."""
    df_status_breakdown = (
        df_client_summaries.with_columns(
            pl.when(pl.col("closing_balance") > 0)
            .then(pl.lit("Outstanding"))
            .when(pl.col("closing_balance") < 0)
            .then(pl.lit("Advance"))
            .otherwise(pl.lit("Settled"))
            .alias("status"),
        )
        .group_by("status")
        .agg(
            pl.count("client").alias("Clients"),
            pl.sum("closing_balance").alias("amount"),
        )
        .with_columns(pl.col("status").cast(pl.Categorical))
        .sort("status")  # or map a custom order if desired
    )

    return df_status_breakdown


def build_summary_report(
    date_format_invoice: str,
    reporting_period_text: str | None,
    df_client_summaries: pl.DataFrame,
    df_status_breakdown: pl.DataFrame,
    df_balance_aggregated: pl.DataFrame,
) -> dict[str, Any]:
    """Build a summary report dictionary."""
    (
        invoice_count,
        receipt_count,
        invoice_total,
        receipt_total,
        opening_balance,
        closing_balance,
    ) = (
        df_client_summaries.select(
            "invoice_count",
            "receipt_count",
            "invoice_total",
            "receipt_total",
            "opening_balance",
            "closing_balance",
        )
        .sum()
        .row(0)
    )
    summary_details = {
        "period": reporting_period_text,
        "generated": f"Generated: {datetime.now().strftime(date_format_invoice)}",
        "key_figures": [
            (
                "Opening Balance",
                opening_balance,
                f"({'Due' if opening_balance > 0 else 'Overpaid'})"
                if opening_balance != 0
                else "",
            ),
            (
                "Total Invoiced",
                invoice_total,
                f"({invoice_count} invoices)",
            ),
            (
                "Total Received",
                receipt_total,
                f"({receipt_count} receipts)",
            ),
            (
                "Closing Balance",
                closing_balance,
                f"({'Due' if closing_balance > 0 else 'Overpaid'})"
                if closing_balance != 0
                else "",
            ),
        ],
        "status_breakdown": df_status_breakdown.to_dicts(),
        "monthly_summary": df_balance_aggregated.to_dicts(),
        "client_summaries": df_client_summaries.filter(
            (pl.col("opening_balance") != 0)
            | (pl.col("closing_balance") != 0)
            | (pl.col("invoice_total") != 0)
            | (pl.col("receipt_total") != 0)
        ).to_dicts(),
    }

    return summary_details
