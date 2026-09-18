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
                    wait_time = 60
                    print(f"[{__name__}] Server Gemini báo lỗi quá tải. Đang đợi {wait_time}s (Lần {attempt + 1}/{max_retries})...")
                    time.sleep(wait_time)
                else:
                    raise Exception(f"Lỗi API: Hệ thống Gemini liên tục báo quá tải sau {max_retries} lần thử. Lỗi gốc: {error_str}")
            else:
                raise e
    return ""

def suggest_product_name(pdf_path=None, text_path=None, product_url="", api_key=None):
    prompt = f"""Đường dẫn: {product_url}
Hãy đọc tài liệu đính kèm và đề xuất tên sản phẩm (bao gồm "Tên loại thiết bị" + "MÃ SẢN PHẨM" nếu có).
YÊU CẦU:
1. BẮT BUỘC sử dụng thuật ngữ tiếng Việt chuyên ngành thiết bị HoReCa (Khách sạn, Nhà hàng, F&B).
2. TUYỆT ĐỐI KHÔNG xuất hiện tên thương hiệu của nhà sản xuất (ví dụ: Suzumo).
Ví dụ: "Máy nắm cơm sushi tự động SSF-JXA", "Lò nướng pizza chuyên dụng điện".
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
3. TUYỆT ĐỐI KHÔNG dùng dấu ** (markdown bold) trong văn bản, KHÔNG được in đậm từ khóa.
4. BẢNG THÔNG SỐ KỸ THUẬT BẮT BUỘC DỊCH SANG TIẾNG VIỆT:
   - Giữ nguyên chính xác số liệu kỹ thuật, mã hiệu và đơn vị đo lường (mm, cm, W, kW, V, Hz, kg, cmm, lít, bar, ºC...). TUYỆT ĐỐI KHÔNG tự bịa đặt hay suy đoán số liệu.
   - BẮT BUỘC DỊCH 100% tất cả tiêu đề cột, tên thông số và mô tả trong bảng sang TIẾNG VIỆT chuẩn chuyên ngành (Ví dụ: "Kích thước (Rộng x Sâu x Cao)", "Công suất tiêu thụ", "Lưu lượng khí tối đa", "Nguồn điện", "Trọng lượng", "Chất liệu"... TUYỆT ĐỐI KHÔNG để nguyên tiếng Anh).

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON (Không dùng markdown) VỚI 5 TRƯỜNG SAU:
{{
  "seo_keywords": "Danh sách ĐÚNG 10 từ khóa SEO. Tất cả các từ khóa BẮT BUỘC phải viết chữ thường (không viết hoa). Mỗi từ khóa viết tự nhiên (giữ nguyên khoảng trắng giữa các chữ), các từ khóa phân cách nhau bằng dấu phẩy (ví dụ: máy làm cơm, khuôn cơm onigiri).",
  "seo_title": "{product_name}",
  "slug": "Đường dẫn URL chuẩn SEO tạo từ seo_title, viết thường, không dấu, phân cách bằng dấu gạch ngang.",
  "short_desc": "Mô tả ngắn 3-4 dòng liệt kê tính năng. TỔNG CHIỀU DÀI BẮT BUỘC DƯỚI 400 KÝ TỰ. KHÔNG DÙNG DẤU GẠCH NGANG '-' Ở ĐẦU DÒNG. Viết cực kỳ súc tích. BẮT BUỘC XUỐNG DÒNG (\\n) sau mỗi ý. Dòng cuối cùng BẮT BUỘC là: Xuất xứ [Tên Quốc Gia]",
  "full_content": "Nội dung chi tiết viết bằng HTML đơn giản (chỉ dùng thẻ <p>). BỐ CỤC BẮT BUỘC: ĐẦU TIÊN là dòng <p>Thông số kỹ thuật</p>, tiếp theo là Bảng thông số <table> (border='1' cellpadding='5' cellspacing='0') (BẮT BUỘC TOÀN BỘ TIÊU ĐỀ VÀ THÔNG SỐ DỊCH SANG TIẾNG VIỆT). KẾ TIẾP BẮT BUỘC có thẻ <p>&nbsp;</p> và theo sau là <p>Xuất xứ [Tên Quốc Gia]</p>. DƯỚI CÙNG là tính năng chi tiết. KHÔNG dùng thẻ in đậm (<b>, <strong>, <th>) trong bảng."
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
        
    # Xử lý an toàn: Đảm bảo không có dấu ** và short_desc < 500 ký tự
    if "full_content" in data:
        data["full_content"] = data["full_content"].replace("**", "")
        
    if "short_desc" in data and len(data["short_desc"]) > 480:
        data["short_desc"] = data["short_desc"][:480]
        
    print(f"[{__name__}] Gemini xử lý xong bài viết!")
    return data
