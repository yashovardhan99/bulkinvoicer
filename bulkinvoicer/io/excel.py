"""I/O handling for BulkInvoicer."""

import logging
from ..config.model import Config

import polars as pl


import sys
from concurrent.futures import Future, ThreadPoolExecutor

logger = logging.getLogger(__name__)


def read_excel(config: Config) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Read Excel file and return dataframes for invoices, receipts, and clients."""
    logger.info("Reading data from Excel files.")

    with ThreadPoolExecutor(max_workers=3) as executor:
        future_invoice_data = executor.submit(
            pl.read_excel,
            config.excel.filepath,
            sheet_name="invoices",
        )
        future_receipt_data = executor.submit(
            pl.read_excel,
            config.excel.filepath,
            sheet_name="receipts",
        )
        future_clients = executor.submit(
            pl.read_excel,
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

        exceptions: list[Exception] = []

        def get_results(future: Future[pl.DataFrame]) -> pl.DataFrame:
            try:
                return future.result()
            except TimeoutError as e:
                logger.critical("Reading Excel file timed out.")
                exceptions.append(e)
            except (FileNotFoundError, ValueError) as e:
                logger.critical(f"Error reading Excel file: {e}")
                exceptions.append(e)
            except pl.exceptions.PolarsError as e:
                logger.critical(f"Polars error reading Excel file: {e}")
                exceptions.append(e)
            except Exception as e:
                logger.critical(f"Unexpected error reading Excel file: {e}")
                exceptions.append(e)

            return pl.DataFrame()

        df_invoice_data = get_results(future_invoice_data)
        df_receipt_data = get_results(future_receipt_data)
        df_clients = get_results(future_clients)

        if exceptions:
            if sys.version_info < (3, 11):
                raise ValueError(
                    f"Errors occurred while reading Excel files: {exceptions}"
                )
            else:
                from builtins import ExceptionGroup

                raise ExceptionGroup(
                    "Errors occurred while reading Excel files.",
                    exceptions,
                )
    logger.info("Data loaded from Excel files.")
    return (df_invoice_data, df_receipt_data, df_clients)
