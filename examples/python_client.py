#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Example: Creating a UPI payment intent & polling for status in Python.
"""

import time
import requests

GATEWAY_URL = "http://localhost:8000"

def create_and_wait_for_payment(amount: float, order_id: str):
    print(f"[*] Creating payment intent for Rs. {amount} (Order #{order_id})...")
    
    # 1. Create Payment Intent
    res = requests.post(f"{GATEWAY_URL}/api/checkout/create-intent", json={
        "amount": amount,
        "order_id": order_id,
        "customer_phone": "9876543210",
        "metadata": {"plan": "Pro Annual"}
    })
    
    data = res.json()["data"]
    intent_id = data["intent_id"]
    exact_amount = data["exact_amount"]
    qr_url = data["qr_code_url"]
    upi_uri = data["upi_uri"]
    
    print(f"[+] Intent Created: {intent_id}")
    print(f"[+] EXACT Amount to Pay: Rs. {exact_amount:.2f}")
    print(f"[+] UPI Deep Link: {upi_uri}")
    print(f"[+] QR Code URL: {qr_url}")
    print("\n[*] Waiting for customer to scan and pay via GPay/PhonePe/Paytm...")
    
    # 2. Poll for payment status
    while True:
        time.sleep(3)
        poll_res = requests.get(f"{GATEWAY_URL}/api/checkout/poll-status?intent_id={intent_id}").json()
        status = poll_res.get("status")
        
        if status == "PAID":
            print("\n🎉 PAYMENT VERIFIED!")
            print(f"Order ID: {poll_res.get('order_id')}")
            print(f"Bank UTR: {poll_res.get('utr')}")
            print(f"Amount: Rs. {poll_res.get('amount')}")
            break
        elif status == "EXPIRED":
            print("\n❌ Payment session expired.")
            break
        else:
            print(f"[*] Status: PENDING (Time remaining: {poll_res.get('time_remaining')}s)")

if __name__ == "__main__":
    create_and_wait_for_payment(amount=199.0, order_id="TEST_ORD_101")
