# -*- coding: utf-8 -*-
"""
Configuration settings for Free UPI Payment Gateway.
Loads settings from environment variables or .env file.
"""

import os
from pathlib import Path

# Load .env file if available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

# Base Directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# BharatPe Merchant Credentials (Default placeholders - override via .env)
BHARATPE_MERCHANT_ID = os.getenv("BHARATPE_MERCHANT_ID", "your_merchant_id_here")
BHARATPE_TOKEN = os.getenv("BHARATPE_TOKEN", "your_token_here")
BHARATPE_UPI_VPA = os.getenv("BHARATPE_UPI_VPA", "your_vpa@unitype")
MERCHANT_DISPLAY_NAME = os.getenv("MERCHANT_DISPLAY_NAME", "FreeUPI Gateway")

# Gateway Behavioral Settings
ENABLE_DECIMAL_MATCH = os.getenv("ENABLE_DECIMAL_MATCH", "true").lower() in ("true", "1", "yes")
INTENT_EXPIRY_SECONDS = int(os.getenv("INTENT_EXPIRY_SECONDS", "600"))  # 10 minutes
CACHE_TTL_SECONDS = float(os.getenv("CACHE_TTL_SECONDS", "2.5"))
RECONCILER_INTERVAL_SECONDS = int(os.getenv("RECONCILER_INTERVAL_SECONDS", "5"))

# Optional Webhook for payment events
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Server Settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# Persistence File Paths
INTENTS_FILE = DATA_DIR / "payment_intents.json"
USED_UTRS_FILE = DATA_DIR / "used_utrs.json"
ORDERS_FILE = DATA_DIR / "orders.json"
