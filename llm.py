#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

import openai

class LLM:
    def __init__(self, model=None):
        self._model = model or os.getenv("OPENAI_MODEL")
        self._history = []
        self._client = openai.Client()

    @property
    def history(self):
        return self._history
    
    def get_last_message(self, role='assistant'):
        for msg in reversed(self._history):
            if msg['role'] == role:
                return msg['content']
        return None
     
    def __call__(self, prompt, system_prompt=None, max_tokens=4000):
        """ Call OpenAI API to generate a response.
        Also update the history with the prompt and response.

        Returns: 
        - The response from OpenAI API
        - None if OpenAI API call fails
        """
        messages = []

        # We shall only send system prompt once
        if not self._history and system_prompt:
            self._history.append({"role": "system", "content": system_prompt})

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
        except Exception as e:
            print(f"❌ OpenAI API 调用失败: {str(e)}")
            return None
        
        self._history.append({"role": "user", "content": prompt})
        self._history.append({"role": "assistant", "content": content})
        return content