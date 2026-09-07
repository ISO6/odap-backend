import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.log_filter import (
    RequestIdFilter,
)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


request_id_filter = RequestIdFilter()

# ==========================================
# 通用格式
# ==========================================
formatter = logging.Formatter(
    "%(asctime)s | "
    "%(levelname)s | "
    "[%(request_id)s] | "
    "%(filename)s:%(lineno)d | "
    "%(message)s"
)
# ==========================================
# Error Logger
# ==========================================

error_logger = logging.getLogger("odap.error")
error_logger.setLevel(logging.ERROR)
error_logger.addFilter(
request_id_filter
)
error_handler = RotatingFileHandler(
    filename=LOG_DIR / "error.log",
    maxBytes=20 * 1024 * 1024,
    backupCount=30,
    encoding="utf-8",
)

error_handler.setFormatter(formatter)

if not error_logger.handlers:
    error_logger.addHandler(error_handler)

# ==========================================
# Access Logger
# ==========================================

access_logger = logging.getLogger("odap.access")
access_logger.setLevel(logging.INFO)
access_logger.addFilter(
request_id_filter
)
access_handler = RotatingFileHandler(
    filename=LOG_DIR / "access.log",
    maxBytes=20 * 1024 * 1024,
    backupCount=30,
    encoding="utf-8",
)

access_handler.setFormatter(formatter)

if not access_logger.handlers:
    access_logger.addHandler(access_handler)
