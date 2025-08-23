"""Data preparation module."""

import logging
from bulkinvoicer.config import Config

import polars as pl

logger = logging.getLogger(__name__)


def prepare_invoices(
    config: Config, df_invoice_data: pl.DataFrame, df_clients: pl.DataFrame
) -> pl.DataFrame:
    """Prepare invoices DataFrame from raw data."""
    tax_columns = config.invoice.tax_columns
    decimals = config.invoice.decimals
    date_format = config.invoice.date_format
    discount_column = config.invoice.discount_column

    df = (
        df_invoice_data.filter(pl.col("unit").is_not_null())
        .with_columns(
            pl.col("unit").cast(pl.Decimal(None, decimals)),
            pl.col("qty").cast(pl.UInt32()),
        )
        .with_columns(
            amount=(pl.col("unit") * pl.col("qty")).cast(pl.Decimal(None, decimals)),
        )
        .group_by("number")
        .agg(
            pl.max("date").cast(pl.Date),
            pl.coalesce(pl.max("due date"), pl.max("date"))
            .cast(pl.Date)
            .alias("due date"),
            pl.first("client"),
            pl.sum("amount").alias("subtotal"),
            (
                pl.sum(discount_column).cast(pl.Decimal(None, decimals))
                if discount_column
                else pl.lit(0)
            ).alias("discount"),
            pl.sum(*tax_columns).cast(pl.Decimal(None, decimals))
            if tax_columns
            else pl.lit(0).alias("tax-ignored"),
            pl.col("description", "unit", "qty", "amount"),
        )
        .join(
            df_clients,
            left_on="client",
            right_on="name",
            how="left",
        )
        .sort("number")
        .select(
            "number",
            pl.col("date").alias("sort_date"),
            pl.col("date").dt.to_string(date_format).alias("date"),
            pl.col("due date").dt.to_string(date_format).alias("due date"),
            pl.col("client"),
            pl.coalesce("display name", "client").alias("client_display_name"),
            pl.col("address").alias("client_address"),
            pl.col("phone").alias("client_phone"),
            pl.col("email").alias("client_email"),
            pl.col("description"),
            pl.col("unit"),
            pl.col("qty"),
            pl.col("amount"),
            pl.col("subtotal"),
            pl.col("discount"),
            pl.col(*tax_columns) if tax_columns else pl.col("tax-ignored"),
            (
                pl.sum_horizontal(
                    "subtotal",
                    pl.col("discount").neg(),
                    *tax_columns,
                )
            ).alias("total"),
        )
    )
    logger.info("Invoices DataFrame prepared.")
    return df


def prepare_receipts(
    config: Config, df_receipt_data: pl.DataFrame, df_clients: pl.DataFrame
) -> pl.DataFrame:
    """Prepare receipts DataFrame from raw data."""
    decimals = config.receipt.decimals
    df_receipts = (
        df_receipt_data.filter(pl.col("date").is_not_null())
        .with_columns(
            pl.col("amount").cast(pl.Decimal(None, decimals)),
        )
        .join(
            df_clients,
            left_on="client",
            right_on="name",
            how="left",
        )
        .sort("number")
        .select(
            "number",
            pl.col("date").cast(pl.Date).alias("sort_date"),
            pl.col("date")
            .cast(pl.Date)
            .dt.to_string(config.receipt.date_format)
            .alias("date"),
            pl.col("client"),
            pl.coalesce("display name", "client").alias("client_display_name"),
            pl.col("address").alias("client_address"),
            pl.col("phone").alias("client_phone"),
            pl.col("email").alias("client_email"),
            pl.col("amount").cast(pl.Decimal(None, decimals)),
            pl.col("payment mode"),
            pl.col("reference").cast(pl.Utf8),
        )
    )
    logger.info("Receipts DataFrame prepared.")
    return df_receipts
