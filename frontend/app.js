// Free UPI Payment Gateway - Client Controller

let currentIntent = null;
let pollTimer = null;
let countdownInterval = null;

function setPresetAmount(amt) {
    document.getElementById('input-amount').value = amt;
}

function showToast(msg) {
    let t = document.getElementById('global-toast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'global-toast';
        t.className = 'fixed bottom-5 left-1/2 -translate-x-1/2 bg-slate-900 text-yellow-300 font-comic font-black text-xs px-4 py-2.5 rounded-2xl border-2 border-yellow-300 shadow-comic-md z-50 transition-all';
        document.body.appendChild(t);
    }
    t.innerText = msg;
    t.style.opacity = '1';
    setTimeout(() => {
        t.style.opacity = '0';
    }, 2800);
}

// ----------------- INITIATE PAYMENT FLOW -----------------

async function startPaymentFlow() {
    const amtInput = document.getElementById('input-amount');
    const phoneInput = document.getElementById('input-phone');
    const orderInput = document.getElementById('input-order-id');
    const btn = document.getElementById('btn-create-intent');

    const amount = parseFloat(amtInput.value || 0);
    if (!amount || amount <= 0) {
        alert("Please enter a valid amount!");
        return;
    }

    const origBtn = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin text-base"></i> Generating Standee QR...';
    btn.disabled = true;

    try {
        const payload = {
            amount: amount,
            order_id: orderInput.value.trim() || undefined,
            customer_phone: phoneInput.value.trim() || undefined
        };

        const res = await fetch('/api/checkout/create-intent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!data.success) {
            alert("Error: " + (data.detail || "Could not create payment intent"));
            return;
        }

        currentIntent = data.data;
        renderPaymentStep(currentIntent);

    } catch (e) {
        console.error(e);
        alert("Network error. Please make sure the gateway server is running!");
    } finally {
        btn.innerHTML = origBtn;
        btn.disabled = false;
    }
}

// ----------------- RENDER STANDEE & START POLLING -----------------

function renderPaymentStep(intent) {
    document.getElementById('step-init').classList.add('hidden');
    document.getElementById('step-success').classList.add('hidden');
    document.getElementById('step-payment').classList.remove('hidden');

    const amtStr = parseFloat(intent.exact_amount).toFixed(2);
    document.getElementById('display-exact-amount').innerText = `₹${amtStr}`;
    document.getElementById('display-vpa').innerText = intent.upi_vpa;

    const qrImg = document.getElementById('display-qr-img');
    const spinner = document.getElementById('qr-loading-spinner');
    spinner.classList.remove('hidden');

    qrImg.onload = () => spinner.classList.add('hidden');
    qrImg.onerror = () => spinner.classList.add('hidden');
    qrImg.src = intent.qr_code_url;

    // Start 10-minute countdown
    startCountdown(intent.expires_at);

    // Start Real-Time BharatPe Polling (every 2.5 seconds)
    startPolling(intent.intent_id);
}

function startCountdown(expiresAt) {
    if (countdownInterval) clearInterval(countdownInterval);
    const el = document.getElementById('display-countdown');

    function update() {
        const now = Math.floor(Date.now() / 1000);
        const rem = Math.max(0, expiresAt - now);
        const m = Math.floor(rem / 60);
        const s = rem % 60;
        el.innerText = `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;

        if (rem <= 0) {
            clearInterval(countdownInterval);
            document.getElementById('display-polling-status').innerText = "⚠️ Payment window expired. Please retry.";
        }
    }
    update();
    countdownInterval = setInterval(update, 1000);
}

function startPolling(intentId) {
    if (pollTimer) clearInterval(pollTimer);

    pollTimer = setInterval(async () => {
        try {
            const res = await fetch(`/api/checkout/poll-status?intent_id=${encodeURIComponent(intentId)}`);
            const data = await res.json();

            if (data.status === 'PAID') {
                clearInterval(pollTimer);
                if (countdownInterval) clearInterval(countdownInterval);
                onPaymentSuccess(data);
            } else if (data.status === 'EXPIRED') {
                clearInterval(pollTimer);
                document.getElementById('display-polling-status').innerText = "Session expired.";
            }
        } catch (e) {
            console.warn("Polling error:", e);
        }
    }, 2500);
}

function onPaymentSuccess(data) {
    document.getElementById('step-payment').classList.add('hidden');
    document.getElementById('step-success').classList.remove('hidden');

    document.getElementById('success-order-id').innerText = `#${data.order_id || currentIntent.order_id}`;
    document.getElementById('success-amount').innerText = `₹${parseFloat(data.amount || currentIntent.exact_amount).toFixed(2)}`;
    document.getElementById('success-utr').innerText = data.utr || 'BharatPe Auto-Verified';

    showToast("🎉 Payment 100% Verified! Funds received in bank.");
}

function resetPaymentFlow() {
    if (pollTimer) clearInterval(pollTimer);
    if (countdownInterval) clearInterval(countdownInterval);
    currentIntent = null;

    document.getElementById('step-payment').classList.add('hidden');
    document.getElementById('step-success').classList.add('hidden');
    document.getElementById('step-init').classList.remove('hidden');
}

// ----------------- COPY HELPERS -----------------

function copyAmount() {
    if (!currentIntent) return;
    const amtStr = parseFloat(currentIntent.exact_amount).toFixed(2);
    navigator.clipboard.writeText(amtStr);
    showToast(`Copied Exact Amount: ₹${amtStr}`);
}

function copyVpa() {
    if (!currentIntent) return;
    navigator.clipboard.writeText(currentIntent.upi_vpa);
    showToast(`Copied VPA: ${currentIntent.upi_vpa}`);
}

// ----------------- MANUAL UTR FALLBACK -----------------

function toggleUtrAccordion() {
    const body = document.getElementById('utr-accordion-body');
    const chevron = document.getElementById('utr-chevron');
    const isHidden = body.classList.contains('hidden');
    body.classList.toggle('hidden', !isHidden);
    chevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
}

async function submitManualUtr() {
    if (!currentIntent) return;
    const input = document.getElementById('input-manual-utr');
    const errBox = document.getElementById('utr-error-box');
    const utr = input.value.trim();

    errBox.classList.add('hidden');
    if (utr.length < 8) {
        errBox.innerText = "Please enter a valid 12-digit UTR.";
        errBox.classList.remove('hidden');
        return;
    }

    try {
        const res = await fetch('/api/checkout/verify-utr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                intent_id: currentIntent.intent_id,
                utr: utr
            })
        });

        const data = await res.json();
        if (data.success) {
            onPaymentSuccess(data.data);
        } else {
            errBox.innerText = data.detail || "UTR verification failed. Please wait a moment and retry.";
            errBox.classList.remove('hidden');
        }
    } catch (e) {
        errBox.innerText = "Network error. Please try again.";
        errBox.classList.remove('hidden');
    }
}

// ----------------- CLIENT-SIDE CANVAS COMIC POSTER DOWNLOAD -----------------

function roundRect(ctx, x, y, width, height, radius, fill, stroke) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    if (fill) ctx.fill();
    if (stroke) ctx.stroke();
}

async function downloadComicPoster() {
    if (!currentIntent) return;
    const btn = document.getElementById('btn-download-qr');
    const origHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Generating Poster...';
    btn.disabled = true;

    const amt = parseFloat(currentIntent.exact_amount).toFixed(2);
    const filename = `UPI_Pay_Rs${amt}.png`;

    try {
        // High Resolution 800x1080 Canvas
        const canvas = document.createElement('canvas');
        canvas.width = 800;
        canvas.height = 1080;
        const ctx = canvas.getContext('2d');

        // Sunny FamPay Comic Yellow
        ctx.fillStyle = '#fde047';
        ctx.fillRect(0, 0, 800, 1080);

        // 10px Black Neo-Brutalist Border
        ctx.lineWidth = 10;
        ctx.strokeStyle = '#0f172a';
        ctx.strokeRect(10, 10, 780, 1060);

        // Header Pill: Black Pill with Pink Shadow
        ctx.fillStyle = '#f43397';
        roundRect(ctx, 64, 44, 672, 72, 36, true, false);
        ctx.fillStyle = '#0f172a';
        roundRect(ctx, 60, 40, 672, 72, 36, true, false);

        ctx.fillStyle = '#fde047';
        ctx.font = '900 28px Fredoka, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('⚡ FREE UPI PAY ⚡', 400, 86);

        // Amount Card
        ctx.fillStyle = '#0f172a';
        roundRect(ctx, 64, 138, 672, 126, 24, true, false);
        ctx.fillStyle = '#ffffff';
        roundRect(ctx, 60, 134, 672, 126, 24, true, false);
        ctx.lineWidth = 5;
        ctx.strokeStyle = '#0f172a';
        roundRect(ctx, 60, 134, 672, 126, 24, false, true);

        ctx.fillStyle = '#f43397';
        ctx.font = '900 16px Fredoka, sans-serif';
        ctx.fillText('💥 SCAN & PAY EXACT AMOUNT 💥', 400, 168);

        ctx.fillStyle = '#038d63';
        ctx.font = '900 52px Fredoka, sans-serif';
        ctx.fillText(`₹${amt}`, 400, 226);

        // QR Frame Card
        ctx.fillStyle = '#0f172a';
        roundRect(ctx, 154, 284, 492, 492, 28, true, false);
        ctx.fillStyle = '#ffffff';
        roundRect(ctx, 150, 280, 492, 492, 28, true, false);
        ctx.lineWidth = 6;
        ctx.strokeStyle = '#0f172a';
        roundRect(ctx, 150, 280, 492, 492, 28, false, true);

        // Neo-Brutalist Corner Brackets
        ctx.strokeStyle = '#f43397';
        ctx.lineWidth = 8;
        ctx.lineCap = 'round';
        ctx.beginPath();
        ctx.moveTo(175, 335); ctx.lineTo(175, 305); ctx.lineTo(205, 305);
        ctx.stroke();

        ctx.strokeStyle = '#038d63';
        ctx.beginPath();
        ctx.moveTo(595, 305); ctx.lineTo(625, 305); ctx.lineTo(625, 335);
        ctx.stroke();

        ctx.strokeStyle = '#038d63';
        ctx.beginPath();
        ctx.moveTo(175, 715); ctx.lineTo(175, 745); ctx.lineTo(205, 745);
        ctx.stroke();

        ctx.strokeStyle = '#f43397';
        ctx.beginPath();
        ctx.moveTo(595, 745); ctx.lineTo(625, 745); ctx.lineTo(625, 715);
        ctx.stroke();

        // Load QR image onto canvas
        const qrImg = document.getElementById('display-qr-img');
        if (qrImg && qrImg.src) {
            const tempImg = new Image();
            tempImg.crossOrigin = 'anonymous';
            await new Promise((resolve, reject) => {
                tempImg.onload = resolve;
                tempImg.onerror = reject;
                tempImg.src = qrImg.src;
            });
            ctx.drawImage(tempImg, 196, 326, 400, 400);

            // Centered Lightning Emblem
            ctx.fillStyle = '#0f172a';
            ctx.beginPath();
            ctx.arc(400, 526, 30, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = '#facc15';
            ctx.beginPath();
            ctx.arc(398, 524, 28, 0, Math.PI * 2);
            ctx.fill();
            ctx.lineWidth = 3;
            ctx.strokeStyle = '#0f172a';
            ctx.stroke();

            ctx.font = '24px sans-serif';
            ctx.fillStyle = '#0f172a';
            ctx.fillText('⚡', 398, 532);
        }

        // Accepted UPI Apps Banner Card
        ctx.fillStyle = '#0f172a';
        roundRect(ctx, 64, 796, 672, 70, 18, true, false);
        ctx.fillStyle = '#ffffff';
        roundRect(ctx, 60, 792, 672, 70, 18, true, false);
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#0f172a';
        roundRect(ctx, 60, 792, 672, 70, 18, false, true);

        ctx.font = '800 18px Fredoka, sans-serif';
        ctx.fillStyle = '#0f172a';
        ctx.fillText('📸 PhonePe   •   Google Pay   •   Paytm   •   BHIM   •   Cred', 400, 834);

        // 3-Step Guide Card
        ctx.fillStyle = '#0f172a';
        roundRect(ctx, 64, 886, 672, 142, 20, true, false);
        ctx.fillStyle = '#ffffff';
        roundRect(ctx, 60, 882, 672, 142, 20, true, false);
        ctx.lineWidth = 4;
        ctx.strokeStyle = '#0f172a';
        roundRect(ctx, 60, 882, 672, 142, 20, false, true);

        ctx.font = '900 16px Fredoka, sans-serif';
        ctx.fillStyle = '#f43397';
        ctx.fillText('⚡ 3 EASY STEPS TO PAY ⚡', 400, 916);

        ctx.font = '700 15px Plus Jakarta Sans, sans-serif';
        ctx.fillStyle = '#334155';
        ctx.fillText('1. Save this QR to your gallery or scan with another phone', 400, 946);
        ctx.fillText(`2. Open any UPI App and pay the EXACT amount (₹${amt})`, 400, 974);
        ctx.fillStyle = '#038d63';
        ctx.font = '800 15px Plus Jakarta Sans, sans-serif';
        ctx.fillText('3. Once paid, the transaction is verified within 3 seconds! ✓', 400, 1002);

        // Download Blob
        canvas.toBlob((blob) => {
            if (!blob) throw new Error('Blob creation failed');
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 10000);
            showToast("✅ Standee QR poster downloaded!");
        }, 'image/png');

    } catch (e) {
        console.warn("Canvas failed, falling back to server poster:", e);
        window.location.href = `/api/checkout/download-qr?intent_id=${encodeURIComponent(currentIntent.intent_id)}`;
    } finally {
        setTimeout(() => {
            btn.innerHTML = origHtml;
            btn.disabled = false;
        }, 1200);
    }
}
