#!/usr/bin/env bash
# Free UPI Payment Gateway - cURL Cheat Sheet

# 1. Create a Payment Session
curl -X POST "http://localhost:8000/api/checkout/create-intent" \
     -H "Content-Type: application/json" \
     -d '{
       "amount": 100,
       "order_id": "ORDER_12345",
       "customer_phone": "9876543210",
       "customer_name": "Amaresh"
     }'

# 2. Check Payment Status
curl -X GET "http://localhost:8000/api/checkout/poll-status?intent_id=YOUR_INTENT_ID"

# 3. Verify Manual 12-Digit UTR Fallback
curl -X POST "http://localhost:8000/api/checkout/verify-utr" \
     -H "Content-Type: application/json" \
     -d '{
       "intent_id": "YOUR_INTENT_ID",
       "utr": "045183118335"
     }'

# 4. Download FamPay-Style Branded Poster
curl -X GET "http://localhost:8000/api/checkout/download-qr?intent_id=YOUR_INTENT_ID" \
     --output "Payment_Poster.png"

# 5. Gateway Health Check
curl -X GET "http://localhost:8000/api/gateway/health"
