"""Config loader for bulkinvoicer."""

from .model import Config


from pydantic import ValidationError


import logging
import sys

logger = logging.getLogger(__name__)


def load_config(config_file: str) -> Config:
    """Load configuration from a TOML file."""
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib
    try:
        with open(config_file, "rb") as f:
            config = tomllib.load(f)
            logger.debug("Configuration loaded successfully.")
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
