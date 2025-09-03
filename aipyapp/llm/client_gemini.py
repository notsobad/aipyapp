#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any
from collections import Counter

from google import genai
from google.genai import types
from loguru import logger

from .base import BaseClient, AIMessage

class GeminiClient(BaseClient):
    MODEL = 'gemini-2.5-flash'
    
    def usable(self):
        return super().usable() and self._api_key
    
    def _get_client(self):
        return genai.Client(api_key=self._api_key)
    
    def _prepare_messages(self, messages: list[Dict[str, Any]]) -> list[types.Content]:
        """将OpenAI格式的messages转换为Gemini的contents格式"""
        contents = []
        
        for msg in messages:
            role = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'system':
                self._system_prompt = content
            elif role == 'user':
                contents.append(types.UserContent(
                    parts=[types.Part.from_text(text=content)]
                ))
            elif role == 'assistant':
                contents.append(types.ModelContent(
                    parts=[types.Part.from_text(text=content)]
                ))
        
        return contents
    
    def _parse_usage(self, response) -> Counter:
        """解析Gemini响应中的使用统计"""
        usage = Counter()
        
        # Gemini响应的usage结构可能不同，需要适配
        if hasattr(response, 'usage_metadata'):
            metadata = response.usage_metadata
            usage.update({
                'input_tokens': getattr(metadata, 'prompt_token_count', 0),
                'output_tokens': getattr(metadata, 'candidates_token_count', 0),
                'total_tokens': getattr(metadata, 'total_token_count', 0)
            })
        
        return usage
    
    def _parse_stream_response(self, response, stream_processor) -> AIMessage:
        """处理Gemini的流式响应"""
        usage = Counter()
        
        with stream_processor as lm:
            for chunk in response:
                # 处理流式响应的每个chunk
                if hasattr(chunk, 'text') and chunk.text:
                    lm.process_chunk(chunk.text, reason=False)
                
                # 获取usage信息
                if hasattr(chunk, 'usage_metadata'):
                    usage = self._parse_usage(chunk)
        
        return AIMessage(
            content=lm.content,
            reason=lm.reason,
            usage=usage
        )
    
    def _parse_response(self, response) -> AIMessage:
        """处理Gemini的非流式响应"""
        content = ""
        
        # 获取响应文本
        if hasattr(response, 'text'):
            content = response.text
        elif hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and candidate.content:
                content = candidate.content.parts[0].text
        
        return AIMessage(
            content=content,
            reason=None,
            usage=self._parse_usage(response)
        )
    
    def get_completion(self, messages: list[Dict[str, Any]], **kwargs) -> Any:
        """获取Gemini的completion响应"""
        if not self._client:
            self._client = self._get_client()
        
        # 准备生成参数
        generation_config = types.GenerateContentConfig(
            temperature=self._temperature,
            max_output_tokens=self.max_tokens,
            system_instruction=self._system_prompt,
            tools=[types.Tool(
                google_search=types.GoogleSearch()
            )]
        )
        
        try:
            response = self._client.models.generate_content_stream(
                model=self._model,
                contents=messages,
                config=generation_config,
            )
            return response
        except Exception as e:
            self.log.exception("Gemini API call failed", e=e)
            raise e