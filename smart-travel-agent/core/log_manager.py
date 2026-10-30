import logging
import os

from dotenv import load_dotenv

load_dotenv()

_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DEFAULT_LOG_LEVEL = "WARNING"


def get_logger(name: str) -> logging.Logger:
    """Return a named application logger using the centralized log settings."""
    configured_level = os.getenv("LOG_LEVEL", _DEFAULT_LOG_LEVEL).upper()
    level = getattr(logging, configured_level, None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid LOG_LEVEL {configured_level!r}")

    logging.basicConfig(level=level, format=_LOG_FORMAT)
    logging.getLogger().setLevel(level)
    return logging.getLogger(name)
