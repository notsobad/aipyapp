#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import re
from pathlib import Path
from typing import Union, List, Dict, Any
import mimetypes

from loguru import logger

MessageList = List[Dict[str, Any]]
LLMContext = Union[str, MessageList]

class MMContentError(Exception):
    """多模态内容处理的基础异常类"""
    pass

class FileReadError(MMContentError):
    """文件读取失败异常"""
    def __init__(self, file_path: str, original_error: Exception):
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(f"无法读取文件 {file_path}: {original_error}")

class MMContent:
    """
    多模态内容类，支持文本、图片、文件的统一处理。
    """
    def __init__(self, string: str, base_path: Path = None):
        self.string = string
        self.items = self._from_string(string, base_path)

    def _from_string(self, text: str, base_path: Path = None) -> list:
        """
        从输入字符串解析多模态内容，支持@file.pdf、@image.jpg等文件引用，返回MMContent对象
        """
        parts = re.split(r'(@[^\s]+)', text)
        items = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.startswith('@'):
                file_path = part[1:]
                ext = Path(file_path).suffix.lower()
                file_type = 'image' if ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'} else 'file'
                items.append({'type': file_type, 'path': file_path})
            else:
                items.append({'type': 'text', 'text': part})

        if base_path:
            for item in items:
                if item.get('type') in ('image', 'file'):
                    p = Path(item['path'])
                    if not p.is_absolute():
                        item['path'] = base_path / p
        return items

    @property
    def is_multimodal(self) -> bool:
        return any(item['type'] in ('image', 'file') for item in self.items)
    
    def _is_network_url(self, url: str) -> bool:
        """判断是否为网络URL"""
        return url.startswith(('http://', 'https://', 'data:'))
    
    def _get_mime_type(self, file_path: str, default_mime: str) -> str:
        """获取文件的MIME类型"""
        mime, _ = mimetypes.guess_type(file_path)
        return mime or default_mime
    
    def _read_file_as_base64(self, file_path: str) -> str:
        """读取文件并转换为base64编码"""
        try:
            with open(file_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            raise FileReadError(file_path, e)
    
    def _process_image_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理图片项"""
        url = item['path']
        
        # 网络URL直接使用
        if self._is_network_url(url):
            return {"type": "image_url", "image_url": {"url": url}}
        
        # 本地图片转换为data URL
        mime = self._get_mime_type(url, 'image/jpeg')
        b64_data = self._read_file_as_base64(url)
        data_url = f"data:{mime};base64,{b64_data}"
        return {"type": "image_url", "image_url": {"url": data_url}}
    
    def _process_file_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理文件项"""
        return {"type": "file", "file": {"path": item['path']}}
    
    def _process_text_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """处理文本项"""
        return {"type": "text", "text": item['text']}
    
    @property
    def content(self) -> LLMContext:
        """返回多模态内容的结构化列表

        转换为 LLM API 可接受的 context 格式：
        - 只有一个纯文本时，直接返回字符串
        - 图片：image_url，自动转data url
        - 文件（如PDF）：inlineData，自动转base64
        """
        if not self.is_multimodal:
            return self.string
        
        results = []
        for item in self.items:
            if item['type'] == 'text':
                result = self._process_text_item(item)
            elif item['type'] == 'image':
                result = self._process_image_item(item)
            else:
                result = self._process_file_item(item)
            results.append(result)
        return results
    