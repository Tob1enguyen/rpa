import os
import traceback
import sys
import json
import pandas as pd
from dotenv import load_dotenv

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

# Import các hàm từ 4 module đã tạo
from module1_scraper import get_product_data
from module1_catalog_pdf import extract_pdf_pages, suggest_product_name_from_catalog, generate_full_content_from_catalog
from module2_gemini import suggest_product_name, generate_full_content
from module3_image import rename_images_in_folder
from module4_cms import upload_to_cms

def clean_filename_for_folder(name):
    import re
    return re.sub(r'[\\/*?:"<>|]', "", name)

def find_catalog_pdf(brand_name):
    safe_brand = clean_filename_for_folder(brand_name)
    candidates = [
        os.path.join("tempdata", f"{safe_brand}.pdf"),
        os.path.join("tempdata", f"{brand_name}.pdf"),
        os.path.join("temp_data", f"{safe_brand}.pdf"),
        os.path.join("temp_data", f"{brand_name}.pdf"),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
            
    # Tìm kiếm không phân biệt hoa thường
    for folder in ["tempdata", "temp_data"]:
        if os.path.exists(folder):
            try:
                for f in os.listdir(folder):
                    if f.lower() in [f"{safe_brand.lower()}.pdf", f"{brand_name.lower()}.pdf"]:
                        return os.path.join(folder, f)
            except Exception:
                pass
    return None

def update_excel_status(brand_name, folder_name):
    safe_brand = clean_filename_for_folder(brand_name)
    # 1. Cập nhật file danh_sach_san_pham.xlsx (Link cào web)
    excel_file1 = f"{safe_brand}_danh_sach_san_pham.xlsx"
    if os.path.exists(excel_file1):
        try:
            df_excel = pd.read_excel(excel_file1)
            if 'Sản phẩm' in df_excel.columns and 'Trạng thái' in df_excel.columns:
                mask = df_excel['Sản phẩm'].astype(str) == folder_name
                if mask.any() and df_excel.loc[mask, 'Trạng thái'].iloc[0] != "Hoàn thành":
                    # Ép kiểu cột Trạng thái về dạng chuỗi/object để tránh lỗi khi pandas đọc cột rỗng thành số (float64)
                    df_excel['Trạng thái'] = df_excel['Trạng thái'].astype(object)
                    df_excel.loc[mask, 'Trạng thái'] = "Hoàn thành"
                    df_excel.to_excel(excel_file1, index=False)
        except Exception as ex:
            print(f"\n[CẢNH BÁO] Không thể lưu trạng thái vào {excel_file1}: {ex}")
            print(f"-> Lỗi này thường do bạn ĐANG MỞ file {excel_file1}. Vui lòng TẮT file Excel đi để bot có thể lưu!")

    # 2. Cập nhật file catalog.xlsx (Catalog PDF)
    excel_file2 = f"{safe_brand}_catalog.xlsx"
    if os.path.exists(excel_file2):
        try:
            df_excel = pd.read_excel(excel_file2)
            col_prod = 'Tên sản phẩm' if 'Tên sản phẩm' in df_excel.columns else ('Sản phẩm' if 'Sản phẩm' in df_excel.columns else None)
            col_status = 'Tình trạng' if 'Tình trạng' in df_excel.columns else ('Trạng thái' if 'Trạng thái' in df_excel.columns else None)
            if col_prod and col_status:
                mask = df_excel[col_prod].astype(str) == folder_name
                if mask.any() and df_excel.loc[mask, col_status].iloc[0] != "Hoàn thành":
                    df_excel[col_status] = df_excel[col_status].astype(object)
                    df_excel.loc[mask, col_status] = "Hoàn thành"
                    df_excel.to_excel(excel_file2, index=False)
        except Exception as ex:
            print(f"\n[CẢNH BÁO] Không thể lưu trạng thái vào {excel_file2}: {ex}")
            print(f"-> Lỗi này thường do bạn ĐANG MỞ file {excel_file2}. Vui lòng TẮT file Excel đi để bot có thể lưu!")

def run_phase1_data_prep(brand_name, url):
    print(f"\n==============================================")
    print(f"BẮT ĐẦU GIAI ĐOẠN 1: CHUẨN BỊ DỮ LIỆU")
    print(f"Thương hiệu: {brand_name}")
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
        safe_brand = clean_filename_for_folder(brand_name)
        safe_name = clean_filename_for_folder(final_name)
        folder_path = os.path.join("temp_data", safe_brand, safe_name)
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
    brand_name = input("\nNhập tên thương hiệu (hãng) muốn chạy Giai đoạn 1: ").strip()
    if not brand_name:
        print("Tên thương hiệu không được để trống!")
        return
        
    safe_brand = clean_filename_for_folder(brand_name)
    excel_file = f"{safe_brand}_danh_sach_san_pham.xlsx"
    
    if not os.path.exists(excel_file):
        print(f"\n[Thông báo] Không tìm thấy '{excel_file}'. Đang tạo mẫu...")
        df_template = pd.DataFrame({
            "Đường dẫn": ["https://www.suzumokikou.com/products/products/sushi-making-machine/ssn-jlxtrs-jlx/"],
            "Hình ảnh": ["1-3"],
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
    if 'Hình ảnh' not in df.columns:
        df['Hình ảnh'] = ""
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
            status = run_phase1_data_prep(brand_name, url)
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
                    
                # Nghỉ giải lao 60s sau khi xong 1 sản phẩm (nếu chưa phải sản phẩm cuối cùng)
                if index != pending_df.index[-1]:
                    print("\n>>> BOT ĐANG NGHỈ GIẢI LAO TRƯỚC KHI TẠO SẢN PHẨM TIẾP THEO <<<")
                    import sys
                    import time
                    for remaining in range(60, 0, -1):
                        sys.stdout.write(f"\rThời gian chờ còn lại: {remaining:2d} giây... ")
                        sys.stdout.flush()
                        time.sleep(1)
                    print("\rBắt đầu tiếp tục...                             ")

def run_phase1_catalog_pdf():
    print(f"\n==============================================")
    print(f"BẮT ĐẦU GIAI ĐOẠN 1: CHUẨN BỊ DỮ LIỆU TỪ CATALOG PDF")
    print(f"==============================================\n")
    
    brand_name = input("Nhập tên thương hiệu (hãng) cho catalog PDF: ").strip()
    if not brand_name:
        print("Tên thương hiệu không được để trống!")
        return

    safe_brand = clean_filename_for_folder(brand_name)
    
    # 1. TÌM FILE PDF CATALOG
    pdf_path = find_catalog_pdf(brand_name)
    if not pdf_path:
        print(f"\n[LỖI] Không tìm thấy file PDF catalog cho thương hiệu '{brand_name}'.")
        print(f"-> Vui lòng chép file '{brand_name}.pdf' (ví dụ: {safe_brand}.pdf) vào thư mục 'tempdata' (hoặc 'temp_data') trước khi chạy.")
        return

    print(f"-> Đã tìm thấy file catalog: {pdf_path}")
    excel_file = f"{safe_brand}_catalog.xlsx"
    
    # 2. KIỂM TRA FILE EXCEL
    if not os.path.exists(excel_file):
        print(f"\n[Thông báo] Chưa có file '{excel_file}'. Đang khởi tạo mẫu...")
        df_template = pd.DataFrame({
            "Số trang": ["16-17"],
            "Model": ["SKK-B1104S"],
            "Hình ảnh": ["1-3"],
            "Tên sản phẩm": [""],
            "Tình trạng": [""]
        })
        df_template.to_excel(excel_file, index=False)
        print(f"-> [THÀNH CÔNG] Đã khởi tạo file Excel '{excel_file}' với 5 cột chuẩn:")
        print("   [Số trang, Model, Hình ảnh, Tên sản phẩm, Tình trạng]")
        print(f"-> Bạn hãy mở file '{excel_file}', điền 'Số trang' (vd: 16-17) và 'Model' (vd: SKK-B1104S) cho các sản phẩm.")
        print(f"-> Sau đó lưu và ĐÓNG file Excel lại, rồi chọn lại chức năng này để bot xử lý nhé.\n")
        return

    # 3. KIỂM TRA QUYỀN TRUY CẬP FILE EXCEL
    try:
        with open(excel_file, 'a'):
            pass
    except PermissionError:
        print(f"\n[LỖI NGHIÊM TRỌNG] BẠN CHƯA TẮT FILE EXCEL '{excel_file}' !!!")
        print("-> Vui lòng ĐÓNG file Excel trước khi chạy.")
        return

    df = pd.read_excel(excel_file)
    if 'Số trang' not in df.columns or 'Model' not in df.columns:
        print(f"-> [Lỗi] File '{excel_file}' thiếu cột 'Số trang' hoặc 'Model'. Vui lòng kiểm tra lại cấu trúc file.")
        return

    if 'Hình ảnh' not in df.columns:
        df['Hình ảnh'] = ""
    if 'Tên sản phẩm' not in df.columns:
        df['Tên sản phẩm'] = ""
    if 'Tình trạng' not in df.columns:
        df['Tình trạng'] = ""

    df['Số trang'] = df['Số trang'].fillna("").astype(str)
    df['Model'] = df['Model'].fillna("").astype(str)
    df['Tên sản phẩm'] = df['Tên sản phẩm'].fillna("").astype(str)
    df['Tình trạng'] = df['Tình trạng'].fillna("").astype(str)

    # Lọc các dòng cần chạy: có Số trang và Model, Tình trạng chưa hoàn thành hoặc Tên sản phẩm chưa có
    mask_pending = (df['Số trang'].str.strip() != "") & \
                   (df['Số trang'].str.strip().str.lower() != "nan") & \
                   (df['Model'].str.strip() != "") & \
                   (df['Model'].str.strip().str.lower() != "nan") & \
                   ((df['Tình trạng'].str.strip() != "Hoàn thành") | (df['Tên sản phẩm'].str.strip() == ""))

    pending_df = df[mask_pending]
    if pending_df.empty:
        print(f"-> Tất cả sản phẩm trong '{excel_file}' đã hoàn thành (hoặc chưa điền Số trang/Model).")
        return

    total_pending = len(pending_df)
    print(f"\nTìm thấy {total_pending} sản phẩm cần xử lý trong '{excel_file}'.")

    temp_dir = os.path.join("temp_data", safe_brand, "_temp")
    os.makedirs(temp_dir, exist_ok=True)

    import shutil

    for loop_idx, (index, row) in enumerate(pending_df.iterrows()):
        page_str = str(row['Số trang']).strip()
        model_name = str(row['Model']).strip()
        
        print(f"\n==============================================")
        print(f"ĐANG XỬ LÝ SẢN PHẨM [{loop_idx + 1}/{total_pending}]")
        print(f"Thương hiệu: {brand_name}")
        print(f"Model: {model_name}")
        print(f"Số trang trong catalog: {page_str}")
        print(f"==============================================\n")

        temp_slice_pdf = os.path.join(temp_dir, f"slice_{clean_filename_for_folder(model_name)}.pdf")
        
        try:
            # 1. Cắt trang PDF
            print(">>> BƯỚC 1: TRÍCH XUẤT CÁC TRANG LIÊN QUAN TỪ FILE CATALOG")
            extract_pdf_pages(pdf_path, page_str, temp_slice_pdf)

            # 2. Gợi ý Tên sản phẩm
            print("\n>>> BƯỚC 2: AI ĐỌC TRANG PDF & MODEL ĐỀ XUẤT TÊN SẢN PHẨM")
            suggested_name = suggest_product_name_from_catalog(temp_slice_pdf, model_name)

            print("\n" + "="*50)
            print(f"💡 AI đề xuất tên sản phẩm: {suggested_name}")
            print("="*50)

            user_input = input("Nhấn Enter để ĐỒNG Ý tên này, hoặc GÕ TÊN MỚI nếu muốn thay đổi: ").strip()
            final_name = user_input if user_input else suggested_name
            safe_name = clean_filename_for_folder(final_name)

            # Tạo thư mục chính thức cho sản phẩm
            product_dir = os.path.join("temp_data", safe_brand, safe_name)
            os.makedirs(product_dir, exist_ok=True)

            # 3. AI Viết bài chi tiết
            print(f"\n>>> BƯỚC 3: AI VIẾT BÀI CHI TIẾT & BẢNG THÔNG SỐ CHO MODEL {model_name}")
            content_data = generate_full_content_from_catalog(temp_slice_pdf, model_name, final_name)

            json_path = os.path.join(product_dir, "data.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(content_data, f, ensure_ascii=False, indent=4)

            # Di chuyển file PDF trích xuất vào thư mục sản phẩm để lưu trữ
            final_pdf_dest = os.path.join(product_dir, "catalog_pages.pdf")
            shutil.copy2(temp_slice_pdf, final_pdf_dest)
            if os.path.exists(temp_slice_pdf):
                try:
                    os.remove(temp_slice_pdf)
                except Exception:
                    pass

            # 4. Cập nhật Excel ngay
            df.at[index, 'Tên sản phẩm'] = final_name
            df.at[index, 'Tình trạng'] = "Hoàn thành"
            try:
                df.to_excel(excel_file, index=False)
                print(f"-> Đã lưu cập nhật vào '{excel_file}' (Tình trạng: Hoàn thành).")
            except PermissionError:
                print(f"\n[LỖI NGHIÊM TRỌNG] BẠN ĐANG MỞ FILE EXCEL '{excel_file}'. Vui lòng đóng lại.")
                break

            print(f"\n[THÀNH CÔNG] Đã chuẩn bị xong dữ liệu cho sản phẩm: {final_name}")
            print(f"-> Thư mục dữ liệu: {product_dir}")
            print("-> Bạn có thể chép ảnh (1, 2, 3...) vào thư mục này hoặc dùng kho picture trước khi đăng CMS.\n")

            # Nghỉ giải lao giữa các sản phẩm để tránh quá tải API
            if loop_idx < total_pending - 1:
                print("\n>>> BOT ĐANG NGHỈ GIẢI LAO TRƯỚC KHI XỬ LÝ SẢN PHẨM TIẾP THEO <<<")
                import time
                for remaining in range(30, 0, -1):
                    sys.stdout.write(f"\rThời gian chờ còn lại: {remaining:2d} giây... ")
                    sys.stdout.flush()
                    time.sleep(1)
                print("\rBắt đầu tiếp tục...                             ")

        except Exception as e:
            print(f"\n[LỖI] Xảy ra lỗi khi xử lý model '{model_name}': {e}")
            traceback.print_exc()
            if "Hệ thống Gemini liên tục báo quá tải" in str(e):
                print("\n[CẢNH BÁO] API Gemini bị lỗi quá tải sau nhiều lần thử. Dừng tiến trình.")
                break
            continue

def parse_image_indices(text):
    indices = set()
    for part in str(text).split(','):
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                indices.update(range(int(start), int(end) + 1))
            except Exception:
                pass
        else:
            try:
                indices.add(int(part))
            except Exception:
                pass
    return sorted(list(indices))

def fetch_images_for_product(brand_name, folder_name, image_string):
    if not str(image_string).strip() or str(image_string).lower() == 'nan':
        return
        
    safe_brand = clean_filename_for_folder(brand_name)
    picture_dir = os.path.join("picture", f"{safe_brand} picture")
    target_dir = os.path.join("temp_data", safe_brand, folder_name)
    
    if not os.path.exists(picture_dir):
        print(f"-> Thư mục '{picture_dir}' không tồn tại. Bỏ qua lấy ảnh tự động.")
        return
        
    indices = parse_image_indices(image_string)
    if not indices:
        return
        
    import shutil
    from pathlib import Path
    
    copied = 0
    for file_name in os.listdir(picture_dir):
        try:
            stem = Path(file_name).stem
            if stem.isdigit() and int(stem) in indices:
                src = os.path.join(picture_dir, file_name)
                dst = os.path.join(target_dir, file_name)
                if not os.path.exists(dst):
                    shutil.copy2(src, dst)
                    copied += 1
        except Exception:
            pass
            
    if copied > 0:
        print(f"-> Đã gom {copied} ảnh từ kho picture vào thư mục sản phẩm.")

def run_phase2_auto_post():
    print(f"\n==============================================")
    print(f"BẮT ĐẦU GIAI ĐOẠN 2: ĐỔI TÊN ẢNH VÀ ĐĂNG BÀI")
    print(f"==============================================\n")
    
    brand_name = input("Nhập tên thương hiệu (hãng) muốn đăng bài (bỏ qua để thoát): ").strip()
    if not brand_name:
        return
        
    safe_brand = clean_filename_for_folder(brand_name)
    base_dir = os.path.join("temp_data", safe_brand)
    
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
        
        # Đọc cột Hình ảnh từ Excel (hỗ trợ cả danh_sach_san_pham và catalog)
        image_string = ""
        excel_file1 = f"{safe_brand}_danh_sach_san_pham.xlsx"
        if os.path.exists(excel_file1):
            try:
                df_excel = pd.read_excel(excel_file1)
                if 'Sản phẩm' in df_excel.columns and 'Hình ảnh' in df_excel.columns:
                    mask = df_excel['Sản phẩm'].astype(str) == folder_name
                    if mask.any():
                        image_string = df_excel.loc[mask, 'Hình ảnh'].iloc[0]
            except Exception:
                pass
                
        if not image_string:
            excel_file2 = f"{safe_brand}_catalog.xlsx"
            if os.path.exists(excel_file2):
                try:
                    df_excel = pd.read_excel(excel_file2)
                    col_prod = 'Tên sản phẩm' if 'Tên sản phẩm' in df_excel.columns else ('Sản phẩm' if 'Sản phẩm' in df_excel.columns else None)
                    if col_prod and 'Hình ảnh' in df_excel.columns:
                        mask = df_excel[col_prod].astype(str) == folder_name
                        if mask.any():
                            image_string = df_excel.loc[mask, 'Hình ảnh'].iloc[0]
                except Exception:
                    pass
                
        # Gọi hàm copy ảnh
        if image_string:
            fetch_images_for_product(brand_name, folder_name, image_string)
        
        if os.path.exists(status_path):
            print(f"-> Bỏ qua thư mục '{folder_name}' (Đã đăng thành công trước đó).")
            update_excel_status(brand_name, folder_name)
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
            update_excel_status(brand_name, folder_name)
                    
            print(f"\n[THÀNH CÔNG] Đã đăng bài xong cho: {product_name}")
            
            # Tạm nghỉ 3s sau mỗi lần đăng xong 1 sản phẩm
            print("-> Đang nghỉ 3s trước khi tiếp tục...")
            import time
            time.sleep(3)
                
        except Exception as e:
            print(f"\n[LỖI] Phát hiện lỗi ở Giai đoạn 2 thư mục '{folder_name}':")
            traceback.print_exc()

def main():
    load_dotenv()
    
    if not os.path.exists("picture"):
        os.makedirs("picture")
    if not os.path.exists("tempdata"):
        os.makedirs("tempdata")
    
    while True:
        print("\n=== CÔNG CỤ TỰ ĐỘNG HÓA M2MSTORE (PHIÊN BẢN 2 GIAI ĐOẠN) ===")
        print("1. [GIAI ĐOẠN 1] Chuẩn bị Dữ liệu (Hàng loạt từ Excel - Link Web)")
        print("2. [GIAI ĐOẠN 1] Chuẩn bị Dữ liệu (File catalog pdf)")
        print("3. [GIAI ĐOẠN 2] Đăng bài lên CMS (Từ thư mục temp_data)")
        print("q. Thoát")
        
        choice = input("Vui lòng chọn (1/2/3/q): ").strip()
        
        if choice == '1':
            run_phase1_excel()
        elif choice == '2':
            run_phase1_catalog_pdf()
        elif choice == '3':
            run_phase2_auto_post()
        elif choice.lower() == 'q':
            print("Đã thoát chương trình.")
            sys.exit(0)
        else:
            print("Lựa chọn không hợp lệ, vui lòng thử lại.")

if __name__ == "__main__":
    main()
