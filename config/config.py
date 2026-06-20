"""Configuration file for Customer Request Agent"""
from datetime import datetime

# Evaluation date - change this to datetime.now() for production
EVALUATION_DATE = datetime(2026, 6, 16)

# Customer lookup strategy - order matters (tries first parameter first)
# Options: "customer_id", "email"
CUSTOMER_LOOKUP_ORDER = ["customer_id", "email"]

# LLM Configuration
OPENAI_MODEL = "gpt-4o-mini"
LLM_TEMPERATURE = 0.0  # Deterministic extraction

# Safety limits
MAX_TOKEN_COUNT = 75

# Refund decision thresholds - change these to adjust auto-approval rules
APPROVE_MAX_AMOUNT = 50       # refund under $50 can auto-approve
ESCALATE_MIN_AMOUNT = 500     # refund at or over $500 escalates
APPROVE_MAX_AGE_DAYS = 30     # order 30 days old or newer can approve
ESCALATE_MIN_AGE_DAYS = 90    # order older than this escalates

# Langfuse Configuration
LANGFUSE_PUBLIC_KEY = ""  # Set via environment variable
LANGFUSE_SECRET_KEY = ""  # Set via environment variable
LANGFUSE_HOST = "https://cloud.langfuse.com"  # Can be self-hosted

# Database
DATA_DIR = "data"
