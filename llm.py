#!/usr/bin/env python
# -*- coding: utf-8 -*-

import openai

class LLM:
    def __init__(self, api_key, base_url, model):
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._history = []
        self._client = openai.Client(api_key=self._api_key, base_url=self._base_url)

    def __call__(self, prompt, max_tokens=4000):
        messages = []
        
        for msg in self._history:
            if msg["role"] not in ["user", "assistant", "system"]:
                continue
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": prompt})

        try:
            response = self._client.chat.completions.create(
                model = self._model,
                messages = messages,
                max_tokens = max_tokens
            )
            
            content = response.choices[0].message.content
            success = True
        except Exception as e:
            print(f"❌ OpenAI API 调用失败: {str(e)}")
            content = f"ERROR: {str(e)}"
            success = False
        
        self._history.append({"role": "user", "content": prompt})
        self._history.append({"role": "assistant", "content": content})
        return content, success