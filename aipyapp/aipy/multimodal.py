#!/usr/bin/env python
# -*- coding: utf-8 -*-

import base64
import re
from pathlib import Path
from typing import Union, List, Dict, Any, Optional
import mimetypes

from loguru import logger

class MMContent:
    """
    多模态内容类，支持文本、图片、文件的统一处理。
    __str__ 可还原为原始输入字符串格式（@file.pdf 语法）。
    """
    def __init__(self, items: Optional[List[Dict[str, Any]]] = None):
        self.items = items or []  # 每个元素: {'type': 'text'|'image'|'file', ...}

    @classmethod
    def from_string(cls, text: str, base_path: Path = None) -> 'MMContent':
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
                        item['path'] = str(base_path / p)
        return cls(items)

    def append_text(self, text: str):
        """追加文本内容"""
        self.items.append({'type': 'text', 'text': text})

    def append_file(self, file_path: str, file_type: Optional[str] = None):
        """追加文件内容，file_type 可选 'image'|'file'，自动判断"""
        ext = Path(file_path).suffix.lower()
        if not file_type:
            file_type = 'image' if ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'} else 'file'
        self.items.append({'type': file_type, 'path': file_path})

    @property
    def content(self) -> List[Dict[str, Any]]:
        """
        返回多模态内容的结构化列表
        """
        return self.items

    @property
    def is_multimodal(self) -> bool:
        return any(item['type'] in ('image', 'file') for item in self.items)

    def __str__(self):
        """
        还原为原始输入字符串格式（@file.pdf 语法）
        """
        parts = []
        for item in self.items:
            if item['type'] == 'text':
                parts.append(item['text'])
            elif item['type'] in ('image', 'file'):
                parts.append(f"@{Path(item['path']).name}")
        return ' '.join(parts)

    def __repr__(self):
        return f"MMContent({self.items})"

    @classmethod
    def from_text_and_images(cls, text: str, image_paths: List[str] = None, base_path: Path = None) -> "MMContent":
        """
        从文本和图片路径构建多模态内容（兼容原build_multimodal_content）
        """
        items = []
        if not image_paths:
            items.append({'type': 'text', 'text': text})
        else:
            parts = re.split(r'(\{image\d+\})', text)
            image_index = 0
            for part in parts:
                if part.startswith('{image') and part.endswith('}'):
                    if image_index < len(image_paths):
                        path = str(base_path / image_paths[image_index]) if base_path else image_paths[image_index]
                        items.append({'type': 'image', 'path': path})
                        image_index += 1
                    else:
                        items.append({'type': 'text', 'text': f"[错误：图片占位符 {part} 没有对应的图片]"})
                else:
                    if part:
                        items.append({'type': 'text', 'text': part})
        return cls(items)

    def to_llm_context(self) -> Union[str, list]:
        """
        转换为 LLM API 可接受的 context 格式：
        - 只有一个纯文本时，直接返回字符串
        - 图片：image_url，自动转data url
        - 文件（如PDF）：inlineData，自动转base64
        """
        if len(self.items) == 1 and self.items[0]['type'] == 'text':
            return self.items[0]['text']
        result = []
        for item in self.items:
            if item['type'] == 'text':
                result.append({"type": "text", "text": item['text']})
            elif item['type'] == 'image':
                url = item['path']
                if url.startswith('http://') or url.startswith('https://') or url.startswith('data:'):
                    result.append({"type": "image_url", "image_url": {"url": url}})
                else:
                    try:
                        mime, _ = mimetypes.guess_type(url)
                        if not mime:
                            mime = 'image/jpeg'
                        with open(url, 'rb') as f:
                            b64 = base64.b64encode(f.read()).decode('utf-8')
                        data_url = f"data:{mime};base64,{b64}"
                        result.append({"type": "image_url", "image_url": {"url": data_url}})
                    except Exception as e:
                        result.append({"type": "text", "text": f"[图片读取失败: {url} - {e}]"})
            elif item['type'] == 'file':
                path = item['path']
                try:
                    mime, _ = mimetypes.guess_type(path)
                    if not mime:
                        mime = 'application/octet-stream'
                    with open(path, 'rb') as f:
                        b64 = base64.b64encode(f.read()).decode('utf-8')
                    result.append({
                        'type': 'inlineData',
                        "inlineData": {
                            "mimeType": mime,
                            "data": b64
                        }
                    })
                except Exception as e:
                    result.append({"type": "text", "text": f"[文件读取失败: {path} - {e}]"})
        return result
