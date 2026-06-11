import os
import time
import json
from google import genai

def _upload_and_retry_gemini(pdf_path, text_path, prompt, api_key=None):
    if not api_key:
        api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "AIzaSy_YOUR_API_KEY_HERE":
        raise ValueError("Chưa cấu hình GEMINI_API_KEY trong file .env hoặc tham số.")

    client = genai.Client(api_key=api_key)
    
    target_file = pdf_path if pdf_path and os.path.exists(pdf_path) else text_path
    if not target_file or not os.path.exists(target_file):
        raise ValueError("Không tìm thấy file PDF hay Text để phân tích.")
        
    print(f"[{__name__}] Đang tải dữ liệu lên hệ thống Gemini...")
    uploaded_file = client.files.upload(file=target_file)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[uploaded_file, prompt]
            )
            return response.text
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str or "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                if attempt < max_retries - 1:
                    wait_time = 32 if "429" in error_str else 10
                    print(f"[{__name__}] Server Gemini báo lỗi quá tải. Đang đợi {wait_time}s (Lần {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Lỗi API: Hệ thống Gemini liên tục báo quá tải sau {max_retries} lần thử. Lỗi gốc: {error_str}")
            else:
                raise e
    return ""

def suggest_product_name(pdf_path=None, text_path=None, product_url="", api_key=None):
    prompt = f"""Đường dẫn: {product_url}
Hãy đọc tài liệu đính kèm và đưa ra "Tên chung của loại sản phẩm" + "MÃ SẢN PHẨM" (nếu có).
TUYỆT ĐỐI KHÔNG xuất hiện tên thương hiệu của nhà sản xuất (như Suzumo).
Ví dụ: Máy nắn cơm sushi SSF-JXA.
Trả về DUY NHẤT 1 dòng chứa tên sản phẩm, không thêm bất kỳ văn bản nào khác."""
    
    raw_text = _upload_and_retry_gemini(pdf_path, text_path, prompt, api_key)
    # Loại bỏ dấu ngoặc kép hoặc khoảng trắng dư thừa
    return raw_text.strip().replace('"', '')

def generate_full_content(pdf_path=None, text_path=None, product_url="", product_name="", api_key=None):
    prompt = f"""Bạn là chuyên gia viết bài chuẩn SEO cho website thương mại điện tử.
Đường dẫn của sản phẩm là: {product_url}
Tên sản phẩm CHÍNH THỨC là: "{product_name}"

Hãy đọc tài liệu đính kèm (PDF hoặc Văn bản), sau đó tự động suy luận ra "Quốc gia xuất xứ" của thương hiệu.

YÊU CẦU CỰC KỲ QUAN TRỌNG:
1. TUYỆT ĐỐI KHÔNG xuất hiện tên thương hiệu của nhà sản xuất (ví dụ: Suzumo) trong toàn bộ văn bản.
2. Tự động sinh ra danh sách các từ khóa chuẩn SEO. Lồng ghép tự nhiên vào Nội dung chi tiết.

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON (Không dùng markdown) VỚI 5 TRƯỜNG SAU:
{{
  "seo_keywords": "Chuỗi các từ khóa SEO. PHẢI phân cách nhau bằng dấu phẩy KHÔNG CÓ KHOẢNG TRẮNG.",
  "seo_title": "{product_name}",
  "slug": "Đường dẫn URL chuẩn SEO tạo từ seo_title, viết thường, không dấu, phân cách bằng dấu gạch ngang.",
  "short_desc": "Mô tả ngắn 4-5 dòng liệt kê tính năng. KHÔNG DÙNG DẤU GẠCH NGANG '-' Ở ĐẦU DÒNG. Súc tích. BẮT BUỘC XUỐNG DÒNG (\\n) sau mỗi ý. Dòng cuối cùng BẮT BUỘC là: Xuất xứ [Tên Quốc Gia]",
  "full_content": "Nội dung chi tiết viết bằng HTML đơn giản (chỉ dùng thẻ <p>). BỐ CỤC BẮT BUỘC: ĐẦU TIÊN là dòng <p>Thông số kỹ thuật</p>, tiếp theo là Bảng thông số <table> (border='1' cellpadding='5' cellspacing='0'). KẾ TIẾP BẮT BUỘC có thẻ <p>&nbsp;</p> và theo sau là <p>Xuất xứ [Tên Quốc Gia]</p>. DƯỚI CÙNG là tính năng chi tiết. KHÔNG dùng thẻ in đậm (<b>, <strong>, <th>) trong bảng."
}}
"""
    print(f"[{__name__}] Đang nhờ Gemini phân tích và viết bài chi tiết...")
    raw_text = _upload_and_retry_gemini(pdf_path, text_path, prompt, api_key)
    
    if raw_text.startswith("```json"):
        raw_text = raw_text.replace("```json", "", 1)
    if raw_text.startswith("```"):
        raw_text = raw_text.replace("```", "", 1)
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
        
    try:
        data = json.loads(raw_text.strip())
    except json.JSONDecodeError as e:
        print(f"[{__name__}] Lỗi parse JSON từ Gemini, trả về nội dung mặc định. Lỗi: {e}")
        data = {
            "seo_title": product_name,
            "short_desc": "Sản phẩm chính hãng.",
            "full_content": f"<p>{raw_text}</p>"
        }
        
    print(f"[{__name__}] Gemini xử lý xong bài viết!")
    return data
