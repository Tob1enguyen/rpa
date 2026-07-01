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
    prompt = f"""Bạn là chuyên gia Content Marketing & SEO cho website thương mại điện tử m2mstore.vn.
Đường dẫn của sản phẩm là: {product_url}
Tên sản phẩm CHÍNH THỨC (Từ khóa chính - Keyword) là: "{product_name}"
Hãy đọc tài liệu đính kèm (PDF hoặc Văn bản), sau đó tự động suy luận ra "Quốc gia xuất xứ" của thương hiệu.
QUY TẮC NỘI DUNG & SEO BẮT BUỘC (Áp dụng cho bài viết chi tiết):
1. TUYỆT ĐỐI KHÔNG xuất hiện tên thương hiệu của nhà sản xuất gốc (ví dụ: Suzumo, Nayati...) trong toàn bộ văn bản.
2. Viết đúng, đủ thông tin, đúng trọng tâm, súc tích, tránh lan man. Văn phong chuyên nghiệp, phù hợp với ngành thiết bị HoReCa.
3. Bố cục bài viết phải có Mở bài (Sapo), Thân bài (các Heading H2, H3) và Kết bài.
   - Mở bài: Tối đa 4 dòng, KHÁI QUÁT bài viết. TỪ KHÓA CHÍNH (Tên sản phẩm) phải xuất hiện trong 150 ký tự đầu tiên. Trả lời được 3 câu hỏi: Viết cho ai? Giúp họ như thế nào? Mang lại lợi ích gì?
   - Thân bài: Dùng thẻ <h2> và <h3> rõ ràng. Có câu nối giữa các Heading và Bullet. Triển khai các câu ngắn (20-30 từ), đoạn ngắn (tối đa 3 dòng). In đậm (dùng thẻ <strong>) các ý quan trọng để người dùng ghi nhớ.
   - Kết bài: Tối đa 4 dòng. Tóm tắt và đánh giá toàn bộ bài viết. IN ĐẬM từ khóa chính. TỪ KHÓA CHÍNH xuất hiện trong 150 ký tự cuối cùng.
4. Mật độ từ khóa: Từ khóa chính xuất hiện ở H1 (Tiêu đề), Sapo, một số H2/H3, và Kết bài (Mật độ dưới 3%, khoảng 300 từ có 1 từ khóa).
5. Trình bày: Chuyển text thành biểu bảng (Bảng thông số kỹ thuật) nếu có. Thu hút thị giác bằng thẻ <blockquote> nếu cần. Dùng HTML đơn giản.
TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON (Không dùng markdown bao bọc JSON) VỚI 5 TRƯỜNG SAU:
{{
  "seo_keywords": "Danh sách ĐÚNG 10 từ khóa SEO (gồm từ khóa chính, từ khóa phụ). Tất cả BẮT BUỘC viết chữ thường, phân cách bằng dấu phẩy.",
  "seo_title": "Tiêu đề SEO dài 65-70 ký tự, không trùng lặp, chứa từ khóa chính, bao quát bài viết, hấp dẫn (có số, tính từ).",
  "slug": "Đường dẫn URL chuẩn SEO tạo từ seo_title, viết thường, không dấu, phân cách bằng dấu gạch ngang.",
  "short_desc": "Mô tả ngắn 3-4 dòng liệt kê tính năng. TỔNG CHIỀU DÀI DƯỚI 400 KÝ TỰ. KHÔNG DÙNG DẤU GẠCH NGANG '-' Ở ĐẦU DÒNG. Xuống dòng (\\n) sau mỗi ý. Dòng cuối cùng BẮT BUỘC là: Xuất xứ [Tên Quốc Gia]",
  "full_content": "Nội dung bài viết chi tiết định dạng HTML. BẮT BUỘC dùng thẻ <h2>, <h3>, <p>, <ul><li>, <strong>. BỐ CỤC: Bắt đầu bằng đoạn Sapo -> Các đoạn H2/H3 -> <h2>Thông số kỹ thuật</h2> -> <table> (border='1' cellpadding='5' cellspacing='0') -> <p>Xuất xứ [Tên Quốc Gia]</p> -> Đoạn Kết bài."
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
        
    # Xử lý an toàn: short_desc < 500 ký tự
    if "short_desc" in data and len(data["short_desc"]) > 480:
        data["short_desc"] = data["short_desc"][:480]
        
    print(f"[{__name__}] Gemini xử lý xong bài viết!")
    return data
