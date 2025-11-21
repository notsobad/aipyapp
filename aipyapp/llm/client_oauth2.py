#! /usr/bin/env python
# -*- coding: utf-8 -*-

import time
import httpx
from typing import Optional, Dict

from .base_openai import OpenAIBaseClient

class OAuth2Client(OpenAIBaseClient):
    """
    OAuth2-based OpenAI LLM client that:
    1. First gets token using client_id/client_secret
    2. Then uses the token to make LLM API calls
    """
    def __init__(self, config):
        super().__init__(config)
        self._access_token: Optional[str] = None
        self._token_expires = 0

    @property
    def token_url(self):
        return self.config.get_extra_field('token_url')

    @property
    def client_id(self):
        return self.config.get_extra_field('client_id')

    @property
    def client_secret(self):
        return self.config.get_extra_field('client_secret')

    def usable(self) -> bool:
        return all([
            self.token_url,
            self.client_id,
            self.client_secret,
            self.base_url
        ])

    def _get_client(self):
        # 动态设置 API key 为 access token
        # 注意：这里需要临时修改 config 的 api_key
        original_api_key = self.config.api_key
        self.config.api_key = self._get_access_token()

        try:
            client = super()._get_client()
        finally:
            # 恢复原始 api_key
            self.config.api_key = original_api_key

        return client

    def _get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials"""
        current_time = time.time()

        # Return existing token if it's still valid (with 300 seconds buffer)
        if self._access_token and current_time < (self._token_expires - 300):
            return self._access_token

        auth_data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'client_credentials'
        }

        # 获取 scope 参数（如果有）
        scope = self.config.get_extra_field('scope')
        if scope:
            auth_data['scope'] = scope

        with httpx.Client(timeout=self.config.timeout, verify=self.config.tls_verify) as client:
            response = client.post(
                self.token_url,
                data=auth_data
            )
            response.raise_for_status()
            token_data = response.json()
            self._access_token = token_data['access_token']

        # Calculate expiration time (default to 5 mins if not provided)
        expires_in = token_data.get("expires_in", 300)
        self._token_expires = current_time + expires_in

        return self._access_token
        
    def get_completion(self, messages, **kwargs):
        response = super().get_completion(messages, **kwargs)
        self._client = None

        return response
