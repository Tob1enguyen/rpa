import os
import sys
import re
import json
import time
from pypdf import PdfReader, PdfWriter
from module2_gemini import _upload_and_retry_gemini

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

def parse_page_ranges(page_str):
    """
    Chuyển chuỗi số trang (ví dụ: '16-17', '16', '16, 18-20')
    thành danh sách các số trang theo thứ tự tăng dần (1-based index).
    """
    if not page_str or str(page_str).strip().lower() == 'nan':
        return []
    
    # Xử lý trường hợp số nguyên hoặc float chuyển thành chuỗi (ví dụ: 16.0)
    cleaned = str(page_str).strip()
    if cleaned.endswith(".0"):
        cleaned = cleaned[:-2]
        
    pages = set()
    parts = cleaned.split(',')
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                sub_parts = part.split('-', 1)
                start = int(float(sub_parts[0].strip()))
                end = int(float(sub_parts[1].strip()))
                if start <= end:
                    pages.update(range(start, end + 1))
                else:
                    pages.update(range(end, start + 1))
            except Exception as e:
                print(f"[CẢNH BÁO] Không thể đọc dải trang '{part}': {e}")
        else:
            try:
                pages.add(int(float(part)))
            except Exception as e:
                print(f"[CẢNH BÁO] Không thể đọc số trang '{part}': {e}")
                
    return sorted(list(pages))

def extract_pdf_pages(input_pdf_path, page_str, output_pdf_path):
    """
    Cắt các trang được chỉ định từ input_pdf_path và lưu vào output_pdf_path.
    """
    if not os.path.exists(input_pdf_path):
        raise FileNotFoundError(f"Không tìm thấy file PDF gốc: {input_pdf_path}")
        
    page_numbers = parse_page_ranges(page_str)
    if not page_numbers:
        raise ValueError(f"Không có số trang hợp lệ nào được chỉ định từ: '{page_str}'")
        
    reader = PdfReader(input_pdf_path)
    total_pages = len(reader.pages)
    
    writer = PdfWriter()
    valid_count = 0
    for p in page_numbers:
        if 1 <= p <= total_pages:
            writer.add_page(reader.pages[p - 1]) # Chuyển 1-based sang 0-based index
            valid_count += 1
        else:
            print(f"[CẢNH BÁO] Trang {p} nằm ngoài phạm vi tài liệu (1 đến {total_pages}). Bỏ qua trang này.")
            
    if valid_count == 0:
        raise ValueError(f"Tất cả các số trang yêu cầu ({page_numbers}) đều vượt quá tổng số trang của file ({total_pages}).")
        
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
    with open(output_pdf_path, "wb") as f_out:
        writer.write(f_out)
        
    print(f"[{__name__}] Đã trích xuất {valid_count} trang ({page_numbers}) vào: {output_pdf_path}")
    return output_pdf_path

def suggest_product_name_from_catalog(pdf_path, model_name, api_key=None):
    """
    Dùng Gemini đọc các trang PDF đã cắt và Model để đề xuất Tên sản phẩm chuẩn HoReCa.
    """
    prompt = f"""Bạn là chuyên gia về thiết bị bếp công nghiệp & F&B (HoReCa).
Tài liệu đính kèm là các trang trích xuất từ catalog sản phẩm.
Model mục tiêu cần trích xuất thông tin là: "{model_name}"

Hãy đọc tài liệu đính kèm và đề xuất tên sản phẩm (bao gồm "Tên loại thiết bị" + "MÃ MODEL").
YÊU CẦU CỰC KỲ QUAN TRỌNG:
1. BẮT BUỘC sử dụng thuật ngữ tiếng Việt chuyên ngành thiết bị HoReCa (Khách sạn, Nhà hàng, F&B).
2. Tên sản phẩm BẮT BUỘC phải chứa mã model: "{model_name}".
3. TUYỆT ĐỐI KHÔNG xuất hiện tên thương hiệu của nhà sản xuất (ví dụ: Suzumo, Nayati...).
Ví dụ: "Máy nắm cơm sushi tự động {model_name}", "Bếp chiên nhúng điện {model_name}", "Lò nướng tầng gas {model_name}".
Trả về DUY NHẤT 1 dòng chứa tên sản phẩm, không thêm bất kỳ lời giải thích hay văn bản nào khác."""

    raw_text = _upload_and_retry_gemini(pdf_path=pdf_path, text_path=None, prompt=prompt, api_key=api_key)
    return raw_text.strip().replace('"', '')

def generate_full_content_from_catalog(pdf_path, model_name, product_name, api_key=None):
    """
    Dùng Gemini tạo toàn bộ nội dung SEO và bảng thông số kỹ thuật HTML chuẩn hóa từ catalog PDF và Model.
    Áp dụng nguyên tắc Zero-Hallucination: chỉ lấy dữ liệu thực tế của Model, cấm bịa đặt.
    """
    prompt = f"""Bạn là chuyên gia viết bài chuẩn SEO cho website thương mại điện tử chuyên ngành thiết bị bếp và F&B (HoReCa).
Model mục tiêu cần trích xuất thông tin là: "{model_name}"
Tên sản phẩm CHÍNH THỨC là: "{product_name}"

Hãy đọc kỹ tài liệu PDF đính kèm (các trang trích xuất từ catalog).

NGUYÊN TẮC BÓC TÁCH DỮ LIỆU & CHỐNG ẢO GIÁC (CỰC KỲ QUAN TRỌNG):
1. TRÊN TRANG CÓ THỂ CÓ NHIỀU MODEL KHÁC NHAU: Bạn CHỈ ĐƯỢC trích xuất thông tin và thông số kỹ thuật của ĐÚNG MODEL "{model_name}".
2. ĐỐI VỚI BẢNG THÔNG SỐ KỸ THUẬT: Đối chiếu kỹ bảng thông số trong tài liệu, CHỈ lấy đúng dòng/cột thông số của model "{model_name}" (kích thước WxDxH, công suất điện/gas, dung tích, trọng lượng, số họng, nguồn điện...). TUYỆT ĐỐI KHÔNG lấy nhầm thông số của model khác nằm cùng trang.
3. TUYỆT ĐỐI KHÔNG TỰ BỊA ĐẶT THÔNG SỐ HOẶC TÍNH NĂNG: Chỉ sử dụng thông tin có thực tế trên tài liệu. Không suy đoán, không sáng tác thông số kỹ thuật.
4. BẢNG THÔNG SỐ KỸ THUẬT BẮT BUỘC DỊCH SANG TIẾNG VIỆT:
   - Giữ nguyên chính xác số liệu kỹ thuật, mã ký hiệu và đơn vị đo lường thực tế (mm, cm, W, kW, V, Hz, kg, cmm, m3/h, Lít, bar, ºC...).
   - BẮT BUỘC DỊCH 100% TẤT CẢ tiêu đề cột, tên thông số, và các phân loại/chú thích trong bảng sang TIẾNG VIỆT chuẩn chuyên ngành. TUYỆT ĐỐI KHÔNG để nguyên tiếng Anh.
   - Ví dụ:
     + "Size (WxDxH)" / "Dimensions" -> "Kích thước (Rộng x Sâu x Cao)" hoặc "Kích thước (Dài x Rộng x Cao)"
     + "Power Consumption" -> "Công suất tiêu thụ"
     + "Maximum Air Volume" -> "Lưu lượng khí tối đa"
     + "Air Velocity" -> "Vận tốc khí"
     + "For 2 persons" -> "Dành cho 2 người" (hoặc "Loại 2 người")
     + "Power Supply" / "Voltage" -> "Nguồn điện"
     + "Weight" -> "Trọng lượng"
     + "Capacity" -> "Dung tích" hoặc "Năng suất"
     + "Material" -> "Chất liệu"
5. Tự động suy luận "Quốc gia xuất xứ" của thương hiệu từ tài liệu.
6. TUYỆT ĐỐI KHÔNG xuất hiện tên thương hiệu của nhà sản xuất trong toàn bộ văn bản.
7. Tự động sinh danh sách từ khóa chuẩn SEO. Lồng ghép tự nhiên vào Nội dung chi tiết.
8. TUYỆT ĐỐI KHÔNG dùng dấu ** (markdown bold) trong văn bản, KHÔNG được in đậm từ khóa.

TRẢ VỀ ĐÚNG ĐỊNH DẠNG JSON (Không dùng markdown) VỚI 5 TRƯỜNG SAU:
{{
  "seo_keywords": "Danh sách ĐÚNG 10 từ khóa SEO. Tất cả các từ khóa BẮT BUỘC phải viết chữ thường (không viết hoa). Mỗi từ khóa viết tự nhiên (giữ nguyên khoảng trắng giữa các chữ), các từ khóa phân cách nhau bằng dấu phẩy (ví dụ: máy làm cơm, khuôn cơm onigiri).",
  "seo_title": "{product_name}",
  "slug": "Đường dẫn URL chuẩn SEO tạo từ seo_title, viết thường, không dấu, phân cách bằng dấu gạch ngang.",
  "short_desc": "Mô tả ngắn 3-4 dòng liệt kê tính năng. TỔNG CHIỀU DÀI BẮT BUỘC DƯỚI 400 KÝ TỰ. KHÔNG DÙNG DẤU GẠCH NGANG '-' Ở ĐẦU DÒNG. Viết cực kỳ súc tích. BẮT BUỘC XUỐNG DÒNG (\\n) sau mỗi ý. Dòng cuối cùng BẮT BUỘC là: Xuất xứ [Tên Quốc Gia]",
  "full_content": "Nội dung chi tiết viết bằng HTML đơn giản (chỉ dùng thẻ <p>). BỐ CỤC BẮT BUỘC: ĐẦU TIÊN là dòng <p>Thông số kỹ thuật</p>, tiếp theo là Bảng thông số <table> (border='1' cellpadding='5' cellspacing='0') CHỈ CHỨA thông số của model {model_name} (BẮT BUỘC TOÀN BỘ TIÊU ĐỀ VÀ THÔNG SỐ DỊCH SANG TIẾNG VIỆT). KẾ TIẾP BẮT BUỘC có thẻ <p>&nbsp;</p> và theo sau là <p>Xuất xứ [Tên Quốc Gia]</p>. DƯỚI CÙNG là tính năng chi tiết của sản phẩm bám sát thực tế trong tài liệu. KHÔNG dùng thẻ in đậm (<b>, <strong>, <th>) trong bảng."
}}
"""
    print(f"[{__name__}] Đang nhờ Gemini phân tích catalog PDF và viết bài chi tiết cho model {model_name}...")
    raw_text = _upload_and_retry_gemini(pdf_path=pdf_path, text_path=None, prompt=prompt, api_key=api_key)
    
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
            "short_desc": f"Sản phẩm {product_name} chính hãng.",
            "full_content": f"<p>{raw_text}</p>"
        }
        
    # Xử lý an toàn: Đảm bảo không có dấu ** và short_desc < 480 ký tự
    if "full_content" in data:
        data["full_content"] = data["full_content"].replace("**", "")
        
    if "short_desc" in data and len(data["short_desc"]) > 480:
        data["short_desc"] = data["short_desc"][:480]
        
    print(f"[{__name__}] Gemini xử lý xong bài viết cho {model_name}!")
    return data
