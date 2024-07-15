import json
import logging
from datetime import datetime
import boto3
from botocore.exceptions import ClientError

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

def get_parameter(name):
    """
    AWS Systems Manager Parameter Storeからパラメータを取得する関数

    Args:
        name (str): パラメータ名

    Returns:
        str: パラメータの値

    Raises:
        ClientError: Parameter Storeへのアクセス中にエラーが発生した場合
    """
    ssm = boto3.client('ssm')
    try:
        response = ssm.get_parameter(Name=name, WithDecryption=True)
        return response['Parameter']['Value']
    except ClientError as e:
        log_error(f"Error retrieving parameter {name}", error=str(e))
        raise
