import os
import re
from playwright.sync_api import sync_playwright

def upload_to_cms(seo_title, seo_keywords, slug, short_desc, html_content, thumbnail_path=None, gallery_paths=None, headless=False):
    """
    Sử dụng Playwright để đăng tải bài viết lên CMS m2mstore.vn
    headless=False: Bật giao diện trình duyệt để dễ quan sát (nếu chạy tự động hoàn toàn thì nên đổi thành True)
    """
    email = os.environ.get("CMS_EMAIL")
    password = os.environ.get("CMS_PASSWORD")
    login_url = os.environ.get("CMS_LOGIN_URL", "https:vn")
    
    if not email or not password:
        raise ValueError("Chưa cấu hình CMS_EMAIL hoặc CMS_PASSWORD trong file .env")

    with sync_playwright() as p:
        # Sử dụng trình duyệt Chrome THẬT thay vì Chromium giả lập để đảm bảo giao diện hiển thị 100% giống máy thật
        browser = p.chromium.launch(headless=headless, channel="chrome", args=['--start-maximized'])
        context = browser.new_context(no_viewport=True)
        page = context.new_page()
        
        # Lắng nghe và tự động nhấn OK (accept) cho TẤT CẢ các popup thông báo native của trình duyệt (ví dụ: "Đã lưu thay đổi!")
        page.on("dialog", lambda dialog: dialog.accept())
        
        try:
            print(f"[{__name__}] Mở trang đăng nhập: {login_url}")
            page.goto(login_url)
            page.get_by_role("textbox", name="Email").fill(email)
            page.get_by_role("textbox", name="Mật khẩu").fill(password)
            # Nút đăng nhập có khoảng trắng ở cuối trong CMS của bạn
            page.get_by_role("button", name=re.compile("Đăng nhập")).click()
            
            # Đợi load xong. Nếu bị đẩy ra trang chủ thì ép về trang admin
            page.wait_for_load_state("networkidle")
            if "admin" not in page.url:
                page.goto("https://vn")
        except Exception as e:
            raise Exception(f"[LỖI] Xảy ra lỗi ở bước ĐĂNG NHẬP CMS. Kiểm tra lại đường dẫn, email/mật khẩu hoặc kết nối mạng.\nChi tiết mã lỗi: {e}")
            
        try:
            print(f"[{__name__}] Vào trang tạo Sản phẩm...")
            # Tìm link menu chứa chữ "Sản phẩm"
            page.get_by_role("link", name=re.compile("Sản phẩm")).click()
            page.get_by_role("button", name="Tạo sản phẩm").click()
            
            print(f"[{__name__}] Nhập Tên sản phẩm & Từ khóa: {seo_title}")
            # Điền Tên sản phẩm trước để CMS tự động copy sang Từ khóa (nếu có tính năng đó)
            page.locator("input[name=\"title\"]").fill(seo_title)
            # Sau đó ghi đè Từ khóa trang bằng danh sách từ khóa đầy đủ chuẩn SEO
            page.locator("input[name=\"meta_keyword\"]").fill(seo_keywords)
            
            print(f"[{__name__}] Điền Đường dẫn (slug): {slug}")
            if slug:
                try:
                    page.locator("input[name=\"slug\"]").click()
                    page.locator("input[name=\"slug\"]").fill(slug)
                except Exception:
                    pass # Bỏ qua nếu không tìm thấy ô slug

        except Exception as e:
            raise Exception(f"[LỖI] Xảy ra lỗi ở bước ĐIỀU HƯỚNG hoặc ĐIỀN TÊN SẢN PHẨM.\nChi tiết mã lỗi: {e}")
        
        try:
            print(f"[{__name__}] Nhập nội dung HTML...")
            # Đợi một chút để các khung CKEditor/TinyMCE load hẳn
            page.wait_for_timeout(2000)
            
            editor_frames = page.locator("iframe[title*='Bộ soạn thảo văn bản có định dạng']")
            editor_frames.first.wait_for()
            
            count = editor_frames.count()
            print(f"[{__name__}] Tìm thấy {count} khung soạn thảo.")
            
            # Ô "Mô tả" (thường là ô đầu tiên) - ta điền tên sản phẩm làm mô tả ngắn
            if count > 0:
                # Chuyển đổi \n thành <br> hoặc chỉ cần fill text nếu CKEditor tự xử lý
                editor_frames.nth(0).content_frame.locator("body").fill(short_desc)
                page.wait_for_timeout(2000)
                
            # Ô "Nội dung" (thường là ô thứ hai) - ta click nút "Mã HTML" và điền vào textarea
            # Tìm tất cả các nút có tiêu đề "Mã HTML" (trên CKEditor)
            source_buttons = page.locator("a[title='Mã HTML']")
            
            if count > 1:
                # Click nút Mã HTML của khung thứ 2 (khung Nội dung)
                if source_buttons.count() > 1:
                    source_buttons.nth(1).click()
                elif source_buttons.count() == 1:
                    source_buttons.first.click()
                    
                # Chờ textarea hiển thị ra
                page.wait_for_timeout(500)
                
                # Điền vào textarea có class cke_source (textarea cuối cùng đang hiển thị)
                source_textareas = page.locator("textarea.cke_source")
                if source_textareas.count() > 0:
                    source_textareas.last.fill(html_content)
                else:
                    # Nếu không tìm thấy class cke_source, fallback về việc điền iframe (trường hợp click thất bại)
                    editor_frames.nth(1).content_frame.locator("body").fill(html_content)
                
                page.wait_for_timeout(2000)
        except Exception as e:
            raise Exception(f"[LỖI] Xảy ra lỗi ở bước NHẬP MÔ TẢ VÀ NỘI DUNG HTML.\nChi tiết mã lỗi: {e}")
            
        try:
            if thumbnail_path and os.path.exists(thumbnail_path):
                abs_thumb = os.path.abspath(thumbnail_path)
                print(f"[{__name__}] Upload Thumbnail: {os.path.basename(abs_thumb)}")
                page.locator("#lfm_thumbnail").click()
                
                # Sử dụng file_chooser để tránh lỗi Node is not an HTMLInputElement
                with page.expect_file_chooser() as fc_info:
                    try:
                        page.locator("form").filter(has_text="Kéo thả files vào đây hoặc nh").click(timeout=3000)
                    except:
                        page.locator("#mlib-upload-tab div").filter(has_text="Kéo thả files vào đây hoặc nh").click()
                        
                file_chooser = fc_info.value
                file_chooser.set_files(abs_thumb)
                
                print(f"[{__name__}] Đang chờ hệ thống upload Thumbnail...")
                page.wait_for_timeout(2000)
                
                # Chuyển về tab thư viện
                page.locator("#mlib-media-li").click()
                page.wait_for_timeout(1000)
                
                # Click chọn ảnh đầu tiên vừa tải lên
                page.locator(".mlib-thumbs").first.click()
                page.wait_for_timeout(1000) 
                
                try:
                    page.locator("text=/Chèn [Ff]ile/i").last.click(timeout=3000)
                except:
                    pass
                
                page.wait_for_timeout(1000)

        except Exception as e:
            raise Exception(f"[LỖI] Xảy ra lỗi ở bước UPLOAD HÌNH ẢNH (Thumbnail).\nChi tiết mã lỗi: {e}")
            
        try:
            if gallery_paths and len(gallery_paths) > 0:
                print(f"[{__name__}] Upload {len(gallery_paths)} ảnh Gallery...")
                abs_galleries = [os.path.abspath(p) for p in gallery_paths if os.path.exists(p)]
                
                if abs_galleries:
                    page.locator("#lfm_gallery").click()
                    
                    with page.expect_file_chooser() as fc_info:
                        try:
                            page.locator("#mlib-upload-tab div").filter(has_text="Kéo thả files vào đây hoặc nh").click(timeout=3000)
                        except:
                            page.locator("form").filter(has_text="Kéo thả files vào đây hoặc nh").click()
                            
                    file_chooser = fc_info.value
                    file_chooser.set_files(abs_galleries)
                    
                    print(f"[{__name__}] Đang chờ hệ thống upload {len(abs_galleries)} ảnh Gallery...")
                    page.wait_for_timeout(3000 + 1500 * len(abs_galleries))
                    
                    page.locator("#mlib-media-li").click()
                    page.wait_for_timeout(1000)
                    
                    # Multi-select các ảnh vừa tải (chúng sẽ nằm ở đầu danh sách)
                    # Tổng số ảnh cần chọn bằng số ảnh gallery cộng thêm ảnh thumbnail (nếu có)
                    total_images_to_select = len(abs_galleries) + (1 if thumbnail_path and os.path.exists(thumbnail_path) else 0)
                    for i in range(total_images_to_select):
                        page.locator(".mlib-thumbs").nth(i).click(modifiers=["ControlOrMeta"])
                        page.wait_for_timeout(500)
                        
                    page.wait_for_timeout(1000)
                    
                    try:
                        page.locator("text=/Chèn [Ff]ile/i").last.click(timeout=3000)
                    except:
                        pass
                    
                    page.wait_for_timeout(1000)
                    
        except Exception as e:
            raise Exception(f"[LỖI] Xảy ra lỗi ở bước LƯU THƯ VIỆN ẢNH (Gallery).\nChi tiết mã lỗi: {e}")
            
        try:
            print(f"[{__name__}] Lưu nháp sản phẩm...")
            # Bỏ chọn "Hiện" để lưu nháp (tránh public bài sai)
            page.get_by_role("checkbox", name=" Hiện").uncheck()
            page.get_by_role("button", name="Lưu").click()
        except Exception as e:
            raise Exception(f"[LỖI] Xảy ra lỗi ở bước LƯU NHÁP.\nChi tiết mã lỗi: {e}")

        print(f"[{__name__}] >>> Hoàn tất quy trình đăng sản phẩm: {seo_title} <<<")
        
        # Chờ 3 giây để hệ thống CMS kịp xử lý trước khi đóng browser
        page.wait_for_timeout(3000)
        
        context.close()
        browser.close()

if __name__ == "__main__":
    pass
