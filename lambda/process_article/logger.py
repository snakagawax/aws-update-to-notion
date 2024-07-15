import json
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def log_debug(message, **kwargs):
    _log("DEBUG", message, **kwargs)

def log_info(message, **kwargs):
    _log("INFO", message, **kwargs)

def log_error(message, **kwargs):
    _log("ERROR", message, **kwargs)

def _log(level, message, **kwargs):
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": level,
        "message": message
    }
    for key, value in kwargs.items():
        if isinstance(value, bytes):
            log_entry[key] = value.decode('utf-8', errors='replace')
        elif isinstance(value, (int, float, str, bool, type(None))):
            log_entry[key] = value
        else:
            log_entry[key] = str(value)
    
    log_message = json.dumps(log_entry, ensure_ascii=False)
    
    if level == "ERROR":
        logger.error(log_message)
    elif level == "INFO":
        logger.info(log_message)
    else:
        logger.debug(log_message)