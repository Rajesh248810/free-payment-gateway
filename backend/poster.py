# -*- coding: utf-8 -*-
"""
FamPay-Style Neo-Brutalist Comic QR Poster Generator.
Renders an eye-catching 800x1060 PNG poster ready for download or gallery scan.
"""

import io
from PIL import Image, ImageDraw, ImageFont
from typing import Optional


def render_comic_qr_poster(
    raw_qr_bytes: bytes,
    amount: float,
    merchant_name: str = "FREE UPI GATEWAY",
    upi_vpa: str = ""
) -> bytes:
    """
    Renders an 800x1060 high-impact Neo-Brutalist Comic payment standee poster.
    """
    try:
        W, H = 800, 1060
        img = Image.new("RGB", (W, H), color="#FDE047")  # Sunny FamPay Yellow
        draw = ImageDraw.Draw(img)

        # 1. Outer 8px Slate-900 border
        draw.rectangle([8, 8, W - 9, H - 9], outline="#0F172A", width=8)

        # 2. Header Banner: Pink drop shadow + Black pill
        draw.rounded_rectangle([74, 44, W - 66, 114], radius=24, fill="#F43397")
        draw.rounded_rectangle([70, 40, W - 70, 110], radius=24, fill="#0F172A", outline="#0F172A", width=3)

        # 3. Amount Box: Shadow + White card
        draw.rounded_rectangle([74, 134, W - 66, 244], radius=20, fill="#0F172A")
        draw.rounded_rectangle([70, 130, W - 70, 240], radius=20, fill="#FFFFFF", outline="#0F172A", width=5)

        # 4. QR Frame Box: Shadow + White card
        draw.rounded_rectangle([144, 274, W - 136, 774], radius=24, fill="#0F172A")
        draw.rounded_rectangle([140, 270, W - 140, 770], radius=24, fill="#FFFFFF", outline="#0F172A", width=6)

        # Paste raw QR code if provided
        if raw_qr_bytes:
            try:
                qr_im = Image.open(io.BytesIO(raw_qr_bytes)).convert("RGBA")
                qr_im = qr_im.resize((410, 410), Image.Resampling.LANCZOS)
                img.paste(qr_im, (195, 315), qr_im)
            except Exception as e:
                print(f"[!] Could not paste QR image: {e}")

        # 5. Signature Neo-Brutalist Corner Brackets
        # Top-Left (Magenta)
        draw.line([(165, 335), (165, 295), (205, 295)], fill="#F43397", width=8)
        # Top-Right (Emerald)
        draw.line([(W - 205, 295), (W - 165, 295), (W - 165, 335)], fill="#038D63", width=8)
        # Bottom-Left (Emerald)
        draw.line([(165, 705), (165, 745), (205, 745)], fill="#038D63", width=8)
        # Bottom-Right (Magenta)
        draw.line([(W - 205, 745), (W - 165, 745), (W - 165, 705)], fill="#F43397", width=8)

        # 6. Center FamPay Floating Badge
        draw.ellipse([370, 490, 430, 550], fill="#0F172A")
        draw.ellipse([373, 493, 427, 547], fill="#FACC15")

        # 7. Accepted Apps Ribbon
        draw.rounded_rectangle([74, 804, W - 66, 874], radius=16, fill="#0F172A")
        draw.rounded_rectangle([70, 800, W - 70, 870], radius=16, fill="#FFFFFF", outline="#0F172A", width=4)

        # 8. 3-Step Guide Box
        draw.rounded_rectangle([74, 894, W - 66, 1014], radius=16, fill="#0F172A")
        draw.rounded_rectangle([70, 890, W - 70, 1010], radius=16, fill="#FFFFFF", outline="#0F172A", width=4)

        # Try rendering clean text using system font or standard truetype font
        try:
            font_title = ImageFont.truetype("arialbd.ttf", 26)
            font_price = ImageFont.truetype("arialbd.ttf", 48)
            font_sub = ImageFont.truetype("arialbd.ttf", 16)
            font_apps = ImageFont.truetype("arialbd.ttf", 18)
            font_steps = ImageFont.truetype("arial.ttf", 16)
        except Exception:
            font_title = ImageFont.load_default()
            font_price = font_title
            font_sub = font_title
            font_apps = font_title
            font_steps = font_title

        # Draw Header Text
        header_text = f"⚡ {merchant_name.upper()} PAY"
        draw.text((W // 2, 75), header_text, fill="#FDE047", font=font_title, anchor="mm")

        # Draw Amount Card Text
        draw.text((W // 2, 160), "💥 SCAN & PAY EXACT AMOUNT 💥", fill="#F43397", font=font_sub, anchor="mm")
        draw.text((W // 2, 205), f"INR {amount:.2f}", fill="#038D63", font=font_price, anchor="mm")

        # Accepted Apps Text
        draw.text((W // 2, 835), "PhonePe  •  Google Pay  •  Paytm  •  BHIM  •  Cred", fill="#0F172A", font=font_apps, anchor="mm")

        # 3-Step Guide Text
        draw.text((W // 2, 920), "⚡ 3 EASY STEPS TO PAY ⚡", fill="#F43397", font=font_sub, anchor="mm")
        draw.text((W // 2, 952), f"1. Save this QR to gallery or scan from second phone", fill="#334155", font=font_steps, anchor="mm")
        draw.text((W // 2, 980), f"2. Open any UPI App and pay the EXACT amount (INR {amount:.2f})", fill="#038D63", font=font_steps, anchor="mm")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    except Exception as e:
        print(f"[!] Error generating comic poster: {e}")
        return raw_qr_bytes
