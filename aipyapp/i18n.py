#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale
import csv
from importlib import resources
import os
import ctypes
import platform

from loguru import logger

def get_system_language() -> str:
    """
    获取当前运行环境的语言代码 (例如 'en', 'zh')。
    支持 Windows, macOS, Linux。
    返回小写的语言代码，如果无法确定则返回 'en'。
    """
    language_code = 'en' # 默认英语

    try:
        if platform.system() == "Windows":
            # Windows: 使用 GetUserDefaultUILanguage 或 GetSystemDefaultUILanguage
            # https://learn.microsoft.com/en-us/windows/win32/intl/language-identifiers
            windll = ctypes.windll.kernel32
            # GetUserDefaultUILanguage 返回当前用户的UI语言ID
            lang_id = windll.GetUserDefaultUILanguage()
            # 将语言ID转换为标准语言代码 (例如 1033 -> en, 2052 -> zh)
            # 主要语言ID在低10位
            primary_lang_id = lang_id & 0x3FF
            if primary_lang_id == 0x04: # zh - Chinese
                language_code = 'zh'
            elif primary_lang_id == 0x09: # en - English
                language_code = 'en'
            # 可以根据需要添加更多语言ID映射
            # 参考: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-lcid/a9eac961-e77d-41a6-90a5-ce1a8b0cdb9c

        elif platform.system() == "Darwin": # macOS
            # macOS: 优先使用 locale.getlocale()
            language, encoding = locale.getlocale()
            if language:
                language_code = language.split('_')[0].lower()
            else:
                # 备选方案: 读取环境变量
                lang_env = os.environ.get('LANG')
                if lang_env:
                    language_code = lang_env.split('_')[0].lower()

        else: # Linux/Unix
            # Linux/Unix: 优先使用 locale.getlocale()
            language, encoding = locale.getlocale()
            if language:
                language_code = language.split('_')[0].lower()
            else:
                # 备选方案: 读取环境变量 LANG 或 LANGUAGE
                lang_env = os.environ.get('LANG') or os.environ.get('LANGUAGE')
                if lang_env:
                    language_code = lang_env.split('_')[0].lower()

        # 规范化常见的中文代码
        if language_code.startswith('zh'):
            language_code = 'zh'

    except Exception:
        # 如果发生任何错误，回退到默认值 'en'
        pass # 使用默认的 'en'

    return language_code

class Translator:
    def __init__(self, lang=None):
        self.lang = lang
        self.messages = {}
        self.log = logger.bind(src='i18n')

    def get_lang(self):
        return self.lang

    def set_lang(self, lang=None):
        """Set the current language."""
        if not lang:
            lang = get_system_language()
            self.log.info(f"No language specified, using system language: {lang}")

        if lang != self.lang:
            if self.lang: self.log.info(f"Switching language from {self.lang} to: {lang}")
            else: self.log.info(f"Setting language to: {lang}")
            self.lang = lang
            self.load_messages()

    def load_messages(self):
        try:
            with resources.open_text('aipyapp.res', 'locales.csv') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.messages[row['en']] = None if self.lang=='en' else row.get(self.lang)
        except Exception as e:
            self.log.error(f"Error loading translations: {e}")

    def translate(self, key, *args):
        if not self.lang:
            self.set_lang()

        if self.lang == 'en':
            msg = key
        else:
            msg = self.messages.get(key)
            if not msg:
                self.log.error(f"Translation not found for key: {key}")
                msg = key
        return msg.format(*args) if args else msg   

translator = Translator()
T = translator.translate
get_lang = translator.get_lang
set_lang = translator.set_lang

