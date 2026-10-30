/**
 * Example: Creating a UPI payment intent & polling for status in Node.js.
 */

const GATEWAY_URL = 'http://localhost:8000';

async function testPayment() {
    console.log('[*] Creating payment intent...');

    const createRes = await fetch(`${GATEWAY_URL}/api/checkout/create-intent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            amount: 250,
            order_id: `NODE_ORDER_${Date.now()}`,
            customer_phone: '9876543210'
        })
    });

    const createData = await createRes.json();
    if (!createData.success) {
        console.error('Failed to create intent:', createData);
        return;
    }

    const { intent_id, exact_amount, upi_uri, qr_code_url } = createData.data;
    console.log(`[+] Intent Created: ${intent_id}`);
    console.log(`[+] Exact Payable Amount: INR ${exact_amount}`);
    console.log(`[+] UPI URI: ${upi_uri}`);
    console.log(`[+] QR Code URL: ${qr_code_url}`);
    console.log('\n[*] Polling payment status...');

    const timer = setInterval(async () => {
        const pollRes = await fetch(`${GATEWAY_URL}/api/checkout/poll-status?intent_id=${encodeURIComponent(intent_id)}`);
        const statusData = await pollRes.json();

        if (statusData.status === 'PAID') {
            clearInterval(timer);
            console.log('\n🎉 PAYMENT CONFIRMED!');
            console.log(`Order ID: ${statusData.order_id}`);
            console.log(`Bank UTR: ${statusData.utr}`);
            console.log(`Amount: INR ${statusData.amount}`);
        } else if (statusData.status === 'EXPIRED') {
            clearInterval(timer);
            console.log('\n❌ Session expired.');
        } else {
            process.stdout.write(`.`);
        }
    }, 2500);
}

testPayment().catch(console.error);
