#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import json
from pathlib import Path
from collections import OrderedDict

from loguru import logger
import diff_match_patch as dmp_module

class CodeBlocks:
    def __init__(self, console):
        self.console = console
        self.blocks = OrderedDict()
        self.code_pattern = re.compile(
            r'<!--\s*Code-Start:\s*(\{.*?\})\s*-->\s*```(\w+)?\s*\n(.*?)\n```[\r\n]*<!--\s*Code-End:\s*(\{.*?\})\s*-->',
            re.DOTALL
        )
        self.exec_pattern = re.compile(
            r'<!--\s*Code-Exec:\s*(\{.*?\})\s*-->'
        )
        self.patch_pattern = re.compile(
            r'<!--\s*Code-Patch:\s*(\{.*?\})\s*-->'
        )
        self.log = logger.bind(src='code_blocks')
        self.dmp = dmp_module.diff_match_patch()

    def apply_patch(self, patch_meta):
        code_id = patch_meta.get("id")
        base_id = patch_meta.get("base_id")
        patch_id = patch_meta.get("patch_id")
        filename = patch_meta.get("filename")

        if not (patch_id in self.blocks and base_id in self.blocks):
            return {'error': 'Patch or base id not found'}

        if code_id in self.blocks:
            return {'error': 'Code id already exists'}

        code = self.blocks[base_id]['content']
        patch = self.blocks[patch_id]['content']
        diff = self.dmp.patch_fromText(patch)
        self.dmp.patch_apply(diff, code)
        self.blocks[code_id] = {
            'language': self.blocks[base_id]['language'],
            'content': code,
            'filename': filename,
            'base_id': base_id,
            'patch_id': patch_id
        }
        return None

    def parse(self, markdown_text):
        blocks = OrderedDict()
        errors = []
        for match in self.code_pattern.finditer(markdown_text):
            start_json, lang, content, end_json = match.groups()
            try:
                start_meta = json.loads(start_json)
                end_meta = json.loads(end_json)
            except json.JSONDecodeError as e:
                self.console.print_exception(show_locals=True)
                error = {'JSONDecodeError': {'json_str': start_json, 'reason': e}}
                errors.append(error)
                continue

            code_id = start_meta.get("id")
            if code_id != end_meta.get("id"):
                error = {'Start and end id mismatch': {'start_id': code_id, 'end_id': end_meta.get("id")}}
                errors.append(error)
                continue

            if code_id in blocks or code_id in self.blocks:
                error = {'Duplicate code id': {'code_id': code_id}}
                errors.append(error)
                continue

            block = {
                'language': lang,
                'content': content,
                'filename': start_meta.get('filename')
            }
            blocks[code_id] = block
            if block['filename']:
                path = Path(block['filename'])
                try:
                    #TODO: path check
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(block['content'])
                except Exception as e:
                    self.log.error("Failed to save file", filename=block['filename'], reason=e)
                    self.console.print("❌ Failed to save file", filename=block['filename'], reason=e)

        self.blocks.update(blocks)

        patch_matches = self.patch_pattern.findall(markdown_text)
        for patch_match in patch_matches:
            try:
                patch_meta = json.loads(patch_match)
            except json.JSONDecodeError as e:
                error = {'Invalid JSON in Code-Patch block': {'json_str': patch_match, 'reason': e}}
                errors.append(error)

            error = self.apply_patch(patch_meta)
            if error:
                errors.append(error)

        exec_id = None
        exec_matches = self.exec_pattern.findall(markdown_text)
        if len(exec_matches) > 1:
            error = {'Only one Code-Exec block is allowed': {"count": len(exec_matches)}}
            errors.append(error)
        elif len(exec_matches) == 1:
            try:
                exec_meta = json.loads(exec_matches[0])
                exec_id = exec_meta.get("id")
                if not (exec_id in blocks or exec_id in self.blocks):
                    error = {'Invalid Code-Exec block': {'exec_id': exec_id}}
                    errors.append(error)                
            except json.JSONDecodeError as e:
                error = {'Invalid JSON in Code-Exec block': {'json_str': exec_matches[0], 'reason': e}}
                errors.append(error)
            
        return {'blocks': blocks, 'errors': errors, 'exec': exec_id}
    
    def get_code_by_id(self, code_id):
        try:    
            return self.blocks[code_id]['content']
        except KeyError:
            self.log.error("Code id not found", code_id=code_id)
            self.console.print("❌ Code id not found", code_id=code_id)
            return None
        
    def get_block_by_id(self, code_id):
        try:
            return self.blocks[code_id]
        except KeyError:
            self.log.error("Code id not found", code_id=code_id)
            self.console.print("❌ Code id not found", code_id=code_id)
            return None
