import logging
from pythonjsonlogger import jsonlogger
import sys

def setup_logger():
    logger = logging.getLogger("qwizable")
    logger.setLevel(logging.INFO)
    
    # Avoid duplicating log handlers
    if not logger.handlers:
        logHandler = logging.StreamHandler(sys.stdout)
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s'
        )
        logHandler.setFormatter(formatter)
        logger.addHandler(logHandler)
    return logger

logger = setup_logger()
