#! /usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from .base import BaseClient
from .base_openai import OpenAIBaseClient
from typing import Optional, Dict

class OAuth2Client(OpenAIBaseClient):
    """
    OAuth2-based LLM client that:
    1. First gets token using client_id/client_secret
    2. Then uses the token to make LLM API calls
    """
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self._token_url = config.get("token_url")
        self._client_id = config.get("client_id")
        self._client_secret = config.get("client_secret")
        self._access_token: Optional[str] = None
    
    def usable(self) -> bool:
        """Check if required OAuth2 config exists"""
        return all([
            self._token_url,
            self._client_id,
            self._client_secret,
            self._api_key,  # This would be the LLM API key from parent class
            self._base_url  # LLM endpoint URL
        ])
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials"""
        if self._access_token:
            return self._access_token
            
        auth_data = {
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'grant_type': 'client_credentials'
        }
        
        response = requests.post(
            self._token_url,
            data=auth_data
        )
        response.raise_for_status()
        token_data = response.json()
        self._access_token = token_data['access_token']
        return self._access_token
    
    def _get_client_headers(self) -> Dict[str, str]:
        """Get headers with Authorization token"""
        headers = super()._get_client_headers()
        headers['Authorization'] = f"Bearer {self._get_access_token()}"
        return headers

    def get_completion(self, messages):
        """Get completion from LLM with fresh authentication headers"""
        headers = self._get_client_headers()
        # Merge headers into existing params
        if 'headers' in self._params:
            self._params['headers'].update(headers)
        else:
            self._params['headers'] = headers

        return super().get_completion(messages)
