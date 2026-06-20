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

# Langfuse Configuration
LANGFUSE_PUBLIC_KEY = ""  # Set via environment variable
LANGFUSE_SECRET_KEY = ""  # Set via environment variable
LANGFUSE_HOST = "https://cloud.langfuse.com"  # Can be self-hosted

# Database
DATA_DIR = "data"
