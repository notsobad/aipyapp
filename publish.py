import sys
import os
import json

import requests
from bs4 import BeautifulSoup

API_URL = "https://ai.xxyy.eu.org/api/publish"
CLIENT_CRT = 'client.crt'

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
            cert=CLIENT_CRT
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
