"""Structured logging for agent decisions"""
import logging
import json
import os
from datetime import datetime

logger = logging.getLogger("customer_agent")

# Create logs directory if it doesn't exist
LOGS_DIR = "logs"
os.makedirs(LOGS_DIR, exist_ok=True)


def setup_logger():
    """Configure structured logging with file and console handlers"""
    if logger.handlers:
        return  # Already configured

    # Console handler
    console_handler = logging.StreamHandler()
    console_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_formatter)

    # File handler
    log_file = os.path.join(LOGS_DIR, f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.setLevel(logging.INFO)


def log_agent_decision(request_id: str, action: str, reasoning: str):
    """Log agent decision with structured data"""
    log_data = {
        "request_id": request_id,
        "action": action,
        "reasoning": reasoning,
        "timestamp": datetime.now().isoformat(),
    }

    log_level = logging.WARNING if action == "ESCALATE" else logging.INFO
    logger.log(log_level, json.dumps(log_data))
