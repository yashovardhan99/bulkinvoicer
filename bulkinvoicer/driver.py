"""Driver module for BulkInvoicer."""

import datetime
from pathlib import Path
import tomllib
import logging
from typing import Any
import polars as pl
from pydantic import ValidationError
from bulkinvoicer.config import Config
from bulkinvoicer.utils import match_payments
from bulkinvoicer.pdf import PDF
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

# Configure logging
logger = logging.getLogger(__name__)


def load_config(config_file: str) -> Config:
    """Load configuration from a TOML file."""
    try:
        with open(config_file, "rb") as f:
            config = tomllib.load(f)
            logger.info("Configuration loaded successfully.")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Config: {config}")

            return Config.model_validate(config)

    except FileNotFoundError:
        logger.critical("Configuration file not found.")
        raise
    except tomllib.TOMLDecodeError:
        logger.critical("Error decoding TOML file")
        raise
    except ValidationError as e:
        logger.critical("Configuration validation failed.")
        for error in e.errors():
            loc = ".".join(str(x) for x in error["loc"])
            logger.critical(
                f"Error in field '{loc}': {error['msg']}. Provided input: {error['input']}"
            )
        raise


def generate(config: Config) -> None:
    """Generate invoices and receipts based on provided configuration."""
    logger.info("Starting the generation process.")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Configuration: %s", config)

    logger.info("Reading data from Excel files.")

    date_format_invoice = config.invoice.date_format
    decimals_invoice = config.invoice.decimals

    date_format_receipt = config.receipt.date_format
    decimals_receipt = config.receipt.decimals

    df_invoice_data = pl.read_excel(
        config.excel.filepath,
        sheet_name="invoices",
    )

    df_receipt_data = pl.read_excel(
        config.excel.filepath,
        sheet_name="receipts",
    )

    df_clients = pl.read_excel(
        config.excel.filepath,
        sheet_name="clients",
        schema_overrides={
            "name": pl.String,
            "display name": pl.String,
            "address": pl.String,
            "phone": pl.String,
            "email": pl.String,
        },
    )

    logger.info("Data loaded from Excel files. Starting data processing.")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Invoice DataFrame: %s", df_invoice_data)
        logger.debug("Clients DataFrame: %s", df_clients)
        logger.debug("Receipt DataFrame: %s", df_receipt_data)

    df_invoices = (
        df_invoice_data.filter(pl.col("unit").is_not_null())
        .with_columns(
            pl.col("unit").cast(pl.Decimal(None, decimals_invoice)),
            pl.col("qty").cast(pl.UInt32()),
        )
        .with_columns(
            amount=(pl.col("unit") * pl.col("qty")).cast(
                pl.Decimal(None, decimals_invoice)
            ),
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
                pl.sum(config.invoice.discount_column).cast(
                    pl.Decimal(None, decimals_invoice)
                )
                if config.invoice.discount_column
                else pl.lit(0)
            ).alias("discount"),
            pl.sum(*config.invoice.tax_columns).cast(pl.Decimal(None, decimals_invoice))
            if config.invoice.tax_columns
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
            pl.col("date").dt.to_string(date_format_invoice).alias("date"),
            pl.col("due date").dt.to_string(date_format_invoice).alias("due date"),
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
            pl.col(*config.invoice.tax_columns)
            if config.invoice.tax_columns
            else pl.col("tax-ignored"),
            (
                pl.sum_horizontal(
                    "subtotal",
                    pl.col("discount").neg(),
                    *config.invoice.tax_columns,
                )
            ).alias("total"),
        )
    )

    logger.info("Invoices DataFrame prepared.")

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Prepared Invoices DataFrame: {df_invoices}")

    df_receipts = (
        df_receipt_data.filter(pl.col("date").is_not_null())
        .with_columns(
            pl.col("amount").cast(pl.Decimal(None, decimals_receipt)),
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
            .dt.to_string(date_format_receipt)
            .alias("date"),
            pl.col("client"),
            pl.coalesce("display name", "client").alias("client_display_name"),
            pl.col("address").alias("client_address"),
            pl.col("phone").alias("client_phone"),
            pl.col("email").alias("client_email"),
            pl.col("amount").cast(pl.Decimal(None, decimals_receipt)),
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

    if matched:
        df_matched = pl.from_dicts(matched)
    else:
        df_matched = pl.DataFrame(schema={"receipt": pl.Utf8, "invoices": pl.List})

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

    with tqdm(
        config.output.items(),
        desc="Generating Outputs",
        leave=False,
    ) as output_format_pbar:
        with logging_redirect_tqdm():
            for key, output_config in output_format_pbar:
                logger.info(f"Starting with output format: {key}")
                output_format_pbar.set_description(f"Generating {key} output")
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"Output format {key} configuration: {output_config}")

                path: str = output_config.path

                if not path:
                    logger.error(f"No path specified for output format: {key}")
                    raise ValueError(
                        f"Output format '{key}' requires a 'path' configuration."
                    )

                Path(path).parent.mkdir(parents=True, exist_ok=True)

                output_type = output_config.type
                if not output_type:
                    logger.error(f"No type specified for output format: {key}")
                    raise ValueError(
                        f"Output format '{key}' requires a 'type' configuration."
                    )

                start_date = output_config.start_date
                end_date = output_config.end_date

                df_invoices_report = df_invoices.clone()
                df_receipts_report = df_receipts.clone()

                df_invoices_open = df_invoices_report.clone()
                df_receipts_open = df_receipts_report.clone()

                df_invoices_close = df_invoices_report.clone()
                df_receipts_close = df_receipts_report.clone()

                if start_date:
                    logger.info(
                        f"Filtering invoices and receipts from {start_date} onwards."
                    )
                    df_invoices_report = df_invoices_report.filter(
                        pl.col("sort_date") >= start_date
                    )
                    df_receipts_report = df_receipts_report.filter(
                        pl.col("sort_date") >= start_date
                    )

                    df_invoices_open = df_invoices.filter(
                        pl.col("sort_date") < start_date
                    )
                    df_receipts_open = df_receipts.filter(
                        pl.col("sort_date") < start_date
                    )
                else:
                    df_invoices_open = df_invoices_open.filter(False)
                    df_receipts_open = df_receipts_open.filter(False)

                if end_date:
                    logger.info(f"Filtering invoices and receipts until {end_date}.")
                    df_invoices_report = df_invoices_report.filter(
                        pl.col("sort_date") <= end_date
                    )
                    df_receipts_report = df_receipts_report.filter(
                        pl.col("sort_date") <= end_date
                    )

                    df_invoices_close = df_invoices.filter(
                        pl.col("sort_date") <= end_date
                    )
                    df_receipts_close = df_receipts.filter(
                        pl.col("sort_date") <= end_date
                    )

                df_invoices_report = df_invoices_report.sort("number")
                df_receipts_report = df_receipts_report.sort("number")

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

                    reporting_period_text = f"Period: {start_date.strftime(date_format_invoice)} - {end_date.strftime(date_format_invoice)}"
                elif start_date:
                    reporting_period_text = (
                        f"Period: Starting {start_date.strftime(date_format_invoice)}"
                    )
                elif end_date:
                    reporting_period_text = (
                        f"Period: Ending {end_date.strftime(date_format_invoice)}"
                    )

                # Get client wise total invoices, receipts, opening and closing balances
                clients = df_clients_close = pl.concat(
                    [
                        df_invoices_close.select("client"),
                        df_receipts_close.select("client"),
                    ]
                ).unique()

                client_summaries: dict[str, tuple] = {}

                include_summary = output_config.include_summary

                if include_summary:
                    for client in df_clients_close.iter_rows():
                        client_id = client[0]
                        logger.info(f"Generating summary data for client: {client_id}")
                        client_summaries[client_id] = get_key_figures(
                            decimals_invoice,
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
                            "client_details": [
                                df_clients.filter(pl.col("name") == client)
                                .select("display name", "address", "phone", "email")
                                .row(0)
                                if df_clients.filter(pl.col("name") == client).height
                                > 0
                                else (client, None, None, None)
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
                    ).sort("closing_balance", "invoice_total", descending=True)

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
                    ) = (
                        df_client_summaries.sum()
                        .drop("client", "client_details")
                        .row(0)
                    )
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

                    logger.info(
                        f"Generating periodic summary from {start_date} to {end_date}."
                    )

                    df_date_range = (
                        pl.date_range(
                            start=start_date, end=end_date, interval="1d", eager=True
                        )
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
                            open=pl.col("balance")
                            .shift(1, fill_value=0)
                            .over("client"),
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
                        .filter((pl.col("invoiced") != 0) | (pl.col("received") != 0))
                        .sort("sort_date")
                    )

                    df_client_summaries = df_client_summaries.with_columns(
                        pl.coalesce(
                            pl.col("client_details").list.get(0), pl.col("client")
                        ).alias("client_display_name"),
                        pl.col("client_details").list.get(1).alias("client_address"),
                        pl.col("client_details").list.get(2).alias("client_phone"),
                        pl.col("client_details").list.get(3).alias("client_email"),
                    ).drop("client_details")

                    summary_details = {
                        "period": reporting_period_text,
                        "generated": f"Generated: {datetime.datetime.now().strftime(date_format_invoice)}",
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
                else:
                    df_client_summaries = None
                    df_balance = None

                if output_type == "combined":
                    logger.info(
                        "Generating combined PDF for all invoices and receipts."
                    )

                    pdf = PDF(
                        config=config,
                        cover_page=include_summary,
                    )
                    pdf.set_title(key)

                    if include_summary:
                        logger.info("Including summary in the combined PDF.")
                        pdf.add_combined_summary(summary_details, toc_level=1)

                    for i, invoice_data in tqdm(
                        enumerate(df_invoices_report.to_dicts()),
                        total=df_invoices_report.height,
                        leave=False,
                        desc="Generating Invoices",
                    ):
                        pdf.generate_invoice(
                            invoice_data,
                            start_section=i == 0,
                            create_toc_entry=True,
                        )

                    logger.info("Invoices generated successfully.")

                    # pdf.start_section("Receipts")
                    for i, receipt_data in tqdm(
                        enumerate(df_receipts_report.to_dicts()),
                        total=df_receipts_report.height,
                        leave=False,
                        desc="Generating Receipts",
                    ):
                        pdf.generate_receipt(
                            receipt_data,
                            start_section=i == 0,
                            create_toc_entry=True,
                        )

                    logger.info("Receipts generated successfully.")

                    pdf.output(path)

                elif output_type == "individual":
                    if include_summary:
                        logger.info("Generating summary PDF")

                        pdf = PDF(
                            config=config,
                            cover_page=True,
                        )
                        pdf.set_title(f"{key} Overall Summary")

                        pdf.add_combined_summary(summary_details, toc_level=0)

                        pdf.output(path.format(NUMBER="summary"))

                    logger.info(
                        "Generating individual PDFs for each invoice and receipt."
                    )

                    with ProcessPoolExecutor() as executor:
                        future_invoices = [
                            executor.submit(generate_invoice_pdf, config, invoice_data)
                            for invoice_data in df_invoices_report.to_dicts()
                        ]
                        future_receipts = [
                            executor.submit(generate_receipt_pdf, config, receipt_data)
                            for receipt_data in df_receipts_report.to_dicts()
                        ]

                        with ThreadPoolExecutor() as thread_executor:
                            futures = []
                            for future in tqdm(
                                as_completed(future_invoices + future_receipts),
                                total=len(future_invoices) + len(future_receipts),
                                desc="Generating Invoices and Receipts",
                                leave=False,
                            ):
                                number, pdfbytes = future.result()
                                futures.append(
                                    thread_executor.submit(
                                        write_pdf, path.format(NUMBER=number), pdfbytes
                                    )
                                )

                            for _ in tqdm(
                                as_completed(futures),
                                total=len(futures),
                                desc="Saving Invoices and Receipts",
                                leave=False,
                            ):
                                pass

                    logger.info(
                        "Individual invoices and receipts generated successfully."
                    )

                elif output_type == "clients":
                    if include_summary:
                        logger.info("Generating summary PDF")

                        pdf = PDF(
                            config=config,
                            cover_page=True,
                        )
                        pdf.set_title(f"{key} Overall Summary")

                        pdf.add_combined_summary(summary_details, toc_level=0)

                        pdf.output(path.format(CLIENT="summary"))

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
                            .with_columns(
                                pl.col("amount")
                                .cum_sum()
                                .over("client")
                                .alias("balance")
                            )
                            .filter(
                                pl.col("sort_date").is_between(start_date, end_date)
                            )
                        )
                    else:
                        df_transactions = None

                    logger.info("Generating PDFs for each client.")

                    with ProcessPoolExecutor() as executor:
                        futures = [
                            executor.submit(
                                generate_client_pdf,
                                config,
                                client_id,
                                df_invoices_report.filter(
                                    pl.col("client") == client_id
                                ).to_dicts(),
                                df_receipts_report.filter(
                                    pl.col("client") == client_id
                                ).to_dicts(),
                                df_transactions.filter(pl.col("client") == client_id)
                                .drop("client")
                                .to_dicts()
                                if df_transactions is not None
                                else None,
                                reporting_period_text,
                                include_summary,
                                df_client_summaries.filter(
                                    pl.col("client") == client_id
                                ).row(0, named=True)
                                if df_client_summaries is not None
                                else {},
                                df_balance.filter(
                                    (pl.col("client") == client_id)
                                    & (
                                        (pl.col("invoiced") != 0)
                                        | (pl.col("received") != 0)
                                    )
                                )
                                .select(
                                    "sort_date",
                                    "open",
                                    "invoiced",
                                    "received",
                                    "balance",
                                )
                                .sort("sort_date")
                                .to_dicts()
                                if df_balance is not None
                                else None,
                            )
                            for client_id in clients.to_series()
                        ]

                        with ThreadPoolExecutor() as thread_executor:
                            futures_pdfs = []

                            for future in tqdm(
                                as_completed(futures),
                                total=len(futures),
                                desc="Generating Client Statements",
                                leave=False,
                            ):
                                client_id, pdfbytes = future.result()
                                futures_pdfs.append(
                                    thread_executor.submit(
                                        write_pdf,
                                        path.format(CLIENT=client_id),
                                        pdfbytes,
                                    )
                                )

                            for _ in tqdm(
                                as_completed(futures_pdfs),
                                total=len(futures_pdfs),
                                desc="Saving Client Statements",
                                leave=False,
                            ):
                                pass

                    logger.info("Client PDFs generated successfully.")

                else:
                    logger.error(f"Unknown output type: {output_type}")
                    raise ValueError(
                        f"Output format '{key}' has an unknown 'type': {output_type}"
                    )


def generate_client_pdf(
    config: Config,
    client_id: str,
    client_invoices: list[dict[str, Any]],
    client_receipts: list[dict[str, Any]],
    client_transactions: list[dict[str, Any]] | None,
    reporting_period_text: str | None,
    include_summary: bool,
    client_summary: dict[str, Any],
    monthly_summary: list[dict[str, Any]] | None,
) -> tuple[str, bytearray]:
    """Generate PDF for a single client."""
    logger.info(f"Generating PDF for client: {client_id}")

    pdf = PDF(
        config=config,
        cover_page=include_summary,
    )
    pdf.set_title(client_id)

    # Add client summary if available
    if include_summary:
        key_figures = [
            (
                "Opening Balance",
                client_summary["opening_balance"],
                f"({'Due' if client_summary['opening_balance'] > 0 else 'Advance'})"
                if client_summary["opening_balance"] != 0
                else "",
            ),
            (
                "Total Billed",
                client_summary["invoice_total"],
                f"({client_summary['invoice_count']} invoices)",
            ),
            (
                "Total Paid",
                client_summary["receipt_total"],
                f"({client_summary['receipt_count']} receipts)",
            ),
            (
                "Closing Balance",
                client_summary["closing_balance"],
                f"({'Due' if client_summary['closing_balance'] > 0 else 'Advance'})"
                if client_summary["closing_balance"] != 0
                else "",
                "#ffcccc" if client_summary["closing_balance"] > 0 else None,
            ),
        ]

        if client_transactions is None or monthly_summary is None:
            raise ValueError(
                f"Transactions or monthly summary data for client {client_id} is missing."
            )

        pdf.add_client_summary(
            client=client_id,
            client_display_name=client_summary["client_display_name"],
            client_address=client_summary["client_address"],
            client_phone=client_summary["client_phone"],
            client_email=client_summary["client_email"],
            generated=f"Generated: {datetime.datetime.now().strftime(config.invoice.date_format)}",
            period=reporting_period_text,
            key_figures=key_figures,
            monthly_summary=monthly_summary,
            transactions=client_transactions,
            outstanding=client_summary["closing_balance"],
            toc_level=1,
        )

        logger.info(f"Client summary for {client_id} added to PDF.")

    for i, invoice_data in enumerate(client_invoices):
        pdf.generate_invoice(
            invoice_data,
            start_section=i == 0,
            create_toc_entry=True,
        )

    logger.info(f"Invoices for client {client_id} generated successfully.")

    for i, receipt_data in enumerate(client_receipts):
        pdf.generate_receipt(
            receipt_data,
            start_section=i == 0,
            create_toc_entry=True,
        )

    logger.info(f"Receipts for client {client_id} generated successfully.")

    return client_id, pdf.output()


def generate_invoice_pdf(
    config: Config, invoice_data: dict[str, Any]
) -> tuple[str, bytearray]:
    """Generate a single invoice PDF."""
    pdf = PDF(config=config)
    pdf.set_title(f"Invoice {invoice_data['number']}")
    pdf.generate_invoice(
        invoice_data,
        start_section=False,
        create_toc_entry=False,
    )
    return invoice_data["number"], pdf.output()


def generate_receipt_pdf(
    config: Config, receipt_data: dict[str, Any]
) -> tuple[str, bytearray]:
    """Generate a single receipt PDF."""
    pdf = PDF(config=config)
    pdf.set_title(f"Receipt {receipt_data['number']}")
    pdf.generate_receipt(
        receipt_data,
        start_section=False,
        create_toc_entry=False,
    )
    return receipt_data["number"], pdf.output()


def write_pdf(path: str, pdfBytes: bytearray):
    """Write PDF bytes to a file."""
    with open(path, "wb") as f:
        f.write(pdfBytes)


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
    config = load_config(config_file)
    logger.info("Configuration loaded successfully.")
    generate(config)
