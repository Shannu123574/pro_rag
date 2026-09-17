import logging
import json
import uuid
import time
from contextvars import ContextVar
from datetime import datetime, timezone

# Context variables for traceability
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
endpoint_var: ContextVar[str] = ContextVar("endpoint", default="")

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
            "endpoint": endpoint_var.get(),
        }
        
        # Include extra fields passed in the log record
        if hasattr(record, "extra_fields"):
            log_record.update(record.extra_fields)
            
        return json.dumps(log_record)

def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Avoid duplicate handlers if setup_logger is called multiple times
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
    return logger

# Convenience function to generate a trace ID
def generate_request_id() -> str:
    return str(uuid.uuid4())
