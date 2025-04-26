#!/usr/bin/env python
# -*- coding: utf-8 -*-

import locale
import csv
from importlib import resources

from loguru import logger
__lang__ = 'en'
MESSAGES = None

def load_messages(lang):
    """Load messages from the CSV file."""
    global MESSAGES

    MESSAGES = {}
    try:
        with resources.open_text('aipyapp.res', 'locales.csv') as f:
            reader = csv.DictReader(f)
            for row in reader:
                MESSAGES[row['id']] = None if lang=='en' else row.get(lang)
    except Exception as e:
        logger.error(f"Error loading translations: {e}")

def set_lang(lang=None):
    """Set the current language."""
    global __lang__

    if not lang:
        lang = 'en'
        language, _ = locale.getlocale()
        if language:
            language = language.lower()
            if language.find('china') >= 0 or language.find('chinese') >= 0 or language.find('zh_') >= 0:
                lang = 'zh'

    __lang__ = lang
    load_messages(lang)

def T(key, *args):
    """Get translated message for the given key."""
    if not MESSAGES:
        set_lang()
    
    if __lang__ == 'en':
        return key
    
    msg = MESSAGES.get(key)
    if not msg:
        logger.error(f"Translation not found for key: {key}")
        msg = key
    return msg.format(*args) if args else msg
