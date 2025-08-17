#! /usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations
from typing import Any, Dict, List

from pydantic import BaseModel, Field

class Error(BaseModel):
    """错误"""
    message: str
    context: Dict[str, Any] | None = None

    @classmethod
    def new(cls, message: str, /, **context):
        return cls(message=message, context=context)

    def to_json(self) -> str:
        """获取错误信息"""
        return self.model_dump_json(exclude_none=True, exclude_unset=True)

class Errors(BaseModel):
    """错误列表"""
    errors: List[Error] = Field(default_factory=list)

    def __len__(self) -> int:
        return len(self.errors)

    def append(self, error: Error):
        self.errors.append(error)

    def add(self, message: str, /, **context):
        self.errors.append(Error(message=message, context=context))

    def extend(self, errors: Errors):
        self.errors.extend(errors.errors)

    def to_json(self) -> str:
        """获取错误信息"""
        return self.model_dump_json(exclude_none=True, exclude_unset=True)