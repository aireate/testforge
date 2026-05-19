import logging
import os
from datetime import datetime

_logger = None
_initialized = False


def _get_log_dir():
    log_dir = os.path.join(os.getcwd(), "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    return log_dir


def _init_logger():
    global _logger, _initialized
    
    if _initialized:
        return _logger
    
    log_dir = _get_log_dir()
    log_filename = os.path.join(
        log_dir,
        f"test_{datetime.now().strftime('%Y%m%d')}.log"
    )
    
    _logger = logging.getLogger("TestForge")
    _logger.setLevel(logging.INFO)
    
    if not _logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s"
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        _logger.addHandler(console_handler)
        
        file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        file_handler.setFormatter(formatter)
        _logger.addHandler(file_handler)
    
    _initialized = True
    return _logger


def info(msg):
    logger = _init_logger()
    logger.info(msg)


def error(msg):
    logger = _init_logger()
    logger.error(msg)


def get_logger():
    return _init_logger()
