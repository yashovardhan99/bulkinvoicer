"""Driver module for BulkInvoicer."""

from collections.abc import Mapping
import datetime
from decimal import Decimal
from pathlib import Path
import tomllib
import logging
from typing import Any
from collections.abc import Sequence
from fpdf import FontFace
import polars as pl
from bulkinvoicer.utils import PDF, format_currency, match_payments

# Configure logging
logger = logging.getLogger(__name__)


def load_config(config_file: str) -> Mapping[str, Any]:
    """Load configuration from a TOML file."""
    try:
        with open(config_file, "rb") as f:
            config = tomllib.load(f)
            logger.info("Configuration loaded successfully.")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Config: {config}")
            return config
    except FileNotFoundError:
        logger.error("Configuration file not found.")
        raise
    except tomllib.TOMLDecodeError as e:
        logger.error(f"Error decoding TOML file: {e}")
        raise


def generate_invoice(
    pdf: PDF, config: Mapping[str, Any], invoice_data: Mapping[str, Any]
) -> None:
    """Generate an invoice PDF using the provided configuration."""
    logger.info("Generating invoice with the provided configuration.")

    currency = config.get("payment", {}).get("currency", "INR")

    pdf.add_page(format="A4")

    pdf.print_invoice_header(invoice_data)

    pdf.set_font(pdf.regular_font.family, size=10)

    # Invoice Table

    header = (
        "Description".upper(),
        "Unit Price".upper(),
        "Qty".upper(),
        "Total".upper(),
    )

    descriptions: Sequence[str] = invoice_data.get("description", [])
    unit_prices: Sequence = invoice_data.get("unit", [])
    quantities: Sequence = invoice_data.get("qty", [])
    totals: Sequence = invoice_data.get("amount", [])

    invoice_items = zip(descriptions, unit_prices, quantities, totals)

    headings_style = FontFace.combine(
        pdf.header_font,
        FontFace(
            emphasis="BOLD",
            fill_color=config.get("invoice", {}).get("style-color"),
        ),
    )

    pdf.set_font(pdf.regular_font.family, size=10)
    with pdf.table(
        text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT"),
        borders_layout="MINIMAL",
        padding=2,
        headings_style=headings_style,
        col_widths=(7, 3, 2, 4),
    ) as table:
        table.row(header)
        for invoice_row in invoice_items:
            row = table.row()
            for item in invoice_row:
                value = item
                if type(value) is Decimal:
                    value = format_currency(value, currency)
                else:
                    value = str(value)

                row.cell(
                    value,
                    style=pdf.numbers_font
                    if isinstance(item, (Decimal, int, float))
                    else pdf.regular_font,
                )

        table.row()

        if config.get("invoice", {}).get("show-subtotal", True):
            subtotal_row = table.row(style=FontFace(emphasis="BOLD"))
            subtotal_row.cell(
                "Subtotal",
                colspan=3,
                align="LEFT",
            )
            subtotal_row.cell(
                format_currency(invoice_data.get("subtotal", Decimal()), currency),
                style=pdf.numbers_font,
            )

        if config.get("invoice", {}).get("discount-column", False):
            discount_row = table.row()
            discount_row.cell("Discount", colspan=3, align="RIGHT")
            discount_row.cell(
                format_currency(invoice_data.get("discount", Decimal()), currency),
                style=pdf.numbers_font,
            )

        for tax_column in config.get("invoice", {}).get("tax-columns", []):
            tax_row = table.row()
            tax_row.cell(tax_column.upper(), colspan=3, align="RIGHT", padding=(0, 2))
            tax_row.cell(
                format_currency(invoice_data.get(tax_column, Decimal()), currency),
                padding=(0, 2),
                style=pdf.numbers_font,
            )

        total_row = table.row(style=headings_style)
        total_row.cell("Total".upper(), colspan=3, align="RIGHT")
        total_row.cell(
            format_currency(invoice_data.get("total", Decimal()), currency),
            style=pdf.numbers_font,
        )

    pdf.ln(20)  # Line break for spacing

    section_start_y = pdf.get_y()
    pdf.print_invoice_payment_details(invoice_data)
    section_end_y = pdf.get_y()

    pdf.set_y(section_start_y)
    pdf.print_signature()

    pdf.set_y(max(pdf.get_y(), section_end_y))

    for i in range(20, 1, -1):
        if not pdf.will_page_break(i):
            pdf.ln(i)
            break


def generate_receipt(
    pdf: PDF, config: Mapping[str, Any], receipt_data: Mapping[str, Any]
) -> None:
    """Generate a receipt PDF using the provided configuration."""
    logger.info("Generating receipt with the provided configuration.")

    currency = config.get("payment", {}).get("currency", "INR")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Receipt data: {receipt_data}")

    pdf.add_page(format="A4")

    pdf.print_receipt_header(receipt_data)

    headings_style = FontFace(
        emphasis="BOLD", fill_color=config.get("receipt", {}).get("style-color")
    )

    pdf.set_font(pdf.regular_font.family, size=10)

    with pdf.table(
        text_align=("LEFT", "RIGHT"),
        borders_layout="MINIMAL",
        padding=2,
        headings_style=headings_style,
        col_widths=(3, 1),
    ) as table:
        table.row(("DESCRIPTION", "AMOUNT"))  # Header row

        for invoice in receipt_data.get("invoices", []):
            row = table.row()

            invoice_number = invoice.get("invoice")
            description = (
                f"Payment for Invoice {invoice_number}"
                if invoice_number
                else "Advance Payment"
            )
            row.cell(description)
            row.cell(
                format_currency(invoice.get("amount", Decimal()), currency),
                style=pdf.numbers_font,
            )

        table.row()

        total_row = table.row(style=headings_style)
        total_row.cell("Total".upper(), align="RIGHT")
        total_row.cell(
            format_currency(receipt_data.get("amount", Decimal()), currency),
            style=pdf.numbers_font,
        )

    pdf.ln(20)

    section_start_y = pdf.get_y()
    pdf.print_receipt_payment_details(receipt_data)
    section_end_y = pdf.get_y()
    pdf.set_y(section_start_y)
    pdf.print_signature()

    pdf.set_y(max(pdf.get_y(), section_end_y))

    for i in range(20, 1, -1):
        if not pdf.will_page_break(i):
            pdf.ln(i)
            break


def generate(config: Mapping[str, Any]) -> None:
    """Generate invoices and receipts based on provided configuration."""
    logger.info("Generating invoices and receipts with the provided configuration.")
    invoice_config = config.get("invoice", {})
    receipt_config = config.get("receipt", {})

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Invoice configuration: {invoice_config}")
        logger.debug(f"Receipt configuration: {receipt_config}")

    output_formats: Mapping[str, Any] = config.get("output", {})
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Output formats: {output_formats}")

    logger.info("Reading data from Excel files.")

    date_format = invoice_config.get("date-format", "iso")
    decimals = invoice_config.get("decimals", 2)

    df_invoice_data = pl.read_excel(
        config["excel"]["filepath"],
        sheet_name="invoices",
    )

    df_receipt_data = pl.read_excel(
        config["excel"]["filepath"],
        sheet_name="receipts",
    )

    df_clients = pl.read_excel(
        config["excel"]["filepath"],
        sheet_name="clients",
        schema_overrides={
            "name": pl.String,
            "display name": pl.String,
            "address": pl.String,
            "phone": pl.String,
            "email": pl.String,
        },
    )

    logger.info("Data loaded from Excel files.")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Invoice DataFrame: {df_invoice_data}")
        logger.debug(f"Clients DataFrame: {df_clients}")
        logger.debug(f"Receipt DataFrame: {df_receipt_data}")

    logger.info("Starting data preperation.")
    df_invoices = (
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
                pl.sum(invoice_config["discount-column"]).cast(
                    pl.Decimal(None, decimals)
                )
                if "discount-column" in invoice_config
                else pl.lit(None)
            ).alias("discount"),
            pl.sum(*invoice_config.get("tax-columns", [])).cast(
                pl.Decimal(None, decimals)
            )
            if invoice_config.get("tax-columns", False)
            else pl.lit(None),
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
            pl.col(*invoice_config.get("tax-columns", []))
            if invoice_config.get("tax-columns", False)
            else pl.lit(None).alias("tax-ignored"),
            (
                pl.sum_horizontal(
                    "subtotal",
                    pl.col("discount").neg(),
                    *invoice_config.get("tax-columns", []),
                )
            ).alias("total"),
        )
    )

    logger.info("Invoices DataFrame prepared.")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Prepared Invoices DataFrame: {df_invoices}")

    date_format = receipt_config.get("date-format", "iso")
    decimals = receipt_config.get("decimals", 2)

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
            pl.col("date").cast(pl.Date).dt.to_string(date_format).alias("date"),
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

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Prepared Receipts DataFrame: {df_receipts}")

    logger.info("Matching payments to invoices.")

    matched: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    for client in df_receipts.select("client").unique().iter_rows():
        df_invoices_client = df_invoices.filter(pl.col("client") == client[0])
        df_receipts_client = df_receipts.filter(pl.col("client") == client[0])
        matched_payments, unmatched_invoices = match_payments(
            df_invoices_client.to_dicts(),
            df_receipts_client.to_dicts(),
        )
        matched.extend(matched_payments)
        unmatched.extend(unmatched_invoices)

    df_matched = pl.from_dicts(matched)

    df_unpaid_invoices = pl.from_dicts(
        unmatched, schema={"number": pl.Utf8, "balance": pl.Decimal}
    )

    df_receipts = df_receipts.join(
        df_matched, left_on="number", right_on="receipt", how="inner"
    )

    df_invoices = df_invoices.join(df_unpaid_invoices, on="number", how="left")

    logger.info("Payments matched to invoices.")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Matched Receipts DataFrame: {df_receipts}")

    logger.info("Starting PDF generation.")

    for key, output_config in output_formats.items():
        logger.info(f"Starting with output format: {key}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Output format {key} configuration: {output_config}")

        path: str = output_config.get("path", "")

        if not path:
            logger.error(f"No path specified for output format: {key}")
            raise ValueError(f"Output format '{key}' requires a 'path' configuration.")

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        output_type = output_config.get("type")
        if not output_type:
            logger.error(f"No type specified for output format: {key}")
            raise ValueError(f"Output format '{key}' requires a 'type' configuration.")

        start_date = output_config.get("start-date")
        end_date = output_config.get("end-date")

        df_invoices_report = df_invoices.clone()
        df_receipts_report = df_receipts.clone()

        df_invoices_open = df_invoices_report.clone()
        df_receipts_open = df_receipts_report.clone()

        df_invoices_close = df_invoices_report.clone()
        df_receipts_close = df_receipts_report.clone()

        if start_date:
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            logger.info(f"Filtering invoices and receipts from {start_date} onwards.")
            df_invoices_report = df_invoices_report.filter(
                pl.col("sort_date") >= start_date
            )
            df_receipts_report = df_receipts_report.filter(
                pl.col("sort_date") >= start_date
            )

            df_invoices_open = df_invoices.filter(pl.col("sort_date") < start_date)
            df_receipts_open = df_receipts.filter(pl.col("sort_date") < start_date)
        else:
            df_invoices_open = df_invoices_open.filter(False)
            df_receipts_open = df_receipts_open.filter(False)

        if end_date:
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            logger.info(f"Filtering invoices and receipts until {end_date}.")
            df_invoices_report = df_invoices_report.filter(
                pl.col("sort_date") <= end_date
            )
            df_receipts_report = df_receipts_report.filter(
                pl.col("sort_date") <= end_date
            )

            df_invoices_close = df_invoices.filter(pl.col("sort_date") <= end_date)
            df_receipts_close = df_receipts.filter(pl.col("sort_date") <= end_date)

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
            reporting_period_text = (
                f"Period: Starting {start_date.strftime(date_format)}"
            )
        elif end_date:
            reporting_period_text = f"Period: Ending {end_date.strftime(date_format)}"

        # Get client wise total invoices, receipts, opening and closing balances
        clients = df_clients_close = pl.concat(
            [df_invoices_close.select("client"), df_receipts_close.select("client")]
        ).unique()

        client_summaries: dict[str, tuple] = {}

        include_summary = output_config.get("include-summary", False)

        if include_summary:
            for client in df_clients_close.iter_rows():
                client_id = client[0]
                logger.info(f"Generating summary data for client: {client_id}")
                client_summaries[client_id] = get_key_figures(
                    decimals,
                    df_invoices_open.filter(pl.col("client") == client_id),
                    df_receipts_open.filter(pl.col("client") == client_id),
                    df_invoices_close.filter(pl.col("client") == client_id),
                    df_receipts_close.filter(pl.col("client") == client_id),
                )

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"Client {client_id} summary: {client_summaries[client_id]}"
                    )

            df_client_summaries = pl.DataFrame(
                {
                    "client": [client for client in client_summaries.keys()],
                    "client_display_name": [
                        df_clients.filter(pl.col("name") == client)
                        .select("display name")
                        .item()
                        if df_clients.filter(pl.col("name") == client).height > 0
                        else client
                        for client in client_summaries.keys()
                    ],
                    "invoice_count": [
                        summary[0] for summary in client_summaries.values()
                    ],
                    "receipt_count": [
                        summary[1] for summary in client_summaries.values()
                    ],
                    "invoice_total": [
                        summary[2] for summary in client_summaries.values()
                    ],
                    "receipt_total": [
                        summary[3] for summary in client_summaries.values()
                    ],
                    "opening_balance": [
                        summary[4] for summary in client_summaries.values()
                    ],
                    "closing_balance": [
                        summary[5] for summary in client_summaries.values()
                    ],
                }
            )

            logger.info("Summarizing every client data together.")

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
            )

            (
                invoice_count,
                receipt_count,
                invoice_total,
                receipt_total,
                opening_balance,
                closing_balance,
            ) = df_client_summaries.sum().drop("client", "client_display_name").row(0)
            # Compute periodic key figures

            # Default start and end dates to last 12 months if not provided
            if not end_date:
                end_date = datetime.datetime.now().date()
            end_year, end_month = end_date.year, end_date.month
            if end_month == 12:
                expected_start_date = datetime.datetime(end_year, 1, 1).date()
            else:
                expected_start_date = datetime.datetime(
                    end_year - 1, end_month + 1, 1
                ).date()

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
                    pl.coalesce(
                        "client_display_name", "client_display_name_right"
                    ).alias("client_display_name"),
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

            df_balance_aggregated = (
                df_balance.drop("client", "client_display_name")
                .group_by("sort_date")
                .agg(pl.all().sum())
                .with_columns(
                    pl.col("sort_date").dt.month_end().alias("close_date"),
                )
                .sort("sort_date")
            )

            summary_details = {
                "period": reporting_period_text,
                "generated": f"Generated: {datetime.datetime.now().strftime(date_format)}",
                "key_figures": [
                    (
                        "Opening Balance: ",
                        opening_balance,
                        f"({'Due' if opening_balance > 0 else 'Overpaid'})"
                        if opening_balance != 0
                        else "",
                    ),
                    ("Total Invoiced: ", invoice_total, f"({invoice_count} invoices)"),
                    ("Total Received: ", receipt_total, f"({receipt_count} receipts)"),
                    (
                        "Closing Balance: ",
                        closing_balance,
                        f"({'Due' if closing_balance > 0 else 'Overpaid'})"
                        if closing_balance != 0
                        else "",
                    ),
                ],
                "status_breakdown": df_status_breakdown.to_dicts(),
                "monthly_summary": df_balance_aggregated.to_dicts(),
                "client_summaries": df_client_summaries.to_dicts(),
            }

        if output_type == "combined":
            logger.info("Generating combined PDF for all invoices and receipts.")

            pdf = PDF(config=config, cover_page=include_summary)
            pdf.set_title(key)

            if include_summary:
                logger.info("Including summary in the combined PDF.")
                pdf.add_combined_summary(summary_details)

            for invoice_data in df_invoices_report.to_dicts():
                generate_invoice(pdf, config, invoice_data)

            logger.info("Invoices generated successfully.")

            for receipt_data in df_receipts_report.to_dicts():
                generate_receipt(pdf, config, receipt_data)

            logger.info("Receipts generated successfully.")

            pdf.output(path)

        elif output_type == "individual":
            if include_summary:
                logger.info("Generating summary PDF")

                pdf = PDF(config=config, cover_page=True)
                pdf.set_title(f"{key} Overall Summary")

                pdf.add_combined_summary(summary_details)

                pdf.output(path.format(NUMBER="summary"))

            logger.info("Generating individual PDFs for each invoice and receipt.")

            for invoice_data in df_invoices_report.to_dicts():
                pdf = PDF(
                    config=config,
                )
                pdf.set_title(f"{key} Invoice {invoice_data['number']}")
                generate_invoice(pdf, config, invoice_data)
                pdf.output(path.format(NUMBER=invoice_data["number"]))

            logger.info("Individual invoices generated successfully.")

            for receipt_data in df_receipts_report.to_dicts():
                pdf = PDF(config=config)
                pdf.set_title(f"{key} Receipt {receipt_data['number']}")
                generate_receipt(pdf, config, receipt_data)
                pdf.output(path.format(NUMBER=receipt_data["number"]))

            logger.info("Individual receipts generated successfully.")

        elif output_type == "clients":
            if include_summary:
                logger.info("Generating summary PDF")

                pdf = PDF(config=config, cover_page=True)
                pdf.set_title(f"{key} Overall Summary")

                pdf.add_combined_summary(summary_details)

                pdf.output(path.format(CLIENT="summary"))

            logger.info("Generating PDFs for each client.")
            for client in clients.iter_rows():
                client_id = client[0]
                logger.info(f"Generating PDF for client: {client_id}")

                pdf = PDF(config=config, cover_page=include_summary)
                pdf.set_title(f"{key} {client_id}")

                # Add client summary if available
                if include_summary:
                    client_summary = df_client_summaries.filter(
                        pl.col("client") == client_id
                    ).row(0, named=True)

                    key_figures = [
                        (
                            "Opening Balance: ",
                            client_summary["opening_balance"],
                            f"({'Due' if client_summary['opening_balance'] > 0 else 'Advance'})"
                            if client_summary["opening_balance"] != 0
                            else "",
                        ),
                        (
                            "Total Billed: ",
                            client_summary["invoice_total"],
                            f"({client_summary['invoice_count']} invoices)",
                        ),
                        (
                            "Total Paid: ",
                            client_summary["receipt_total"],
                            f"({client_summary['receipt_count']} receipts)",
                        ),
                        (
                            "Current Outstanding: ",
                            client_summary["closing_balance"],
                            f"({'Due' if client_summary['closing_balance'] > 0 else 'Advance'})"
                            if client_summary["closing_balance"] != 0
                            else "",
                            "#ffcccc"
                            if client_summary["closing_balance"] > 0
                            else None,
                        ),
                    ]

                    df_balance_client = (
                        df_balance.filter(pl.col("client") == client_id)
                        .select(
                            "sort_date",
                            "open",
                            "invoiced",
                            "received",
                            "balance",
                        )
                        .sort("sort_date")
                    )

                    df_invoices_close_client = df_invoices_close.filter(
                        pl.col("client") == client_id
                    ).select(
                        "sort_date",
                        pl.col("date"),
                        pl.lit("Invoice").alias("type"),
                        pl.col("number").alias("reference"),
                        pl.col("total").alias("amount"),
                    )

                    df_receipts_close_client = df_receipts_close.filter(
                        pl.col("client") == client_id
                    ).select(
                        "sort_date",
                        pl.col("date"),
                        pl.lit("Receipt").alias("type"),
                        pl.col("number").alias("reference"),
                        pl.col("amount").neg(),
                    )

                    df_transactions = (
                        pl.concat([df_invoices_close_client, df_receipts_close_client])
                        .sort("sort_date")
                        .with_columns(pl.col("amount").cum_sum().alias("balance"))
                        .filter(pl.col("sort_date").is_between(start_date, end_date))
                    )

                    pdf.add_client_summary(
                        client=client_id,
                        client_display_name=client_summary["client_display_name"],
                        generated=f"Generated: {datetime.datetime.now().strftime(date_format)}",
                        period=reporting_period_text,
                        key_figures=key_figures,
                        monthly_summary=df_balance_client.to_dicts(),
                        transactions=df_transactions.to_dicts(),
                    )

                client_invoices = df_invoices_report.filter(
                    pl.col("client") == client_id
                )
                for invoice_data in client_invoices.to_dicts():
                    generate_invoice(pdf, config, invoice_data)

                logger.info(f"Invoices for client {client_id} generated successfully.")

                client_receipts = df_receipts_report.filter(
                    pl.col("client") == client_id
                )
                for receipt_data in client_receipts.to_dicts():
                    generate_receipt(pdf, config, receipt_data)

                logger.info(f"Receipts for client {client_id} generated successfully.")

                pdf.output(path.format(CLIENT=client_id))
        else:
            logger.error(f"Unknown output type: {output_type}")
            raise ValueError(
                f"Output format '{key}' has an unknown 'type': {output_type}"
            )


def get_key_figures(
    decimals: int,
    df_invoices_open: pl.DataFrame,
    df_receipts_open: pl.DataFrame,
    df_invoices_close: pl.DataFrame,
    df_receipts_close: pl.DataFrame,
):
    """Compute key figures based on input invoices and receipts."""
    logger.info("Computing key figures.")

    invoice_count = df_invoices_close.shape[0] - df_invoices_open.shape[0]
    receipt_count = df_receipts_close.shape[0] - df_receipts_open.shape[0]
    invoice_total = (
        df_invoices_close.select(pl.col("total").sum()).item()
        - df_invoices_open.select(pl.col("total").sum()).item()
    )
    receipt_total = (
        df_receipts_close.select(pl.col("amount").sum()).item()
        - df_receipts_open.select(pl.col("amount").sum()).item()
    )

    opening_balance = (
        df_invoices_open.select(
            pl.col("total").cast(pl.Decimal(None, decimals)).sum()
        ).item()
        - df_receipts_open.select(
            pl.col("amount").cast(pl.Decimal(None, decimals)).sum()
        ).item()
    )

    closing_balance = (
        df_invoices_close.select(
            pl.col("total").cast(pl.Decimal(None, decimals)).sum()
        ).item()
        - df_receipts_close.select(
            pl.col("amount").cast(pl.Decimal(None, decimals)).sum()
        ).item()
    )

    return (
        invoice_count,
        receipt_count,
        invoice_total,
        receipt_total,
        opening_balance,
        closing_balance,
    )


def main(config_file="config.toml") -> None:
    """Main function to run the BulkInvoicer."""
    try:
        config = load_config(config_file)

        # Validate file path for the Excel file
        if "excel" in config and "filepath" in config["excel"]:
            excel_filepath = config["excel"]["filepath"]
            logger.info(f"Excel file path: {excel_filepath}")
        else:
            raise ValueError("Excel file path is not specified in the configuration.")

        generate(config)
    except Exception as e:
        logger.critical(f"An error occurred: {e}")
        raise
