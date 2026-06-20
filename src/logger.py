"""Structured logging for agent decisions"""
import logging
import json
from datetime import datetime

logger = logging.getLogger("customer_agent")


def setup_logger():
    """Configure structured logging"""
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
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
