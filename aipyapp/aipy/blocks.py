#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from collections import OrderedDict
from typing import Optional, Dict, Any, List

from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

from .types import Error, Errors
from ..interface import Trackable

class CodeBlock(BaseModel):
    """Code block"""
    name: str = Field(title="Block name", min_length=1, strip_whitespace=True)
    lang: str = Field(title="Block language", min_length=1, strip_whitespace=True)
    code: str = Field(title="Block code", min_length=1)
    path: Optional[str] = Field(title="Block path", default=None)
    version: int = Field(default=1, ge=1, title="Block version")
    deps: Optional[Dict[str, set]] = Field(default_factory=dict, title="Block dependencies")

    def add_dep(self, dep_name: str, dep_value: Any):
        """添加依赖"""
        if self.deps is None:
            self.deps = {}
        if dep_name not in self.deps:
            deps = set()
            self.deps[dep_name] = deps
        else:
            deps = self.deps[dep_name]

        # dep_value 可以是单个值，或者一个可迭代对象
        if isinstance(dep_value, (list, set, tuple)):
            deps.update(dep_value)
        else:
            deps.add(dep_value)

    def save(self) -> bool:
        """保存代码块到文件"""
        if not self.path:
            return False
            
        try:
            path = Path(self.path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self.code, encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to save block {self.name} to {self.path}", error=e)
            return False
        return True

    @property
    def abs_path(self):
        if self.path:
            return Path(self.path).absolute()
        return None
    
    def get_lang(self):
        lang = self.lang.lower()
        return lang

    def __str__(self):
        return f"<CodeBlock name={self.name}, version={self.version}, lang={self.lang}, path={self.path}>"

class CodeBlocks(Trackable, BaseModel):
    """代码块集合"""
    history: List[CodeBlock] = Field(default_factory=list)
    blocks: Dict[str, CodeBlock] = Field(default_factory=OrderedDict, exclude=True)

    def model_post_init(self, __context: Any):
        self._log = logger.bind(src='CodeBlocks')

    def __len__(self):
        return len(self.blocks)

    def __getitem__(self, key: str) -> CodeBlock:
        return self.blocks[key]

    def __contains__(self, key: str) -> bool:
        return key in self.blocks

    def __iter__(self):
        return iter(self.blocks.values())
    
    def _add_block(self, block: CodeBlock, validate: bool = True):
        """添加代码块"""
        if validate:
            old_block = self.blocks.get(block.name)
            if old_block:
                block.version = old_block.version + 1
                self._log.info(f"Update block {block.name} version to {block.version}")
            
        self.blocks[block.name] = block
        self.history.append(block)
        block.save()

    def add_blocks(self, code_blocks: List[CodeBlock]):
        """添加代码块"""
        for block in code_blocks:
            self._add_block(block)
        self._log.info(f"Added {len(code_blocks)} blocks")

    def get(self, block_name: str) -> Optional[CodeBlock]:
        block = self.blocks.get(block_name)
        if not block:
            self._log.error("Block not found", block_name=block_name)
        return block

    def edit_block(self, block_name: str, old_str: str, new_str: str, replace_all: bool = False) -> Optional[Error]:
        """
        编辑指定代码块，创建新版本而不修改原代码块
        
        Args:
            block_name: 代码块名称
            old_str: 要替换的字符串
            new_str: 新字符串
            replace_all: 是否替换所有匹配项
            
        Returns:
            Error: 错误信息
        """
        if block_name not in self.blocks:
            return Error.new("Block not found")
            
        original_block = self.blocks[block_name]
        
        # 检查是否找到匹配的字符串
        if old_str not in original_block.code:
            return Error.new(f"No match found for {old_str[:50]}...")
        
        # 检查匹配次数
        match_count = original_block.code.count(old_str)
        if match_count > 1 and not replace_all:
            return Error.new(f"Multiple matches found for {old_str[:50]}...", suggestion="set replace_all: true or provide more specific context")
        
        # 执行替换生成新代码
        new_code = original_block.code.replace(old_str, new_str, -1 if replace_all else 1)
        
        # 创建新的代码块（版本号+1）
        new_block = original_block.model_copy(
            update={
                "version": original_block.version + 1,
                "code": new_code,
                "deps": original_block.deps.copy() if original_block.deps else {}
            }
        )
        self._add_block(new_block, validate=False)
        return None

    def get_state(self) -> dict:
        """Get state data for persistence"""
        return self.model_dump(include={'history'})
    
    def restore_state(self, state: dict):
        """Restore state from code block data"""
        try:
            history = state['history']
        except Exception as e:
            self._log.error(f"Failed to restore state: {e}")
            return
        
        if history:
            self.history = self.model_validate(history)
            for block in self.history:
                self.blocks[block.name] = block

    def clear(self):
        self.history.clear()
        self.blocks.clear()
    
    # Trackable接口实现
    def get_checkpoint(self) -> int:
        """获取当前检查点状态 - 返回history长度"""
        return len(self.history)
    
    def restore_to_checkpoint(self, checkpoint: Optional[int]):
        """恢复到指定检查点"""
        if checkpoint is None:
            # 恢复到初始状态
            self.clear()
        else:
            # 恢复到指定长度
            if checkpoint < len(self.history):
                # 获取要删除的代码块
                deleted_blocks = self.history[checkpoint:]
                
                # 从 blocks 字典中删除对应的代码块
                for block in deleted_blocks:
                    if block.name in self.blocks:
                        del self.blocks[block.name]
                
                # 截断 history 到指定长度
                self.history = self.history[:checkpoint]