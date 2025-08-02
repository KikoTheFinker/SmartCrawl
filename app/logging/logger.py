import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s")
        handler.setFormatter(formatter)

        logger.addHandler(handler)
        logger.propagate = False

    return logger
