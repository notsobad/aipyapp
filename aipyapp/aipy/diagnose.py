#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from io import BytesIO

import requests

class NoopDiagnose:
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            pass
        return noop

class Diagnose:
    def __init__(self, api_url, api_key):
        self._api_url = api_url
        self._api_key = api_key

    @classmethod
    def create(cls, settings):
        config = settings.get('diagnose')
        if config:
            api_key = config.get('api_key')
            api_url = config.get('api_url')
            enabled = config.get('enabled', True)
            if not api_key or not api_url:
                enabled = False
        else:
            enabled = False

        return cls(api_url, api_key) if enabled else NoopDiagnose()
    
    def report_data(self, data, filename):
        try:
            data = json.dumps(data, ensure_ascii=False, indent=4)
            data = BytesIO(data.encode('utf-8'))
        except Exception as e:
            return False
        
        headers = {'API-KEY': self._api_key}
        files = {'file': (filename, data)}

        try:
            response = requests.post(self._api_url, files=files, headers=headers)
            success = 200 <= response.status_code < 300
        except Exception as e:
            success = False

        return success

    def report_code_error(self, history):
        # Report code execution errors from history
        # Each history entry contains code and execution result
        # We only collect entries with traceback information
        # Returns True if report was sent successfully
        data = []

        for h in history:
            result = h.get('result')
            if not result:
                continue
            traceback = result.get('traceback')
            if not traceback:
                continue
            data.append({
                'code': h.get('code'),
                'traceback': traceback,
                'error': result.get('errstr')
            })

        if data:
            return self.report_data(data, 'code_error.json')
        return True

if __name__ == '__main__':
    settings = {
        'diagnose': {
            'api_key': 'sk-aipy-',
            'api_url': 'https://aipy.ror.workers.dev/',
        }
    }
    diagnose = Diagnose.create(settings)
    diagnose.report_code_error([
        {'code': 'print("Hello, World!")', 'result': {'traceback': 'Traceback (most recent call last):\n  File "test.py", line 1, in <module>\n    print("Hello, World!")\nNameError: name \'print\' is not defined\n', 'errstr': 'NameError: name \'print\' is not defined'}}
    ])
