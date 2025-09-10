#!/usr/bin/env python
# -*- coding: utf-8 -*-

from base64 import b64encode
import re
from pathlib import Path
from typing import Union, List, Dict, Any, Protocol, Literal
import mimetypes
from abc import ABC, abstractmethod

from loguru import logger
from charset_normalizer import from_bytes
from pydantic import BaseModel, Field

from ..llm import UserMessage

class MMContentError(Exception):
    """Multimodal content processing base exception"""
    pass

class FileReadError(MMContentError):
    """File read failed exception"""
    def __init__(self, file_path: str, original_error: Exception):
        self.file_path = file_path
        self.original_error = original_error
        super().__init__(f"Failed to read file {file_path}: {original_error}")

class ParseError(MMContentError):
    """Content parsing failed exception"""
    pass

class ContentItem(BaseModel):
    """Content item data class"""
    type: str
    data: Dict[str, Any] = Field(default_factory=dict)
    
    def __getitem__(self, key):
        if key == 'type':
            return self.type
        return self.data.get(key)
    
    def get(self, key, default=None):
        if key == 'type':
            return self.type
        return self.data.get(key, default)

class FileTypeDetector:
    """File type detector"""
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    
    @staticmethod
    def is_text_file(path: str, blocksize: int = 4096) -> bool:
        """Check if the file is a text file"""
        try:
            with open(path, 'rb') as f:
                chunk = f.read(blocksize)
            result = from_bytes(chunk)
            if not result:
                return False
            best = result.best()
            if best is None:
                return False
            # If encoding exists and chaos is low, it is considered text
            return best.encoding and best.chaos < 0.1
        except Exception:
            logger.exception('Failed to check if file is text')
            return False
    
    @classmethod
    def detect_file_type(cls, file_path: str) -> str:
        """Detect file type"""
        ext = Path(file_path).suffix.lower()
        
        if ext in cls.IMAGE_EXTENSIONS:
            return 'image'
        
        if cls.is_text_file(file_path):
            return 'document'
        
        return 'file'

class PathResolver:
    """Path resolver"""
    
    def __init__(self, base_path: Path = None):
        self.base_path = base_path
    
    def resolve_path(self, file_path: str) -> str:
        """Resolve file path"""
        # Remove quotes from file path
        if (file_path.startswith('"') and file_path.endswith('"')) or \
           (file_path.startswith("'") and file_path.endswith("'")):
            file_path = file_path[1:-1]
        
        # Handle relative paths
        if self.base_path:
            p = Path(file_path)
            if not p.is_absolute():
                file_path = str(self.base_path / p)
        
        return file_path

class ContentParser:
    """Content parser - responsible for parsing @file syntax"""
    
    FILE_PATTERN = re.compile(r'(@(?:"[^"]*"|\'[^\']*\'|[^\s]+))')
    
    def __init__(self, base_path: Path = None):
        self.path_resolver = PathResolver(base_path)
        self.file_detector = FileTypeDetector()
    
    def parse(self, text: str) -> List[ContentItem]:
        """Parse input text, return content item list"""
        parts = self.FILE_PATTERN.split(text)
        items = []
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if part.startswith('@'):
                item = self._parse_file_reference(part)
            else:
                item = ContentItem(type='text', data={'text': part})
            
            items.append(item)
        
        return items
    
    def _parse_file_reference(self, file_ref: str) -> ContentItem:
        """Parse file reference"""
        file_path = file_ref[1:]  # Remove @ symbol
        resolved_path = self.path_resolver.resolve_path(file_path)
        
        # Check if file exists
        if not Path(resolved_path).exists():
            return ContentItem(type='text', data={'text': file_ref})
        
        file_type = self.file_detector.detect_file_type(resolved_path)
        return ContentItem(type=file_type, data={'path': resolved_path})

class ContentProcessor(ABC):
    """Content processor abstract base class"""
    
    @abstractmethod
    def process(self, item: ContentItem) -> Dict[str, Any]:
        """Process content item"""
        pass

class TextProcessor(ContentProcessor):
    """Text processor"""
    
    def process(self, item: ContentItem) -> Dict[str, Any]:
        return {"type": "text", "text": item['text']}

class ImageProcessor(ContentProcessor):
    """Image processor"""
    
    def process(self, item: ContentItem) -> Dict[str, Any]:
        url = item['path']
        
        # Use network URL directly
        if self._is_network_url(url):
            return {"type": "image_url", "image_url": {"url": url}}
        
        # Convert local image to data URL
        mime = self._get_mime_type(url, 'image/jpeg')
        b64_data = self._read_file_as_base64(url)
        data_url = f"data:{mime};base64,{b64_data}"
        return {"type": "image_url", "image_url": {"url": data_url}}
    
    def _is_network_url(self, url: str) -> bool:
        """Check if it is a network URL"""
        return url.startswith(('http://', 'https://', 'data:'))
    
    def _get_mime_type(self, file_path: str, default_mime: str) -> str:
        """Get file MIME type"""
        mime, _ = mimetypes.guess_type(file_path)
        return mime or default_mime
    
    def _read_file_as_base64(self, file_path: str) -> str:
        """Read file and encode to base64"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            return b64encode(data).decode('utf-8')
        except Exception as e:
            raise FileReadError(file_path, e)

class DocumentProcessor(ContentProcessor):
    """Document processor"""
    
    def process(self, item: ContentItem) -> Dict[str, Any]:
        path = str(item['path'])
        content = self._read_file_as_text(path)
        text = f"<attachment filename=\"{path}\">{content}</attachment>"
        return {"type": "text", "text": text}
    
    def _read_file_as_text(self, file_path: str) -> str:
        """Read file content as text"""
        try:
            with open(file_path, 'rb') as f:
                data = f.read()
            return data.decode('utf-8')
        except Exception as e:
            raise FileReadError(file_path, e)

class FileProcessor(ContentProcessor):
    """File processor (binary file)"""
    
    def process(self, item: ContentItem) -> Dict[str, Any]:
        return {"type": "text", "text": f"file: {item['path']}"}

class ContentProcessorFactory:
    """Content processor factory"""
    
    _processors = {
        'text': TextProcessor(),
        'image': ImageProcessor(),
        'document': DocumentProcessor(),
        'file': FileProcessor(),
    }
    
    @classmethod
    def get_processor(cls, content_type: str) -> ContentProcessor:
        """Get processor for corresponding type"""
        return cls._processors.get(content_type, cls._processors['text'])
    
    @classmethod
    def register_processor(cls, content_type: str, processor: ContentProcessor):
        """Register new processor"""
        cls._processors[content_type] = processor

class ContentFormatter:
    """Content formatter - responsible for formatting processed content into LLM-acceptable format"""
    
    def __init__(self):
        self.factory = ContentProcessorFactory()
    
    def format(self, items: List[ContentItem]) -> UserMessage:
        """Format content item list"""
        results = []
        has_image = False
        
        for item in items:
            processor = self.factory.get_processor(item.type)
            result = processor.process(item)
            results.append(result)
            
            if item.type == 'image':
                has_image = True
        
        # If there is no image, merge all text
        if not has_image:
            texts = [r['text'] for r in results if r['type'] == 'text']
            return UserMessage(content='\n'.join(texts))
        
        return UserMessage(content=results)

class MMContent:
    """
    Multimodal content class, supporting unified processing of text, images, and files.
    After refactoring, the composition pattern is used, and the responsibilities are separated more clearly.
    """
    
    def __init__(self, string: str, base_path: Path = None):
        self.string = string
        self.log = logger.bind(type='MultiModal')
        
        # Use the various components of the composition
        self.parser = ContentParser(base_path)
        self.formatter = ContentFormatter()
        
        # Parse content
        self.items = self.parser.parse(string)
    
    @property
    def is_multimodal(self) -> bool:
        """Check if it contains multimodal content"""
        return any(item.type in ('image', 'file', 'document') for item in self.items)
    
    @property
    def message(self) -> UserMessage:
        """Return formatted content"""
        return self.formatter.format(self.items)
