"""Run the Bulkinvoicer application with command line interface."""

import sys
from bulkinvoicer.driver import main as bulkinvoicer_main
import logging
import pathlib
import logging.config

logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for the Bulkinvoicer application."""
    # Set up logging configuration

    expected_logging_conf_path = pathlib.Path("logging.conf")
    bundled_logging_conf_path = pathlib.Path(__file__).parent.joinpath("logging.conf")
    bundled_debug_conf_path = pathlib.Path(__file__).parent.joinpath(
        "logging-debug.conf"
    )

    debug = "--debug" in sys.argv

    if expected_logging_conf_path.exists():
        logging.config.fileConfig(expected_logging_conf_path)
        logger.info("Logging configuration loaded from logging.conf")
    elif bundled_logging_conf_path.exists() and not debug:
        logging.config.fileConfig(bundled_logging_conf_path)
        logger.info("Logging configuration loaded from bundled logging.conf")
    elif bundled_debug_conf_path.exists() and debug:
        logging.config.fileConfig(bundled_debug_conf_path)
        logger.info("Logging configuration loaded from bundled logging-debug.conf")
    elif debug:
        logging.basicConfig(level=logging.DEBUG)
        logger.info(
            "No logging configuration found, using basicConfig with DEBUG level"
        )
    else:
        logging.basicConfig(level=logging.WARNING)
        logger.info(
            "No logging configuration found, using basicConfig with WARNING level"
        )

    # Get the config file path from command line arguments if provided
    config_file = "config.toml"
    for arg in sys.argv:
        if arg.endswith(".toml"):
            config_file = arg
            logger.info(f"Overriding config file path: {config_file}")
            break
    logger.info(f"Using config file: {config_file}")

    logger.info("Starting Bulkinvoicer...")
    try:
        bulkinvoicer_main(config_file)
    except Exception as e:
        if debug:
            logger.critical(e, exc_info=True)
        else:
            logger.critical("Bulkinvoicer encountered an error.")
            logger.critical("Run with --debug for more details.")
        sys.exit(1)

    logger.info("Bulkinvoicer finished successfully.")
    sys.exit(0)
