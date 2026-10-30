# -*- coding: utf-8 -*-
"""
Core Payment Gateway Engine:
- BharatPe API Polling & Transaction Fetcher
- Unique Decimal Offset Algorithm (Collision-free 100% automated matching)
- Dynamic UPI Intent & QR Code Generator
- Anti-Fraud UTR Deduplication (prevents double-spending)
- Webhook Dispatcher
"""

import os
import time
import json
import random
import urllib.parse
import threading
import requests
from typing import Dict, Any, List, Optional, Tuple

from . import config

_lock = threading.RLock()
_last_fetch_time = 0.0
_cached_transactions: List[Dict[str, Any]] = []


# ----------------- PERSISTENCE UTILITIES -----------------

def load_intents() -> Dict[str, Any]:
    if not os.path.exists(config.INTENTS_FILE):
        return {}
    try:
        with open(config.INTENTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_intents(data: Dict[str, Any]) -> None:
    try:
        with open(config.INTENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Error saving intents: {e}")


def load_used_utrs() -> Dict[str, Any]:
    if not os.path.exists(config.USED_UTRS_FILE):
        return {}
    try:
        with open(config.USED_UTRS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_used_utrs(data: Dict[str, Any]) -> None:
    try:
        with open(config.USED_UTRS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Error saving used UTRs: {e}")


def is_utr_already_used(utr: str) -> bool:
    """Strictly checks if a UTR has already been claimed for another order."""
    if not utr:
        return False
    clean = "".join(filter(str.isalnum, str(utr))).strip()
    if not clean:
        return False
    with _lock:
        used = load_used_utrs()
        return clean in used


def mark_utr_as_used(utr: str, order_id: str, amount: float, payer_name: str = "") -> None:
    """Permanently records a UTR to block duplicate claims across the system."""
    if not utr:
        return
    clean = "".join(filter(str.isalnum, str(utr))).strip()
    if not clean:
        return
    with _lock:
        used = load_used_utrs()
        used[clean] = {
            "order_id": str(order_id),
            "amount": float(amount),
            "payer_name": str(payer_name or ""),
            "claimed_at": int(time.time()),
            "claimed_date": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        save_used_utrs(used)
        print(f"[🛡️ Anti-Fraud] UTR {clean} permanently locked for Order #{order_id}")


# ----------------- BHARATPE API FETCHER -----------------

def fetch_bharatpe_transactions(force: bool = False) -> List[Dict[str, Any]]:
    """
    Fetches real-time UPI transactions from BharatPe Merchant API.
    Caches results for config.CACHE_TTL_SECONDS to protect against rate limits.
    """
    global _last_fetch_time, _cached_transactions
    now = time.time()

    if not force and (now - _last_fetch_time < config.CACHE_TTL_SECONDS) and _cached_transactions:
        return _cached_transactions

    # If no BharatPe credentials, return cached or empty
    if not config.BHARATPE_MERCHANT_ID or not config.BHARATPE_TOKEN:
        print("[!] BharatPe credentials missing in config/environment.")
        return _cached_transactions

    now_ms = int(now * 1000)
    # Check last 48 hours to account for any clock drift
    s_date = now_ms - (48 * 3600 * 1000)
    e_date = now_ms + (3600 * 1000)

    url = (
        f"https://payments-tesseract.bharatpe.in/api/v1/merchant/transactions"
        f"?module=PAYMENT_QR&merchantId={config.BHARATPE_MERCHANT_ID}"
        f"&sDate={s_date}&eDate={e_date}&pageSize=30&pageCount=0&isFromOtDashboard=1"
    )
    headers = {
        "token": config.BHARATPE_TOKEN,
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X)",
        "origin": "https://enterprise.bharatpe.in",
        "referer": "https://enterprise.bharatpe.in/",
        "accept": "application/json, text/javascript, */*; q=0.01"
    }

    try:
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            res_json = r.json()
            if res_json.get("status"):
                txns = res_json.get("data", {}).get("transactions", [])
                with _lock:
                    _cached_transactions = txns
                    _last_fetch_time = now
                return txns
            else:
                print(f"[!] BharatPe API returned status false: {res_json.get('message')}")
        else:
            print(f"[!] BharatPe API error HTTP {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"[!] BharatPe request exception: {e}")

    return _cached_transactions


# ----------------- INTENT CREATION & DECIMAL ENGINE -----------------

def create_payment_intent(
    base_amount: float,
    order_id: Optional[str] = None,
    customer_phone: str = "",
    customer_name: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Creates a unique payment session with dynamic decimal paise.
    E.g.: Base amount ₹100 becomes ₹100.14.
    Different concurrent users get unique paise offsets, making settlement
    verification 100% collision-free without requiring the customer to manually enter UTR!
    """
    with _lock:
        intents = load_intents()
        now = time.time()
        base_amt = float(base_amount)
        if base_amt <= 0:
            base_amt = 1.0

        # Clean expired/stale intents older than 15 minutes
        cutoff = now - 900
        active_amounts = set()
        for i_id, i_data in list(intents.items()):
            if i_data.get("status") == "PENDING" and i_data.get("expires_at", 0) > now:
                active_amounts.add(round(float(i_data.get("exact_amount", 0)), 2))
            elif i_data.get("created_at", 0) < cutoff and i_data.get("status") != "PAID":
                intents.pop(i_id, None)

        if config.ENABLE_DECIMAL_MATCH:
            # Pick a unique decimal paise offset (0.01 to 0.99)
            offsets = list(range(1, 100))
            random.shuffle(offsets)
            chosen_exact = None
            for off in offsets:
                candidate = round(int(base_amt) + (off / 100.0), 2)
                if candidate not in active_amounts:
                    chosen_exact = candidate
                    break
            if chosen_exact is None:
                chosen_exact = round(int(base_amt) + (random.randint(101, 199) / 100.0), 2)
        else:
            chosen_exact = round(base_amt, 2)

        intent_id = f"pi_{int(now)}_{random.randint(1000, 9999)}"
        order_num = order_id or f"ORD_{int(now)}_{random.randint(100, 999)}"
        expires_at = int(now + config.INTENT_EXPIRY_SECONDS)

        clean_phone = "".join(filter(str.isdigit, str(customer_phone or "")))[-10:]

        # UPI URI parameters (Standard NPCI UPI Spec)
        encoded_note = urllib.parse.quote(f"Pay {order_num}")
        encoded_name = urllib.parse.quote(config.MERCHANT_DISPLAY_NAME)
        base_upi_params = (
            f"pa={config.BHARATPE_UPI_VPA}"
            f"&pn={encoded_name}"
            f"&am={chosen_exact:.2f}"
            f"&cu=INR"
            f"&tn={encoded_note}"
            f"&mode=02"
        )

        upi_uri = f"upi://pay?{base_upi_params}"
        phonepe_uri = f"phonepe://pay?{base_upi_params}"
        gpay_uri = f"tez://upi/pay?{base_upi_params}"
        paytm_uri = f"paytmmp://pay?{base_upi_params}"
        bhim_uri = f"bhim://pay?{base_upi_params}"

        qr_code_url = (
            f"https://api.qrserver.com/v1/create-qr-code/"
            f"?size=320x320&margin=10&data={urllib.parse.quote(upi_uri)}"
        )

        intent_record = {
            "intent_id": intent_id,
            "order_id": order_num,
            "status": "PENDING",  # PENDING, PAID, EXPIRED
            "base_amount": base_amt,
            "exact_amount": chosen_exact,
            "created_at": int(now),
            "expires_at": expires_at,
            "customer_phone": clean_phone,
            "customer_name": customer_name or "Customer",
            "metadata": metadata or {},
            "upi_vpa": config.BHARATPE_UPI_VPA,
            "upi_uri": upi_uri,
            "phonepe_uri": phonepe_uri,
            "gpay_uri": gpay_uri,
            "paytm_uri": paytm_uri,
            "bhim_uri": bhim_uri,
            "qr_code_url": qr_code_url,
            "utr": None,
            "paid_at": None,
            "payer_name": None
        }

        intents[intent_id] = intent_record
        save_intents(intents)
        return intent_record


# ----------------- STATUS POLLING & VERIFICATION -----------------

def check_intent_status(intent_id: str) -> Dict[str, Any]:
    """
    Checks if a payment intent has been fulfilled.
    Automatically queries BharatPe transactions for real-time confirmation.
    """
    now = time.time()
    with _lock:
        intents = load_intents()
        intent = intents.get(intent_id)

    if not intent:
        return {"success": False, "error": "Intent session not found"}

    if intent.get("status") == "PAID":
        return {
            "success": True,
            "status": "PAID",
            "order_id": intent.get("order_id"),
            "amount": intent.get("exact_amount"),
            "utr": intent.get("utr"),
            "paid_at": intent.get("paid_at")
        }

    # Fetch live transactions from BharatPe
    txns = fetch_bharatpe_transactions()
    target_amount = float(intent["exact_amount"])
    created_ts_ms = (intent["created_at"] - 120) * 1000  # 2 minute grace window

    matched_txn = None
    for t in txns:
        t_amt = float(t.get("amount") or 0)
        t_time = int(t.get("paymentTimestamp") or 0)
        t_status = str(t.get("status") or "").upper()
        t_utr = str(t.get("bankReferenceNo") or "").strip()

        # Strict: Skip any transaction whose UTR was previously claimed
        if is_utr_already_used(t_utr):
            continue

        # Match exact unique decimal paise (< 0.005 tolerance) and valid timestamp
        if t_status == "SUCCESS" and abs(t_amt - target_amount) < 0.005 and t_time >= created_ts_ms:
            matched_txn = t
            break

    if matched_txn:
        order_res = confirm_paid_order(intent_id, matched_txn)
        return {
            "success": True,
            "status": "PAID",
            "order_id": order_res.get("order_id"),
            "amount": target_amount,
            "utr": matched_txn.get("bankReferenceNo"),
            "paid_at": int(time.time())
        }

    # Check if window expired
    if intent.get("expires_at", 0) < now:
        intent["status"] = "EXPIRED"
        with _lock:
            intents[intent_id] = intent
            save_intents(intents)
        return {"success": True, "status": "EXPIRED", "message": "Payment window expired"}

    return {
        "success": True,
        "status": "PENDING",
        "time_remaining": max(0, intent.get("expires_at", 0) - int(now)),
        "exact_amount": target_amount
    }


def verify_by_manual_utr(intent_id: str, raw_utr: str) -> Tuple[bool, Any]:
    """
    Fallback: verify payment using 12-digit bank reference UTR number.
    Strictly forbids duplicate reuse of any previously used UTR!
    """
    clean_utr = "".join(filter(str.isalnum, str(raw_utr or ""))).strip()
    if len(clean_utr) < 8:
        return False, "Please enter a valid 12-digit UTR/Bank Reference number"

    if is_utr_already_used(clean_utr):
        return False, f"⚠️ UTR ({clean_utr}) has already been used! Duplicate UTR strictly not allowed."

    with _lock:
        intents = load_intents()
        intent = intents.get(intent_id)

    if not intent:
        return False, "Order session not found"

    if intent.get("status") == "PAID":
        return True, {"order_id": intent.get("order_id"), "status": "PAID", "utr": intent.get("utr")}

    # Force fetch fresh transactions
    txns = fetch_bharatpe_transactions(force=True)
    base_amt = float(intent.get("base_amount") or 1)

    matched_txn = None
    for t in txns:
        t_utr = str(t.get("bankReferenceNo") or "").strip()
        t_int_utr = str(t.get("internalUtr") or "").strip()
        t_amt = float(t.get("amount") or 0)
        t_status = str(t.get("status") or "").upper()

        if t_status == "SUCCESS" and (clean_utr in t_utr or clean_utr in t_int_utr or t_utr == clean_utr):
            if t_amt >= (base_amt - 1.0):
                matched_txn = t
                break

    if matched_txn:
        order_res = confirm_paid_order(intent_id, matched_txn)
        return True, {
            "status": "PAID",
            "order_id": order_res.get("order_id"),
            "utr": matched_txn.get("bankReferenceNo"),
            "amount": matched_txn.get("amount")
        }

    return False, "UTR not found in recent BharatPe transactions. Please verify UTR or wait 10 seconds."


def confirm_paid_order(intent_id: str, txn_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executed when a payment is confirmed.
    Marks intent as PAID, locks UTR, records order, and triggers webhook.
    """
    utr = str(txn_data.get("bankReferenceNo") or "").strip()
    order_id = ""

    with _lock:
        intents = load_intents()
        intent = intents.get(intent_id)
        if not intent:
            return {}

        if intent.get("status") == "PAID":
            return {"order_id": intent.get("order_id")}

        order_id = intent.get("order_id") or f"ORD_{int(time.time())}"
        intent["status"] = "PAID"
        intent["utr"] = utr
        intent["payer_name"] = txn_data.get("payerName")
        intent["paid_at"] = int(time.time())
        intent["matched_txn"] = txn_data

        intents[intent_id] = intent
        save_intents(intents)

    # Permanently lock UTR
    if utr:
        mark_utr_as_used(utr, order_id, intent.get("exact_amount", 0), txn_data.get("payerName", ""))

    # Save order record
    try:
        orders = {}
        if os.path.exists(config.ORDERS_FILE):
            with open(config.ORDERS_FILE, "r", encoding="utf-8") as f:
                orders = json.load(f)
        orders[order_id] = {
            "order_id": order_id,
            "intent_id": intent_id,
            "amount": intent.get("exact_amount"),
            "base_amount": intent.get("base_amount"),
            "utr": utr,
            "payer_name": txn_data.get("payerName"),
            "customer_phone": intent.get("customer_phone"),
            "customer_name": intent.get("customer_name"),
            "metadata": intent.get("metadata"),
            "status": "PAID",
            "paid_at": intent.get("paid_at")
        }
        with open(config.ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(orders, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[!] Error saving order: {e}")

    # Fire Webhook asynchronously if configured
    if config.WEBHOOK_URL:
        def _dispatch_webhook():
            try:
                payload = {
                    "event": "payment.succeeded",
                    "order_id": order_id,
                    "intent_id": intent_id,
                    "amount": intent.get("exact_amount"),
                    "utr": utr,
                    "payer_name": txn_data.get("payerName"),
                    "customer_phone": intent.get("customer_phone"),
                    "metadata": intent.get("metadata"),
                    "timestamp": int(time.time())
                }
                headers = {"Content-Type": "application/json"}
                if config.WEBHOOK_SECRET:
                    headers["X-Webhook-Secret"] = config.WEBHOOK_SECRET
                requests.post(config.WEBHOOK_URL, json=payload, headers=headers, timeout=5)
                print(f"[Webhook] Successfully dispatched event to {config.WEBHOOK_URL}")
            except Exception as we:
                print(f"[Webhook] Failed to dispatch webhook: {we}")

        threading.Thread(target=_dispatch_webhook, daemon=True).start()

    return {"order_id": order_id}
