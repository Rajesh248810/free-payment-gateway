#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quickstart entry point for Free UPI Payment Gateway.
Usage:
    python run.py
"""

import sys
import uvicorn
from backend import config

if __name__ == "__main__":
    print("=" * 65)
    print("   ⚡ FREE UPI PAYMENT GATEWAY (0% FEE SELF-HOSTED) ⚡")
    print("=" * 65)
    print(f"[*] Starting server on http://{config.HOST}:{config.PORT}")
    print(f"[*] Interactive Demo UI: http://localhost:{config.PORT}/")
    print(f"[*] Interactive API Docs: http://localhost:{config.PORT}/docs")
    print("=" * 65)

    uvicorn.run(
        "backend.server:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG
    )
