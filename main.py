import os
import traceback
import sys
import json
import pandas as pd
from dotenv import load_dotenv

# Import các hàm từ 4 module đã tạo
from module1_scraper import get_product_data
from module2_gemini import suggest_product_name, generate_full_content
from module3_image import rename_images_in_folder
from module4_cms import upload_to_cms

def clean_filename_for_folder(name):
    import re
    return re.sub(r'[\\/*?:"<>|]', "", name)

def run_phase1_data_prep(url):
    print(f"\n==============================================")
    print(f"BẮT ĐẦU GIAI ĐOẠN 1: CHUẨN BỊ DỮ LIỆU")
    print(f"URL: {url}")
    print(f"==============================================\n")
    try:
        # BƯỚC 1: CÀO PDF VÀ TEXT
        print(">>> BƯỚC 1: LẤY DỮ LIỆU TỪ WEBSITE (KHÔNG LẤY ẢNH)")
        data = get_product_data(url, temp_dir="temp_data")
        pdf_path = data.get("pdf_path")
        text_path = data.get("text_path")
        
        # BƯỚC 2a: AI GỢI Ý TÊN SẢN PHẨM
        print("\n>>> BƯỚC 2a: AI GỢI Ý TÊN SẢN PHẨM")
        suggested_name = suggest_product_name(pdf_path, text_path, url)
        
        print("\n" + "="*50)
        print(f"💡 AI đề xuất tên sản phẩm: {suggested_name}")
        print("="*50)
        
        user_input = input("Nhấn Enter để ĐỒNG Ý tên này, hoặc GÕ TÊN MỚI nếu muốn thay đổi: ").strip()
        final_name = user_input if user_input else suggested_name
        
        # TẠO THƯ MỤC CHÍNH THỨC VÀ DI CHUYỂN FILE TẠM
        safe_name = clean_filename_for_folder(final_name)
        folder_path = os.path.join("temp_data", safe_name)
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            
        import shutil
        if pdf_path and os.path.exists(pdf_path):
            new_pdf_path = os.path.join(folder_path, os.path.basename(pdf_path))
            shutil.move(pdf_path, new_pdf_path)
            pdf_path = new_pdf_path
            
        if text_path and os.path.exists(text_path):
            new_text_path = os.path.join(folder_path, os.path.basename(text_path))
            shutil.move(text_path, new_text_path)
            text_path = new_text_path
            
        # Xóa thư mục tạm nếu rỗng
        try:
            temp_dir_path = os.path.dirname(data.get("text_path"))
            if temp_dir_path and os.path.exists(temp_dir_path) and not os.listdir(temp_dir_path):
                os.rmdir(temp_dir_path)
        except Exception:
            pass
            
        # BƯỚC 2b: AI VIẾT BÀI CHI TIẾT
        print(f"\n>>> BƯỚC 2b: AI VIẾT BÀI CHI TIẾT CHO SẢN PHẨM: {final_name}")
        content_data = generate_full_content(pdf_path, text_path, url, final_name)
        
        json_path = os.path.join(folder_path, "data.json")
            
        json_path = os.path.join(folder_path, "data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(content_data, f, ensure_ascii=False, indent=4)
            
        print(f"\n[THÀNH CÔNG] Đã lưu dữ liệu vào thư mục: {folder_path}")
        print("-> Bạn hãy vào thư mục này để CHÉP HÌNH ẢNH (đặt tên là 1, 2, 3...) trước khi chạy Giai đoạn 2 nhé.\n")
        
        return safe_name
        
    except Exception as e:
        print(f"\n[LỖI] Phát hiện lỗi trong Giai đoạn 1:")
        traceback.print_exc()
        if "Hệ thống Gemini liên tục báo quá tải" in str(e):
            print("\n[CẢNH BÁO] API Gemini bị lỗi quá tải sau nhiều lần thử.")
            return "API_OVERLOAD"
        return False

def run_phase1_excel():
    excel_file = "danh_sach_san_pham.xlsx"
    if not os.path.exists(excel_file):
        print(f"\n[Thông báo] Không tìm thấy '{excel_file}'. Đang tạo mẫu...")
        df_template = pd.DataFrame({
            "Đường dẫn": ["https://www.suzumokikou.com/products/products/sushi-making-machine/ssn-jlxtrs-jlx/"],
            "Sản phẩm": [""],
            "Trạng thái": [""]
        })
        df_template.to_excel(excel_file, index=False)
        print(f"-> Đã tạo '{excel_file}'. Hãy điền URL và chạy lại.")
        return

    # Check nếu file mở
    try:
        with open(excel_file, 'a'):
            pass
    except PermissionError:
        print(f"\n[LỖI NGHIÊM TRỌNG] BẠN CHƯA TẮT FILE EXCEL '{excel_file}' !!!")
        print("-> Vui lòng ĐÓNG file Excel trước khi chạy.")
        return

    df = pd.read_excel(excel_file)
    if 'Đường dẫn' not in df.columns:
        print("-> [Lỗi] File Excel không có cột 'Đường dẫn'. Vui lòng đổi tên cột hoặc dùng file mẫu mới.")
        return
        
    df = df.dropna(subset=['Đường dẫn'])
    if 'Sản phẩm' not in df.columns:
        df['Sản phẩm'] = ""
    if 'Trạng thái' not in df.columns:
        df['Trạng thái'] = ""
        
    df['Sản phẩm'] = df['Sản phẩm'].fillna("").astype(str)
    
    # Những dòng nào CHƯA có tên Sản phẩm thì mới chạy Giai đoạn 1
    pending_df = df[df['Sản phẩm'] == ""]
    
    if pending_df.empty:
        print("-> Tất cả URL đã hoàn thành Giai đoạn 1 (đã có Tên Sản Phẩm).")
        return
        
    for index, row in pending_df.iterrows():
        url = str(row['Đường dẫn']).strip()
        if url and url.lower() != 'nan':
            status = run_phase1_data_prep(url)
            if status == "API_OVERLOAD":
                print("\n[HỆ THỐNG] Dừng do sự cố API.")
                break
            elif status: # Nếu trả về tên thư mục
                df.at[index, 'Sản phẩm'] = status
                try:
                    df.to_excel(excel_file, index=False)
                except PermissionError:
                    print("\n[LỖI NGHIÊM TRỌNG] BẠN ĐANG MỞ FILE EXCEL. Buộc ngưng.")
                    break

def run_phase2_auto_post():
    print(f"\n==============================================")
    print(f"BẮT ĐẦU GIAI ĐOẠN 2: ĐỔI TÊN ẢNH VÀ ĐĂNG BÀI")
    print(f"==============================================\n")
    
    base_dir = "temp_data"
    if not os.path.exists(base_dir):
        print(f"Chưa có thư mục {base_dir}. Vui lòng chạy Giai đoạn 1 trước.")
        return
        
    folders = [f for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    if not folders:
        print(f"Không có thư mục sản phẩm nào trong {base_dir}.")
        return
        
    for i, folder_name in enumerate(folders):
        folder_path = os.path.join(base_dir, folder_name)
        json_path = os.path.join(folder_path, "data.json")
        status_path = os.path.join(folder_path, "posted.txt")
        
        if os.path.exists(status_path):
            print(f"-> Bỏ qua thư mục '{folder_name}' (Đã đăng thành công trước đó).")
            continue
            
        if not os.path.exists(json_path):
            print(f"-> Bỏ qua thư mục '{folder_name}' (Không có file data.json).")
            continue
            
        print(f"\n>> Đang xử lý thư mục: {folder_name} <<")
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                content_data = json.load(f)
                
            product_name = content_data.get("seo_title", folder_name)
            
            # MODULE 3: ĐỔI TÊN ẢNH
            print(">>> MODULE 3: ĐỔI TÊN ẢNH <<<")
            image_paths_dict = rename_images_in_folder(folder_path, product_name)
            
            # MODULE 4: ĐĂNG BÀI LÊN CMS
            print(">>> MODULE 4: BOT PLAYWRIGHT BẮT ĐẦU ĐĂNG BÀI <<<")
            upload_to_cms(
                seo_title=product_name, 
                seo_keywords=content_data.get("seo_keywords", product_name), 
                slug=content_data.get("slug", ""), 
                short_desc=content_data.get("short_desc", ""), 
                html_content=content_data.get("full_content", ""), 
                thumbnail_path=image_paths_dict.get("thumbnail"), 
                gallery_paths=image_paths_dict.get("gallery"),
                headless=False
            )
            
            # Đánh dấu đã post xong
            with open(status_path, "w", encoding="utf-8") as f:
                f.write("DONE")
                
            # CẬP NHẬT EXCEL
            excel_file = "danh_sach_san_pham.xlsx"
            if os.path.exists(excel_file):
                try:
                    df_excel = pd.read_excel(excel_file)
                    if 'Sản phẩm' in df_excel.columns and 'Trạng thái' in df_excel.columns:
                        mask = df_excel['Sản phẩm'].astype(str) == folder_name
                        if mask.any():
                            df_excel.loc[mask, 'Trạng thái'] = "Hoàn thành"
                            df_excel.to_excel(excel_file, index=False)
                except Exception as ex:
                    print(f"-> Không thể cập nhật trạng thái vào Excel (Có thể file đang mở).")
                    
            print(f"\n[THÀNH CÔNG] Đã đăng bài xong cho: {product_name}")
            
            # Tạm nghỉ 60s (Chỉ nghỉ nếu chưa phải thư mục cuối cùng)
            if i < len(folders) - 1:
                # Kiểm tra thư mục tiếp theo xem đã posted chưa (để đỡ chờ nếu thư mục cuối cùng đã posted)
                next_status = os.path.join(base_dir, folders[-1], "posted.txt")
                if not os.path.exists(next_status) or i < len(folders) - 2:
                    print("\n>>> BOT ĐANG NGHỈ GIẢI LAO TRƯỚC KHI ĐĂNG SẢN PHẨM TIẾP THEO <<<")
                    import sys
                    import time
                    for remaining in range(60, 0, -1):
                        sys.stdout.write(f"\rThời gian chờ còn lại: {remaining:2d} giây... ")
                        sys.stdout.flush()
                        time.sleep(1)
                    print("\rBắt đầu tiếp tục...                             ")
                
        except Exception as e:
            print(f"\n[LỖI] Phát hiện lỗi ở Giai đoạn 2 thư mục '{folder_name}':")
            traceback.print_exc()

def main():
    load_dotenv()
    
    while True:
        print("\n=== CÔNG CỤ TỰ ĐỘNG HÓA M2MSTORE (PHIÊN BẢN 2 GIAI ĐOẠN) ===")
        print("1. [GIAI ĐOẠN 1] Chuẩn bị Dữ liệu (Thủ công 1 Link)")
        print("2. [GIAI ĐOẠN 1] Chuẩn bị Dữ liệu (Hàng loạt từ Excel)")
        print("3. [GIAI ĐOẠN 2] Đăng bài lên CMS (Từ thư mục temp_data)")
        print("q. Thoát")
        
        choice = input("Vui lòng chọn (1/2/3/q): ").strip()
        
        if choice == '1':
            url = input("Nhập URL: ").strip()
            if url:
                run_phase1_data_prep(url)
        elif choice == '2':
            run_phase1_excel()
        elif choice == '3':
            run_phase2_auto_post()
        elif choice.lower() == 'q':
            print("Đã thoát chương trình.")
            sys.exit(0)
        else:
            print("Lựa chọn không hợp lệ, vui lòng thử lại.")

if __name__ == "__main__":
    main()
