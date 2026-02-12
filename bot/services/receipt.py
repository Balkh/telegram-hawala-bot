
import io
import logging
from PIL import Image, ImageDraw, ImageFont
from arabic_reshaper import reshape
from bidi.algorithm import get_display
import os

logger = logging.getLogger(__name__)

def get_font(size=24):
    """انتخاب فونت مناسب برای فارسی در ویندوز یا لینوکس"""
    font_paths = [
        "C:\\Windows\\Fonts\\tahoma.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def format_farsi(text):
    """اصلاح نمایش متن فارسی برای Pillow"""
    if not text:
        return ""
    reshaped_text = reshape(str(text))
    bidi_text = get_display(reshaped_text)
    return bidi_text

def generate_receipt_image(transaction_data):
    """
    تولید تصویر رسید حواله
    transaction_data: dict containing code, sender, receiver, amount, currency, etc.
    """
    # تنظیمات ابعاد رسید
    width = 600
    height = 800
    background_color = (255, 255, 255)
    primary_color = (41, 128, 185)  # آبی حرفه‌ای
    text_color = (44, 62, 80)
    
    # ایجاد تصویر خام
    img = Image.new('RGB', (width, height), color=background_color)
    draw = ImageDraw.Draw(img)
    
    # فونت‌ها
    font_header = get_font(40)
    font_body = get_font(24)
    font_footer = get_font(18)
    
    # کشیدن کادر دور رسید
    draw.rectangle([10, 10, width-10, height-10], outline=primary_color, width=3)
    
    # هدر
    header_text = format_farsi("رسید حواله سیستم هوشمند")
    draw.text((width//2, 60), header_text, fill=primary_color, font=font_header, anchor="mm")
    
    draw.line([50, 100, width-50, 100], fill=primary_color, width=2)
    
    # محتوا
    y_offset = 150
    line_height = 50
    
    fields = [
        ("کد حواله:", transaction_data.get('transaction_code', '')),
        ("فرستنده:", transaction_data.get('sender_name', '')),
        ("گیرنده:", transaction_data.get('receiver_name', '')),
        ("تذکره گیرنده:", transaction_data.get('receiver_tazkira', '')),
        ("مبلغ:", f"{transaction_data.get('amount', 0):,.0f} {transaction_data.get('currency', '')}"),
        ("عامل مبدأ:", transaction_data.get('sender_agent', '')),
        ("عامل مقصد:", transaction_data.get('receiver_agent', '')),
        ("تاریخ ثبت:", transaction_data.get('created_at', '')),
    ]
    
    for label, value in fields:
        # برچسب (راست‌چین)
        label_farsi = format_farsi(label)
        draw.text((width-60, y_offset), label_farsi, fill=text_color, font=font_body, anchor="rm")
        
        # مقدار (چپ‌چین یا وسط‌چین برای فارسی بهتر است راست‌چین باشد ولی در ستون مقابل)
        value_farsi = format_farsi(value)
        draw.text((60, y_offset), value_farsi, fill=text_color, font=font_body, anchor="lm")
        
        y_offset += line_height
        draw.line([50, y_offset-10, width-50, y_offset-10], fill=(236, 240, 241), width=1)
        y_offset += 10

    # فوتر و بارکد (شبیه‌سازی شده با کد)
    footer_text = format_farsi("این رسید به صورت سیستمی صادر شده است.")
    draw.text((width//2, height-80), footer_text, fill=(127, 140, 141), font=font_footer, anchor="mm")
    
    # خروجی به صورت بایت
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    
    return img_byte_arr
