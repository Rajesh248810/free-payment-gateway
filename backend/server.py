# -*- coding: utf-8 -*-
"""
FastAPI REST API Server for Free Payment Gateway.
Provides clean, developer-friendly endpoints for creating intents, polling status,
manual UTR verification, and downloading FamPay-style comic posters.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

import requests
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config
from . import gateway
from . import poster
from . import reconciler

app = FastAPI(
    title="Free UPI Payment Gateway",
    description="0% Fee, Self-Hosted BharatPe & UPI Dynamic QR Payment Gateway with Auto-Verification",
    version="1.0.0"
)

# Enable CORS for cross-origin integrations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- PYDANTIC REQUEST MODELS -----------------

class CreateIntentRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Base payment amount in INR")
    order_id: Optional[str] = Field(None, description="Your unique order/invoice ID")
    customer_phone: Optional[str] = Field("", description="Customer 10-digit mobile number")
    customer_name: Optional[str] = Field("Customer", description="Customer full name")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Arbitrary custom metadata")


class VerifyUtrRequest(BaseModel):
    intent_id: str = Field(..., description="Payment session Intent ID")
    utr: str = Field(..., description="12-digit Bank Reference / UTR Number")


# ----------------- LIFECYCLE HOOKS -----------------

@app.on_event("startup")
def on_startup():
    # Start 5-second background auto-reconciler
    reconciler.start_background_payment_reconciler(interval=config.RECONCILER_INTERVAL_SECONDS)
    print(f"🚀 Free UPI Payment Gateway started on http://{config.HOST}:{config.PORT}")
    print(f"💳 Merchant VPA: {config.BHARATPE_UPI_VPA} ({config.MERCHANT_DISPLAY_NAME})")


# ----------------- API ENDPOINTS -----------------

@app.post("/api/checkout/create-intent", summary="Create UPI Payment Intent")
def api_create_intent(req: CreateIntentRequest):
    """
    Creates a dynamic UPI payment session.
    Assigns unique decimal paise (e.g. ₹100 becomes ₹100.14) so payments
    auto-verify in real time with zero merchant fees.
    """
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    intent = gateway.create_payment_intent(
        base_amount=req.amount,
        order_id=req.order_id,
        customer_phone=req.customer_phone or "",
        customer_name=req.customer_name or "Customer",
        metadata=req.metadata or {}
    )

    return {
        "success": True,
        "data": {
            "intent_id": intent["intent_id"],
            "order_id": intent["order_id"],
            "base_amount": intent["base_amount"],
            "exact_amount": intent["exact_amount"],
            "expires_at": intent["expires_at"],
            "upi_vpa": intent["upi_vpa"],
            "upi_uri": intent["upi_uri"],
            "phonepe_uri": intent["phonepe_uri"],
            "gpay_uri": intent["gpay_uri"],
            "paytm_uri": intent["paytm_uri"],
            "bhim_uri": intent["bhim_uri"],
            "qr_code_url": intent["qr_code_url"]
        }
    }


@app.get("/api/checkout/poll-status", summary="Poll Payment Status")
def api_poll_status(intent_id: str = Query(..., description="Payment Intent ID")):
    """
    Polls the payment status. If PENDING, checks BharatPe transactions in real-time.
    Returns status: 'PENDING', 'PAID', or 'EXPIRED'.
    """
    res = gateway.check_intent_status(intent_id)
    if not res.get("success"):
        raise HTTPException(status_code=404, detail=res.get("error", "Intent not found"))
    return res


@app.post("/api/checkout/verify-utr", summary="Verify Manual 12-Digit UTR")
def api_verify_utr(req: VerifyUtrRequest):
    """
    Fallback: customer submits 12-digit UTR from their banking app.
    Strictly verifies against BharatPe transactions and prevents duplicate reuse.
    """
    ok, res = gateway.verify_by_manual_utr(req.intent_id, req.utr)
    if not ok:
        raise HTTPException(status_code=400, detail=str(res))
    return {"success": True, "data": res}


@app.get("/api/checkout/download-qr", summary="Download FamPay-Style Comic Poster")
def api_download_qr(intent_id: str = Query(..., description="Payment Intent ID")):
    """
    Generates and downloads a branded FamPay-style 800x1060 Comic Poster PNG
    with amount highlight, corner brackets, and UPI badges.
    """
    with gateway._lock:
        intents = gateway.load_intents()
        intent = intents.get(intent_id)

    if not intent:
        raise HTTPException(status_code=404, detail="Payment session not found")

    qr_url = intent.get("qr_code_url")
    amt = float(intent.get("exact_amount", 0))

    try:
        r = requests.get(qr_url, timeout=10)
        final_img = poster.render_comic_qr_poster(
            raw_qr_bytes=r.content,
            amount=amt,
            merchant_name=config.MERCHANT_DISPLAY_NAME,
            upi_vpa=config.BHARATPE_UPI_VPA
        )
        return Response(
            content=final_img,
            media_type="image/png",
            headers={
                "Content-Disposition": f'attachment; filename="{config.MERCHANT_DISPLAY_NAME}_Comic_Pay_Rs{amt:.2f}.png"',
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate QR poster: {e}")


@app.get("/api/gateway/health", summary="Gateway Health & Info")
def api_health():
    """Returns gateway configuration status and active session stats."""
    intents = gateway.load_intents()
    used_utrs = gateway.load_used_utrs()
    return {
        "status": "ONLINE",
        "merchant_name": config.MERCHANT_DISPLAY_NAME,
        "upi_vpa": config.BHARATPE_UPI_VPA,
        "decimal_match_enabled": config.ENABLE_DECIMAL_MATCH,
        "total_intents": len(intents),
        "total_claimed_utrs": len(used_utrs)
    }


# ----------------- SERVE FRONTEND STATIC FILES -----------------

frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
