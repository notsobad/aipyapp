#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import base64
import mimetypes
from typing import Union

from openai import OpenAI

from aipyapp import TaskPlugin, PluginInitError

class ImageToolPlugin(TaskPlugin):
    """Image Tool - Provides image recognition and analysis capabilities."""
    name = "image_tool"
    version = "1.0.0"
    description = "Image Tool - Provides image recognition and analysis capabilities."
    author = "AiPy Team"
    
    def init(self):
        """初始化OpenAI客户端"""
        api_key = self.config.get('api_key')
        base_url = self.config.get('base_url')
        model = self.config.get('model', 'gpt-4-vision-preview')
        
        if not api_key:
            raise PluginInitError("API Key not configured for OpenAI.")
        
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        self.logger.info(f"Initialized OpenAI client with model: {model}")
    
    def fn_recognize_image(self,
        image_source: str,
        prompt: str = "Please describe the content of this image in detail, including the main objects, scenes, colors, and composition.",
        return_json: bool = False
    ) -> Union[str, dict]:
        """
        Use the LLM to recognize image content.
        
        Args:
            image_source: Local image path or remote image URL.
            prompt: Analysis prompt.
            return_json: Whether to return a complete JSON response.
            
        Returns:
            String description or JSON response.
        """
        return self._recognize_image(image_source, prompt, return_json)
    
    def fn_analyze_image(self, image_source: str, analysis_type: str = "general") -> str:
        """
        Deeply analyze image content.
        
        Args:
            image_source: Local image path or remote image URL.
            analysis_type: Analysis type (general/technical/artistic/text).
            
        Returns:
            Analysis result.
        """
        prompts = {
            "general": "Please describe the content of this image in detail, including the main objects, scenes, colors, and composition.",
            "technical": "Please analyze this image from a technical perspective, including shooting parameters, post-processing, technical features, etc.",
            "artistic": "Please analyze this image from an artistic perspective, including its composition, color matching, artistic style, etc.",
            "text": "Please identify and extract all text content from the image, preserving the original format."
        }
        
        prompt = prompts.get(analysis_type, prompts["general"])
        return self._recognize_image(image_source, prompt, False)
    
    def _recognize_image(self, image_source: str, prompt: str, return_json: bool) -> Union[str, dict]:
        """Internal image recognition implementation."""
        try:
            # Check if it's a local file or remote URL.
            if image_source.startswith("http://") or image_source.startswith("https://"):
                image_url = {"type": "image_url", "image_url": {"url": image_source}}
            else:
                # Local file processing.
                if not os.path.exists(image_source):
                    raise FileNotFoundError(f"File not found: {image_source}")

                mime_type, _ = mimetypes.guess_type(image_source)
                if mime_type is None:
                    mime_type = "image/jpeg"  # Default MIME type.

                with open(image_source, "rb") as f:
                    image_bytes = f.read()
                base64_image = base64.b64encode(image_bytes).decode("utf-8")
                data_url = f"data:{mime_type};base64,{base64_image}"
                image_url = {"type": "image_url", "image_url": {"url": data_url}}

            # Call OpenAI Chat interface.
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            image_url,
                        ],
                    }
                ],
                max_tokens=self.config.get('max_tokens', 1000),
            )

            # Return value processing.
            if return_json:
                return response.model_dump()
            else:
                return response.choices[0].message.content
                
        except Exception as e:
            self.logger.error(f"Image recognition failed: {e}")
            raise