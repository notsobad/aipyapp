#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import uuid
import time
import platform
import locale
from io import BytesIO

import requests
from loguru import logger

from aipyapp import __version__
from aipyapp.aipy.config import CONFIG_DIR

CONFIG_FILE = CONFIG_DIR / '.diagnose.json'
UPDATE_INTERVAL = 8 * 60 * 60
class NoopDiagnose:
    def __getattr__(self, name):
        def noop(*args, **kwargs):
            pass
        return noop

class Diagnose:
    def __init__(self, api_url, api_key):
        self._api_url = api_url
        self._api_key = api_key
        self.log = logger.bind(src='diagnose')
        self.load_config()

    def save_config(self):
        CONFIG_FILE.write_text(json.dumps({'xid': self._xid, 'last_update': self._last_update}))

    def load_config(self):
        if not CONFIG_FILE.exists():
            self._xid = uuid.uuid4().hex
            self._last_update = 0
            self.save_config()
        else:
            with CONFIG_FILE.open('r') as f:
                data = json.load(f)
                self._xid = data.get('xid')
                self._last_update = data.get('last_update')

    @classmethod
    def create(cls, settings):
        config = settings.get('diagnose')
        if config:
            api_key = config.get('api_key')
            api_url = config.get('api_url')
            enabled = config.get('enabled', True)
            if not api_url:
                enabled = False
        else:
            enabled = False

        return cls(api_url, api_key) if enabled else NoopDiagnose()

    def get_meta(self):
        return {
            "system": platform.system(),
            "version": platform.version(),
            "platform": platform.platform(),
            "arch": platform.machine(),
            "python": sys.executable,
            "python_version": sys.version,
            "python_base_prefix": sys.base_prefix,
            "locale": locale.getlocale(),
        }
    
    def check_update(self, force=False):
        if not force and int(time.time()) - self._last_update < UPDATE_INTERVAL:
            return {}
        self._last_update = int(time.time())
        self.save_config()
        
        data = {
            "xid": self._xid,
            "version": __version__,
            "meta": self.get_meta()
        }
        headers = {
            "Content-Type": "application/json",
            #"API-KEY": self._api_key
        }

        try:
            response = requests.post(
                f"{self._api_url}/4b16535b7e6147f2861508a2ad5f5ce8",
                json=data,
                headers=headers
            )
            if response.status_code == 200:
                result = response.json()
                if result.get("success", False):
                    return {
                        "has_update": result.get("has_update", False),
                        "latest_version": result.get("latest_version", "unknown"),
                        "current_version": __version__,
                    }
                else:
                    self.log.error(f"Server error: {result.get('error', '未知错误')}")
            else:
                self.log.error(f"Request failed: HTTP {response.status_code}")

        except Exception as e:
            self.log.error(f"Connection error: {str(e)}")
        return {"error": "版本检查失败"}

    def report_data(self, data, filename):
        try:
            data = json.dumps(data, ensure_ascii=False, indent=4)
            data = BytesIO(data.encode('utf-8'))
        except Exception as e:
            return False
        
        headers = {'API-KEY': self._api_key}
        files = {'file': (filename, data)}

        try:
            response = requests.post(f"{self._api_url}/a6477529c8c34b6a8ca4bc2d7253ab76", files=files, headers=headers)
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
            'api_url': 'https://aipy.xxyy.eu.org/',
        }
    }
    diagnose = Diagnose.create(settings)
    update = diagnose.check_update()
    print(update)
    diagnose.report_code_error([
        {'code': 'print("Hello, World!")', 'result': {'traceback': 'Traceback (most recent call last):\n  File "test.py", line 1, in <module>\n    print("Hello, World!")\nNameError: name \'print\' is not defined\n', 'errstr': 'NameError: name \'print\' is not defined'}}
    ])
