# -*- coding: utf-8 -*-
"""
Background Auto-Reconciler Daemon.
Monitors pending intents and automatically verifies received payments against BharatPe
every 5 seconds, ensuring seamless checkout even if customer closes browser or switches app.
"""

import time
import threading
from . import config
from . import gateway


def start_background_payment_reconciler(interval: int = 5) -> threading.Thread:
    """
    Starts a daemon thread that continuously matches active pending intents.
    """
    def _reconciler_loop():
        print(f"[*] Background Payment Reconciler active (polling every {interval}s).")
        while True:
            try:
                time.sleep(interval)
                now = time.time()
                with gateway._lock:
                    intents = gateway.load_intents()
                    # Check active pending intents created in the last 30 minutes
                    pending_ids = [
                        k for k, v in intents.items()
                        if v.get("status") == "PENDING" and (now - v.get("created_at", 0) < 1800)
                    ]

                for intent_id in pending_ids:
                    try:
                        res = gateway.check_intent_status(intent_id)
                        if res.get("status") == "PAID":
                            print(f"[+] Reconciler auto-confirmed payment for {intent_id} -> Order #{res.get('order_id')}")
                    except Exception as e:
                        pass
            except Exception as outer_e:
                time.sleep(interval)

    thread = threading.Thread(target=_reconciler_loop, daemon=True, name="PaymentReconciler")
    thread.start()
    return thread
