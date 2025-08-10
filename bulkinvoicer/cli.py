"""Run the Bulkinvoicer application with command line interface."""

import sys
from bulkinvoicer.driver import main as bulkinvoicer_main
import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for the Bulkinvoicer application."""
    # Set up logging configuration
    debug = "--debug" in sys.argv
    
    if debug:
        logging.basicConfig(level=logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug mode is enabled.")
    else:
        logging.basicConfig(level=logging.WARNING)

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
            logger.exception(e)
        else:
            logger.error("An error occurred while running Bulkinvoicer: %s", e)
            logger.info("Run with --debug for more details.")
        sys.exit(1)

    logger.info("Bulkinvoicer finished successfully.")
    sys.exit(0)
