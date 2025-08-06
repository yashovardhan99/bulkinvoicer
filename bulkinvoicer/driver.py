"""Driver module for BulkInvoicer."""

import tomllib
import logging
from typing import Any
import polars as pl

# Configure logging
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_config() -> dict[str, Any]:
    """Load configuration from a TOML file."""
    try:
        with open("config.toml", "rb") as f:
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


def generate_invoice(config: dict[str, Any]) -> None:
    """Generate an invoice based on the provided configuration."""
    # Placeholder for invoice generation logic
    logger.info("Generating invoice with the provided configuration.")
    # Here you would implement the logic to create an invoice using the config
    # For now, we just log the action
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"Invoice configuration: {config['invoice']}")

    df_invoice_data = pl.read_excel(
        config["excel"]["filepath"],
        sheet_name="invoices",
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

        generate_invoice(config)
    except Exception as e:
        logger.critical(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    main()
