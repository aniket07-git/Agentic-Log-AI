import logging
import json
from pythonjsonlogger import jsonlogger
from logging_loki import LokiHandler
import os
from datetime import datetime

def setup_logging(service_name):
    """
    Set up logging configuration with Loki integration
    """
    # Create logger
    logger = logging.getLogger(service_name)
    logger.setLevel(logging.INFO)

    # Create formatters
    json_formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )

    # Create handlers
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)

    # Configure Loki handler
    loki_url = os.getenv('LOKI_URL', 'http://localhost:3100')
    loki_handler = LokiHandler(
        url=f"{loki_url}/loki/api/v1/push",
        tags={"application": service_name},
        version="1"
    )
    loki_handler.setFormatter(json_formatter)

    # Add handlers to logger
    logger.addHandler(console_handler)
    logger.addHandler(loki_handler)

    return logger

def log_request(logger, request_id, method, path, status_code, duration_ms):
    """
    Log HTTP request details
    """
    logger.info(
        "HTTP Request",
        extra={
            "request_id": request_id,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat()
        }
    )

def log_error(logger, request_id, error, context=None):
    """
    Log error details
    """
    logger.error(
        "Error occurred",
        extra={
            "request_id": request_id,
            "error": str(error),
            "context": context,
            "timestamp": datetime.utcnow().isoformat()
        }
    ) 