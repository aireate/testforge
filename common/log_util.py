import logging
import os
from datetime import datetime


if not os.path.exists("logs"):
    os.makedirs("logs")

log_filename = f"logs/test_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_filename, encoding="utf-8")
    ]
)

logger = logging.getLogger(__name__)


def info(msg):
    logger.info(msg)


def error(msg):
    logger.error(msg)
