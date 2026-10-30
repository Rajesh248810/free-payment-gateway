#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example: Webhook Receiver Server.
Receives asynchronous payment.succeeded events when payments are verified.
"""

from fastapi import FastAPI, Request, Header, HTTPException
import uvicorn

app = FastAPI(title="Webhook Receiver Example")

WEBHOOK_SECRET = "my_super_secret_webhook_key"

@app.post("/webhook/payment")
async def handle_payment_webhook(request: Request, x_webhook_secret: str = Header(None)):
    if WEBHOOK_SECRET and x_webhook_secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payload = await request.json()
    event = payload.get("event")
    order_id = payload.get("order_id")
    amount = payload.get("amount")
    utr = payload.get("utr")

    print(f"\n[🔔 Webhook Received] Event: {event}")
    print(f"Order #{order_id} was paid successfully!")
    print(f"Amount: Rs. {amount} | Bank UTR: {utr}")
    print(f"Customer Mobile: {payload.get('customer_phone')}")

    # TODO: Fulfill order, deliver digital goods, or update your database here

    return {"status": "ok", "received": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9000)
