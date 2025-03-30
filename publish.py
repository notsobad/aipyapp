import sys
import os
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

API_URL = "https://ai.xxyy.eu.org/api/publish"
CERT_PATH = Path('/tmp/client.crt')

CERT_STR = """
-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgd0SxLowXp0Ok6bfe
XDVY01D/lhQbYoUt5DIdPocD1EShRANCAATe/5Iv18ZHF3YQE1vwj/V7qZLp3lMD
KUsH0bLymR/tsTVc3urhbmdGTotISd8YjK0sCdbZwG6asL/FjgAFM+XQ
-----END PRIVATE KEY-----
-----BEGIN CERTIFICATE-----
MIIDSjCCAjKgAwIBAgIUZay0Lz7lDWJOijp13RZf0jR2mLwwDQYJKoZIhvcNAQEL
BQAwgagxCzAJBgNVBAYTAlVTMRMwEQYDVQQIEwpDYWxpZm9ybmlhMRYwFAYDVQQH
Ew1TYW4gRnJhbmNpc2NvMRkwFwYDVQQKExBDbG91ZGZsYXJlLCBJbmMuMRswGQYD
VQQLExJ3d3cuY2xvdWRmbGFyZS5jb20xNDAyBgNVBAMTK01hbmFnZWQgQ0EgYWY0
YTk3ODNkN2FkNTdiYjM4MWQ1YzZmMGNlYWMyMzAwHhcNMjUwMzI3MjMxMDAwWhcN
MzUwMzI1MjMxMDAwWjAiMQswCQYDVQQGEwJVUzETMBEGA1UEAxMKQ2xvdWRmbGFy
ZTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABN7/ki/XxkcXdhATW/CP9Xupkune
UwMpSwfRsvKZH+2xNVze6uFuZ0ZOi0hJ3xiMrSwJ1tnAbpqwv8WOAAUz5dCjgbsw
gbgwEwYDVR0lBAwwCgYIKwYBBQUHAwIwDAYDVR0TAQH/BAIwADAdBgNVHQ4EFgQU
wFCmHJl6KU84rtkK37vVDhnxdUgwHwYDVR0jBBgwFoAUpgvvo2E6+NBpBknAqaSs
iXJUT0YwUwYDVR0fBEwwSjBIoEagRIZCaHR0cDovL2NybC5jbG91ZGZsYXJlLmNv
bS84Zjc2NzQwZS1kNmQ0LTQ2ZDUtODZiMi1lNzFjZWRjOGUxY2YuY3JsMA0GCSqG
SIb3DQEBCwUAA4IBAQBZlLhY26owKyeS7KdwNVhyW0vGq5npWc8EkxdlaMyfofdv
ugexnKlmBeVI5kWa3nJ+pCcgHU+oPMTkF9hw2cXjJ+0NREnAvpRdZn+1ujhmK0/Q
MIShQPoD+7ff3QzXjrvw4Brij+6qh6OwLNlEtER726K3kw8hzOod+cWDgXvS9Aig
jGyaXjQybA+iOfiSSVvI76e/0VsevusX0chkut+zRh/wbRPeydR/Gp12BPUzV0mA
ZzbdlBM6jq3cSzLlwyDJX8hbl/CA6rG/RROoniJQyYgwcCFX8MlZz9PTrG11APYD
DHRz8uDQLmtuAvJEjJzd314a7a/3FWqd6odzK4sj
-----END CERTIFICATE-----
"""

def upload_article(api_url, html_file_path):
    """
    调用API上传文章
    
    参数:
        api_url: API基础URL (如 "https://localhost/api/articles")
        title: 文章标题
        html_file_path: HTML文件路径
    """
    if not os.path.isfile(html_file_path):
        print(f"错误: 文件 {html_file_path} 不存在")
        return False

    if not (CERT_PATH.exists() and CERT_PATH.stat().st_size  > 0):
        CERT_PATH.write_text(CERT_STR)

    with open(html_file_path, 'r', encoding='utf-8') as file:
        html_content = file.read()
    soup = BeautifulSoup(html_content, 'html.parser')
    title = soup.find('span', class_='r4').get_text()

    try:
        files = {
            'content': (html_file_path, html_content, 'text/html')
        }
        meta = {'author': os.getlogin()}
        data = {
            'title': title,
            'metadata': json.dumps(meta)
        }        
        
        response = requests.post(
            api_url,
            files=files,
            data=data,
            cert=str(CERT_PATH),
            verify=True
        )
        
        if response.status_code == 201:
            print("文章上传成功!")
            print("访问URL:", response.json()['url'])
            return True
        else:
            print(f"上传失败 (状态码: {response.status_code}):", response.text)
            return False
    except Exception as e:
        print("发生错误:", str(e))
        return False

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python upload_article.py 'path/to/article.html'")
        sys.exit(1)
    
    html_file = sys.argv[1]
    
    print(f"正在上传文件: {html_file})")
    upload_article(API_URL, html_file)
