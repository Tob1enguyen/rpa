import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import hashlib

def download_file(url, save_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return save_path

def get_product_data(url, temp_dir="temp_data"):
    # Tạo tên thư mục con dựa trên URL
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    url_slug = path_parts[-1] if path_parts else hashlib.md5(url.encode()).hexdigest()[:8]
    
    product_temp_dir = os.path.join(temp_dir, url_slug)
    
    if not os.path.exists(product_temp_dir):
        os.makedirs(product_temp_dir)
        
    print(f"[{__name__}] Đang tải trang web: {url} -> Lưu vào {product_temp_dir}")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Bỏ qua cào ảnh, chỉ lấy PDF
    pdf_url = None
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Trang Suzumo thường dùng hubfs cho các file tài liệu pdf
        if '.pdf' in href.lower() or ('hubfs' in href.lower() and 'pdf' in href.lower()):
            pdf_url = urljoin(url, href)
            break
            
    pdf_path = None
    
    if pdf_url:
        print(f"[{__name__}] Tải PDF: {pdf_url}")
        pdf_path = os.path.join(product_temp_dir, "document.pdf")
        download_file(pdf_url, pdf_path)
    else:
        print(f"[{__name__}] KHÔNG tìm thấy file PDF nào trên trang.")
        
    # Cào nội dung text phòng trường hợp không có PDF
    for element in soup(["script", "style", "nav", "footer", "header"]):
        element.extract()
    page_text = soup.get_text(separator='\n', strip=True)
    text_path = os.path.join(product_temp_dir, "webpage_content.txt")
    with open(text_path, "w", encoding="utf-8") as f:
        f.write(page_text)
    print(f"[{__name__}] Đã trích xuất nội dung văn bản trang web.")
        
    return {
        "pdf_path": pdf_path,
        "text_path": text_path
    }

if __name__ == "__main__":
    # Test thử module khi chạy trực tiếp file này
    test_url = "https://www.suzumokikou.com/products/products/sushi-making-machine/ssn-jlxtrs-jlx/"
    result = get_product_data(test_url)
    print("Kết quả test Module 1:", result)
