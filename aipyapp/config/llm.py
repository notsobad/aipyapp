#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from .base import BaseConfig
from ..aipy.i18n import T, __lang__

if __lang__ == "zh":
    PROVIDERS = {
        "Trustoken": {
            "api_base": T("tt_base_url"),
            "models_endpoint": "/models",
            "type": "trust",
            "model": "auto"
        },
        "DeepSeek": {
            "api_base": "https://api.deepseek.com",
            "models_endpoint": "/models",
            "type": "deepseek"
        },
    }
else:
    PROVIDERS = {
        "Trustoken": {
            "api_base": T("tt_base_url"),
            "models_endpoint": "/models",
            "type": "trust",
            "model": "auto"
        },
        "DeepSeek": {
            "api_base": "https://api.deepseek.com",
            "models_endpoint": "/models",
            "type": "deepseek"
        },
        "xAI": {
            "api_base": "https://api.x.ai/v1",
            "models_endpoint": "/models",
            "type": "grok"
        },
        "Claude": {
            "api_base": "https://api.anthropic.com/v1",
            "models_endpoint": "/models",
            "type": "claude"
        },
        "OpenAI": {
            "api_base": "https://api.openai.com/v1",
            "models_endpoint": "/models",
            "type": "openai"
        },
        "Gemini": {
            "api_base": "https://generativelanguage.googleapis.com/v1beta/",
            "models_endpoint": "/models",
            "type": "gemini"
        },
    }

class LLMConfig(BaseConfig):
    FILE = "llm.json"

    def __init__(self, path: str):
        super().__init__(path)
        self.providers = PROVIDERS

    def need_config(self):
        """检查是否需要配置LLM。
        """
        if not self.config:
            return True
        
        for _, config in self.config.items() :
            if config.get("enable", True):
                return False
        return True
