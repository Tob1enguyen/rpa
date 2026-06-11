import os
import re

def clean_filename(name):
    # Loại bỏ các ký tự không hợp lệ cho tên file trên Windows
    return re.sub(r'[\\/*?:"<>|]', "", name)

def rename_images_in_folder(folder_path, product_name):
    """
    Tìm tất cả các file ảnh trong thư mục, đổi tên thành:
    [Tên sản phẩm] 1.jpg (Nếu ảnh gốc có số 1 đứng đầu - dùng làm Thumbnail)
    [Tên sản phẩm] 2.jpg, [Tên sản phẩm] 3.jpg ... (Dùng làm Gallery)
    Trả về dict: {"thumbnail": "path", "gallery": ["path", "path"]}
    """
    if not os.path.exists(folder_path):
        print(f"[{__name__}] Không tìm thấy thư mục {folder_path}")
        return {"thumbnail": None, "gallery": []}
        
    valid_exts = ('.jpg', '.jpeg', '.png', '.webp')
    all_files = os.listdir(folder_path)
    
    # Lọc ra các file ảnh
    images = [f for f in all_files if f.lower().endswith(valid_exts)]
    if not images:
        print(f"[{__name__}] Không có file ảnh nào trong thư mục {folder_path}")
        return {"thumbnail": None, "gallery": []}
        
    # Sắp xếp ảnh để xử lý. Tìm ảnh bắt đầu bằng "1" để làm thumbnail.
    thumbnail_file = None
    for img in images:
        if img.startswith('1.') or img.startswith('1-') or img.startswith('1_') or img == '1' + os.path.splitext(img)[1]:
            thumbnail_file = img
            break
            
    if not thumbnail_file and images:
        # Nếu không có ảnh nào bắt đầu bằng 1, lấy đại ảnh đầu tiên theo alphabet
        images.sort()
        thumbnail_file = images[0]
        
    gallery_files = [img for img in images if img != thumbnail_file]
    
    safe_product_name = clean_filename(product_name)
    
    # Đổi tên Thumbnail
    thumb_ext = os.path.splitext(thumbnail_file)[1]
    new_thumb_name = f"{safe_product_name} 1{thumb_ext}"
    old_thumb_path = os.path.join(folder_path, thumbnail_file)
    new_thumb_path = os.path.join(folder_path, new_thumb_name)
    
    try:
        if old_thumb_path != new_thumb_path:
            if os.path.exists(new_thumb_path):
                os.remove(new_thumb_path)
            os.rename(old_thumb_path, new_thumb_path)
    except Exception as e:
        print(f"[{__name__}] Lỗi khi đổi tên ảnh thumbnail: {e}")
        new_thumb_path = old_thumb_path # Giữ nguyên nếu lỗi
        
    result = {
        "thumbnail": new_thumb_path,
        "gallery": []
    }
    
    # Đổi tên Gallery
    counter = 2
    for img in gallery_files:
        ext = os.path.splitext(img)[1]
        new_name = f"{safe_product_name} {counter}{ext}"
        old_path = os.path.join(folder_path, img)
        new_path = os.path.join(folder_path, new_name)
        
        try:
            if old_path != new_path:
                if os.path.exists(new_path):
                    os.remove(new_path)
                os.rename(old_path, new_path)
        except Exception as e:
            print(f"[{__name__}] Lỗi khi đổi tên ảnh gallery {img}: {e}")
            new_path = old_path
            
        result["gallery"].append(new_path)
        counter += 1
        
    print(f"[{__name__}] Đã đổi tên {len(images)} ảnh cho sản phẩm '{safe_product_name}'")
    return result

if __name__ == "__main__":
    pass
