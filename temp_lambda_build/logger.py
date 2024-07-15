import json
import datetime

def log_output(message, level="INFO", **kwargs):
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    print(json.dumps(log_entry))