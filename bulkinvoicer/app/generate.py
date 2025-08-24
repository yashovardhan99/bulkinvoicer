"""Driver module for BulkInvoicer."""

from pathlib import Path
import logging
import polars as pl
from ..config.loader import load_config
from ..config.model import Config
from ..io.files import write_pdf
from ..domain.prepare import prepare_invoices, prepare_receipts
from ..io.excel import read_excel
from ..pdf.renderer import PDF
from ..domain.matching import match_payments_by_client
from ..domain.periods import slice_period_frames, get_reporting_period_text
from ..domain.transactions import build_client_transactions_df
from ..domain.summaries import (
    build_client_summaries,
    build_status_breakdown,
)
from ..domain.balances import (
    normalize_date_period,
    compute_monthly_client_balances,
    summarize_balance_data,
)
from ..domain.summaries import build_summary_report
from ..services.workers import (
    generate_client_summary_pdf,
    generate_client_pdf,
    generate_invoice_pdf,
    generate_receipt_pdf,
)
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm
from concurrent.futures import (
    ProcessPoolExecutor,
    ThreadPoolExecutor,
    as_completed,
)

# Configure logging
logger = logging.getLogger(__name__)


def generate(config: Config) -> None:
    """Generate invoices and receipts based on provided configuration."""
    logger.info("Starting the generation process.")
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("Configuration: %s", config)

    date_format_invoice = config.invoice.date_format

    # Read input data
    df_invoice_data, df_receipt_data, df_clients = read_excel(config)

    # Prepare frames
    df_invoices = prepare_invoices(config, df_invoice_data, df_clients)
    df_receipts = prepare_receipts(config, df_receipt_data, df_clients)

    # Match payments per client
    df_invoices, df_receipts = match_payments_by_client(df_invoices, df_receipts)

    logger.info("Starting PDF generation.")

    with tqdm(
        config.output.items(),
        desc="Generating Outputs",
        leave=False,
    ) as output_format_pbar:
        with logging_redirect_tqdm():
            for key, output_config in output_format_pbar:
                logger.debug(f"Starting with output format: {key}")
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

                frames = slice_period_frames(
                    df_invoices, df_receipts, start_date, end_date
                )
                df_invoices_report = frames["invoices_report"]
                df_receipts_report = frames["receipts_report"]
                df_invoices_open = frames["invoices_open"]
                df_receipts_open = frames["receipts_open"]
                df_invoices_close = frames["invoices_close"]
                df_receipts_close = frames["receipts_close"]

                reporting_period_text = get_reporting_period_text(
                    date_format_invoice, start_date, end_date
                )

                # Consolidate clients from both invoices and receipts
                df_clients_close = (
                    pl.concat(
                        [
                            df_invoices_close.select("client"),
                            df_receipts_close.select("client"),
                        ]
                    )
                    .unique()
                    .join(df_clients, left_on="client", right_on="name", how="left")
                    .select("client", "display name", "address", "phone", "email")
                )

                include_summary = output_config.include_summary

                if include_summary:
                    df_client_summaries = build_client_summaries(
                        df_clients_close,
                        df_invoices_open,
                        df_invoices_close,
                        df_receipts_open,
                        df_receipts_close,
                    )

                    df_status_breakdown = build_status_breakdown(df_client_summaries)

                    # Default start and end dates to last 12 months if not provided
                    start_date, end_date = normalize_date_period(start_date, end_date)

                    df_balance = compute_monthly_client_balances(
                        start_date,
                        end_date,
                        df_invoices_close,
                        df_receipts_close,
                        df_clients_close,
                    )

                    df_balance_aggregated = summarize_balance_data(df_balance)

                    summary_details = build_summary_report(
                        date_format_invoice,
                        reporting_period_text,
                        df_client_summaries,
                        df_status_breakdown,
                        df_balance_aggregated,
                    )
                else:
                    df_client_summaries = None
                    df_balance = None
                    df_balance_aggregated = None
                    df_status_breakdown = None
                    summary_details = {}

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
                        logger.debug("Including summary in the combined PDF.")
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
                        logger.debug("Generating summary PDF")

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
                    with ProcessPoolExecutor() as executor:
                        futures = (
                            [
                                executor.submit(
                                    generate_client_summary_pdf, config, summary_details
                                )
                            ]
                            if include_summary
                            else []
                        )
                        df_transactions = (
                            build_client_transactions_df(
                                start_date,
                                end_date,
                                df_invoices_close,
                                df_receipts_close,
                            )
                            if include_summary
                            else None
                        )

                        logger.info("Generating PDFs for each client.")

                        futures.extend(
                            [
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
                                    df_transactions.filter(
                                        pl.col("client") == client_id
                                    )
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
                                for client_id in df_clients_close.select(
                                    "client"
                                ).to_series()
                            ]
                        )

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


def main(config_file="config.toml") -> None:
    """Main function to run the BulkInvoicer."""
    config = load_config(config_file)
    logger.info("Configuration loaded successfully.")
    generate(config)
