"""Driver module for BulkInvoicer."""

from collections.abc import Mapping
import logging.config
from pathlib import Path
import tomllib
import logging
from typing import Any
from collections.abc import Sequence
from fpdf import FontFace
import polars as pl
from bulkinvoicer.utils import PDF, match_payments

# Configure logging
logger = logging.getLogger(__name__)


def load_config() -> Mapping[str, Any]:
    """Load configuration from a TOML file."""
    try:
        with open("sample.config.toml", "rb") as f:
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
    pdf.add_page(format="A4")

    pdf.print_invoice_header(invoice_data)

    pdf.set_font("times", size=10)

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

    headings_style = FontFace(emphasis="BOLD", fill_color=(248, 230, 229))
    with pdf.table(
        text_align=("LEFT", "CENTER", "CENTER", "RIGHT"),
        borders_layout="NONE",
        padding=2,
        headings_style=headings_style,
    ) as table:
        header_row = table.row()
        for item in header:
            header_row.cell(item)

        for invoice_row in invoice_items:
            row = table.row()
            for item in invoice_row:
                row.cell(str(item))

        table.row()

        if config.get("invoice", {}).get("show-subtotal", True):
            subtotal_row = table.row(style=FontFace(emphasis="BOLD"))
            subtotal_row.cell("Subtotal", colspan=3, align="LEFT")
            subtotal_row.cell(str(invoice_data.get("subtotal", "0.00")))

        if config.get("invoice", {}).get("discount-column", False):
            discount_row = table.row()
            discount_row.cell("Discount", colspan=3, align="RIGHT")
            discount_row.cell(str(invoice_data.get("discount", "0.00")))

        for tax_column in config.get("invoice", {}).get("tax-columns", []):
            tax_row = table.row()
            tax_row.cell(tax_column.upper(), colspan=3, align="RIGHT", padding=(0, 2))
            tax_row.cell(str(invoice_data.get(tax_column, "0.00")), padding=(0, 2))

        total_row = table.row(style=headings_style)
        total_row.cell("Total".upper(), colspan=3, align="RIGHT")
        total_row.cell(str(invoice_data.get("total", "0.00")))

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

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Receipt data: {receipt_data}")

    pdf.add_page(format="A4")

    pdf.print_receipt_header(receipt_data)

    pdf.set_font("times", size=10)

    headings_style = FontFace(emphasis="BOLD", fill_color=(248, 230, 229))
    with pdf.table(
        text_align=("LEFT", "RIGHT"),
        borders_layout="NONE",
        padding=2,
        headings_style=headings_style,
    ) as table:
        header_row = table.row()
        header_row.cell("Description".upper())
        header_row.cell("Amount".upper())

        for invoice in receipt_data.get("invoices", []):
            row = table.row()

            invoice_number = invoice.get("invoice")
            description = (
                f"Payment for Invoice {invoice_number}"
                if invoice_number
                else "Advance Payment"
            )
            row.cell(description)
            row.cell(str(invoice.get("amount", "0.00")))

        total_row = table.row(style=headings_style)
        total_row.cell("Total".upper(), align="RIGHT")
        total_row.cell(str(receipt_data.get("amount", "0.00")))

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
        df_invoice_data.with_columns(
            pl.col("unit").cast(pl.Decimal(None, decimals)),
            pl.col("qty").cast(pl.UInt32()),
            amount=(pl.col("unit") * pl.col("qty")).cast(pl.Decimal(None, decimals)),
        )
        .group_by("number")
        .agg(
            pl.max("date"),
            pl.max("due date"),
            pl.first("client"),
            pl.sum("amount").alias("subtotal"),
            (
                pl.sum(invoice_config["discount-column"])
                if "discount-column" in invoice_config
                else pl.lit(None)
            )
            .cast(pl.Decimal(None, decimals))
            .alias("discount"),
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
            pl.col("date").dt.to_string(date_format).alias("date"),
            pl.col("due date").dt.to_string(date_format).alias("due date"),
            pl.coalesce("client", "display name").alias("client"),
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
        df_receipt_data.with_columns(
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
            pl.col("date").dt.to_string(date_format).alias("date"),
            pl.coalesce("client", "display name").alias("client"),
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

    for client in df_receipts.select("client").unique().iter_rows():
        df_invoices_client = df_invoices.filter(pl.col("client") == client[0])
        df_receipts_client = df_receipts.filter(pl.col("client") == client[0])
        matched.extend(
            match_payments(
                df_invoices_client.to_dicts(),
                df_receipts_client.to_dicts(),
            )
        )

    df_matched = pl.from_dicts(matched)

    df_receipts = df_receipts.join(
        df_matched, left_on="number", right_on="receipt", how="inner"
    )

    logger.info("Payments matched to invoices.")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Matched Receipts DataFrame: {df_receipts}")

    logger.info("Starting PDF generation.")

    for key, value in output_formats.items():
        logger.info(f"Starting with output format: {key}")
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(f"Output format {key} configuration: {value}")

        path: str = value.get("path", "")

        if not path:
            logger.error(f"No path specified for output format: {key}")
            raise ValueError(f"Output format '{key}' requires a 'path' configuration.")

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        output_type = value.get("type")
        if not output_type:
            logger.error(f"No type specified for output format: {key}")
            raise ValueError(f"Output format '{key}' requires a 'type' configuration.")

        if output_type == "combined":
            logger.info("Generating combined PDF for all invoices and receipts.")
            pdf = PDF(config=config)
            pdf.set_title(key)

            for invoice_data in df_invoices.to_dicts():
                generate_invoice(pdf, config, invoice_data)

            logger.info("Invoices generated successfully.")

            for receipt_data in df_receipts.to_dicts():
                generate_receipt(pdf, config, receipt_data)

            logger.info("Receipts generated successfully.")

            pdf.output(path)

        elif output_type == "individual":
            logger.info("Generating individual PDFs for each invoice and receipt.")

            for invoice_data in df_invoices.to_dicts():
                pdf = PDF(config=config)
                pdf.set_title(f"{key} Invoice {invoice_data['number']}")
                generate_invoice(pdf, config, invoice_data)
                pdf.output(path.format(NUMBER=invoice_data["number"]))

            logger.info("Individual invoices generated successfully.")

            for receipt_data in df_receipts.to_dicts():
                pdf = PDF(config=config)
                pdf.set_title(f"{key} Receipt {receipt_data['number']}")
                generate_receipt(pdf, config, receipt_data)
                pdf.output(path.format(NUMBER=receipt_data["number"]))

            logger.info("Individual receipts generated successfully.")

        elif output_type == "clients":
            logger.info("Generating PDFs for each client.")
            clients = df_invoices.select("client").unique().iter_rows()
            for client in clients:
                client_name = client[0]
                logger.info(f"Generating PDF for client: {client_name}")
                pdf = PDF(config=config)
                pdf.set_title(f"{key} {client_name}")

                client_invoices = df_invoices.filter(pl.col("client") == client_name)
                for invoice_data in client_invoices.to_dicts():
                    generate_invoice(pdf, config, invoice_data)

                logger.info(
                    f"Invoices for client {client_name} generated successfully."
                )

                client_receipts = df_receipts.filter(pl.col("client") == client_name)
                for receipt_data in client_receipts.to_dicts():
                    generate_receipt(pdf, config, receipt_data)

                logger.info(
                    f"Receipts for client {client_name} generated successfully."
                )

                pdf.output(path.format(CLIENT=client_name))
        else:
            logger.error(f"Unknown output type: {output_type}")
            raise ValueError(
                f"Output format '{key}' has an unknown 'type': {output_type}"
            )


def main() -> None:
    """Main function to run the BulkInvoicer."""
    try:
        config = load_config()

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


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
