#!/usr/bin/env python
# -*- coding: utf-8 -*-

import time
from collections import Counter
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Union, Tuple
from enum import Enum

from loguru import logger
from pydantic import BaseModel, Field

from ..llm import MessageRole, UserMessage
from .chat import ChatMessage, MessageStorage

class ContextStrategy(Enum):
    """上下文管理策略"""
    SLIDING_WINDOW = "sliding_window"      # 滑动窗口
    IMPORTANCE_FILTER = "importance_filter"  # 重要性过滤
    SUMMARY_COMPRESSION = "summary_compression"  # 摘要压缩
    HYBRID = "hybrid"                      # 混合策略

@dataclass
class ContextConfig:
    """上下文管理配置"""
    max_tokens: int = 100000               # 最大token数
    max_rounds: int = 10                   # 最大对话轮数
    auto_compress: bool = True             # 是否自动压缩
    strategy: ContextStrategy = ContextStrategy.HYBRID
    compression_ratio: float = 0.3         # 压缩比例
    importance_threshold: float = 0.5      # 重要性阈值
    summary_max_length: int = 200          # 摘要最大长度
    preserve_system: bool = True           # 是否保留系统消息
    preserve_recent: int = 3               # 保留最近几轮对话

    def set_strategy(self, strategy: str) -> Union[ContextStrategy, None]:
        try:
            strategy = ContextStrategy(strategy)
            self.strategy = strategy
        except ValueError:
            strategy = None
        return strategy

    @classmethod
    def from_dict(cls, data: dict) -> 'ContextConfig':
        obj = cls(**data)
        obj.set_strategy(data.get('strategy', 'hybrid'))
        return obj
    
    def to_dict(self) -> dict:
        return self.__dict__

class MessageCompressor:
    """消息压缩器"""
    
    def __init__(self, message_store: MessageStorage, config: ContextConfig):
        self.config = config
        self.message_store = message_store
        self.log = logger.bind(src='message_compressor')
    
    def compress_messages(self, messages: List[ChatMessage], current_tokens: int) -> Tuple[List[ChatMessage], int]:
        """压缩消息列表"""
        if current_tokens <= self.config.max_tokens:
            return messages, current_tokens
        
        strategy = self.config.strategy
        if strategy == ContextStrategy.SLIDING_WINDOW:
            return self._sliding_window_compress(messages, current_tokens)
        elif strategy == ContextStrategy.IMPORTANCE_FILTER:
            return self._importance_filter_compress(messages, current_tokens)
        elif strategy == ContextStrategy.SUMMARY_COMPRESSION:
            return self._summary_compression_compress(messages, current_tokens)
        elif strategy == ContextStrategy.HYBRID:
            return self._hybrid_compress(messages, current_tokens)
        else:
            return messages, current_tokens
    
    def _sliding_window_compress(self, messages: List[ChatMessage], current_tokens: int) -> Tuple[List[ChatMessage], int]:
        """滑动窗口压缩"""
        preserved_messages = []
        preserved_tokens = 0
        
        # 保留系统消息
        system_messages = [msg for msg in messages if msg.role == MessageRole.SYSTEM]
        for msg in system_messages:
            preserved_messages.append(msg)
            preserved_tokens += self.estimate_message_tokens(msg.content)
        
        # 保留最近的对话
        recent_messages = [msg for msg in messages if msg.role != MessageRole.SYSTEM]
        max_recent = self.config.preserve_recent * 2  # 用户+助手消息
        
        for msg in recent_messages[-max_recent:]:
            msg_tokens = self.estimate_message_tokens(msg.content)
            if preserved_tokens + msg_tokens <= self.config.max_tokens:
                preserved_messages.append(msg)
                preserved_tokens += msg_tokens
            else:
                break
        
        self.log.info(f"Sliding window compression: {len(messages)} -> {len(preserved_messages)} messages")
        return preserved_messages, preserved_tokens
    
    def _importance_filter_compress(self, messages: List[ChatMessage], current_tokens: int) -> Tuple[List[ChatMessage], int]:
        """重要性过滤压缩"""
        # 计算消息重要性分数
        scored_messages = []
        for i, msg in enumerate(messages):
            score = self._calculate_importance_score(msg, i, len(messages))
            scored_messages.append((score, msg))
        
        # 按重要性排序
        scored_messages.sort(key=lambda x: x[0], reverse=True)
        
        preserved_messages = []
        preserved_tokens = 0
        
        for score, msg in scored_messages:
            msg_tokens = self.estimate_message_tokens(msg.content)
            if preserved_tokens + msg_tokens <= self.config.max_tokens:
                preserved_messages.append(msg)
                preserved_tokens += msg_tokens
            else:
                break
        
        # 按原始顺序重新排序
        preserved_messages.sort(key=lambda x: messages.index(x))
        
        self.log.info(f"Importance filter compression: {len(messages)} -> {len(preserved_messages)} messages")
        return preserved_messages, preserved_tokens
    
    def _summary_compression_compress(self, messages: List[ChatMessage], current_tokens: int) -> Tuple[List[ChatMessage], int]:
        """摘要压缩"""
        preserved_messages: List[ChatMessage] = []
        preserved_tokens = 0
        
        # 保留系统消息
        system_messages = [msg for msg in messages if msg.role == MessageRole.SYSTEM]
        for msg in system_messages:
            preserved_messages.append(msg)
            preserved_tokens += self.estimate_message_tokens(msg.content)
        
        # 保留最近的对话
        recent_messages: List[ChatMessage] = [msg for msg in messages if msg.role != MessageRole.SYSTEM]
        max_recent = self.config.preserve_recent * 2
        
        # 分割消息
        if len(recent_messages) > max_recent:
            old_messages = recent_messages[:-max_recent]
            new_messages = recent_messages[-max_recent:]
            
            # 创建摘要消息
            summary_content = self._create_summary(old_messages)
            summary_msg = UserMessage(
                content=f"对话历史摘要：{summary_content}"
            )
            
            preserved_messages.append(self.message_store.store(summary_msg))
            preserved_tokens += self.estimate_message_tokens(summary_msg.content)
        
        # 添加新消息
        for msg in recent_messages[-max_recent:]:
            msg_tokens = self.estimate_message_tokens(msg.content)
            if preserved_tokens + msg_tokens <= self.config.max_tokens:
                preserved_messages.append(msg)
                preserved_tokens += msg_tokens
            else:
                break
        
        self.log.info(f"Summary compression: {len(messages)} -> {len(preserved_messages)} messages")
        return preserved_messages, preserved_tokens
    
    def _hybrid_compress(self, messages: List[ChatMessage], current_tokens: int) -> Tuple[List[ChatMessage], int]:
        """混合压缩策略"""
        # 首先尝试滑动窗口
        compressed_messages, compressed_tokens = self._sliding_window_compress(messages, current_tokens)
        
        # 如果仍然超出限制，使用摘要压缩
        if compressed_tokens > self.config.max_tokens:
            compressed_messages, compressed_tokens = self._summary_compression_compress(messages, current_tokens)
        
        return compressed_messages, compressed_tokens
    
    def _calculate_importance_score(self, message: ChatMessage, index: int, total: int) -> float:
        """计算消息重要性分数"""
        score = 0.0
        
        # 基于角色评分
        role = message.role
        if role == MessageRole.SYSTEM:
            score += 1.0  # 系统消息最重要
        elif role == MessageRole.USER:
            score += 0.8  # 用户消息次重要
        elif role == MessageRole.ASSISTANT:
            score += 0.6  # 助手消息一般重要
        
        # 基于位置评分（越新越重要）
        recency = (index + 1) / total
        score += recency * 0.4
        
        # 基于内容长度评分
        content = message.content
        if isinstance(content, str):
            length_score = min(len(content) / 1000, 1.0)  # 标准化到0-1
            score += length_score * 0.2
        
        return score
    
    def _create_summary(self, messages: List[ChatMessage]) -> str:
        """创建消息摘要"""
        summary_parts = []
        
        for msg in messages:
            role = msg.role
            content = msg.content
            
            if isinstance(content, str):
                # 截取前100个字符作为摘要
                content_preview = content[:100] + ('...' if len(content) > 100 else '')
                summary_parts.append(f"{role}: {content_preview}")
        
        summary = " | ".join(summary_parts)
        return summary[:self.config.summary_max_length]
    
    def estimate_message_tokens(self, content: str | List[Dict[str, Any]]) -> int:
        """估算消息的token数量"""
        if isinstance(content, str):
            total_length = len(content) // 4  # 简单估算
        elif isinstance(content, list):
            # 多模态内容
            total_length = 0
            for item in content:
                if item.get('type') == 'text':
                    total_length += len(item.get('text', ''))
        return total_length // 4

class ContextData(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    total_tokens: int = 0
    
    def __len__(self):
        return len(self.messages)
    
class ContextManager:
    """上下文管理器"""
    
    def __init__(self, message_store: MessageStorage, data: ContextData, config: dict | None = None):
        self.config = ContextConfig.from_dict(config or {})
        self.message_store = message_store
        self.compressor = MessageCompressor(message_store, self.config)
        self.log = logger.bind(src='context_manager')
        
        self.data = data
        self._last_compression_time = 0
        
    @property
    def total_tokens(self):
        return self.data.total_tokens
    
    @property
    def messages(self):
        return self.data.messages
    
    def add_message(self, message: ChatMessage):
        """添加消息到上下文"""
        # 添加到缓存
        self.data.messages.append(message)
        total_tokens = 0
        if message.role == MessageRole.ASSISTANT:
            total_tokens = message.usage.get('total_tokens', 0)

        if total_tokens == 0:
            total_tokens = self.compressor.estimate_message_tokens(message.content)
        self.data.total_tokens = total_tokens
        self.log.info(f"Added message: {message.role}, tokens: {self.data.total_tokens}, id: {message.id}")
    
    def get_messages(self, force_compress: bool = False) -> List[ChatMessage]:
        """获取压缩后的消息列表"""
        current_time = time.time()
        
        # 检查是否需要压缩
        if force_compress or self.config.auto_compress:
            should_compress = (
                force_compress or
                self.total_tokens > self.config.max_tokens or
                len(self.data.messages) > self.config.max_rounds * 2 or
                (current_time - self._last_compression_time) > 300  # 5分钟强制压缩
            )
            
            if should_compress:
                self.compress()
        
        return [msg.message.dict() for msg in self.data.messages]
    
    def compress(self):
        """压缩消息"""
        if not self.data.messages:
            return
        
        original_count = len(self.data.messages)
        original_tokens = self.total_tokens
        
        # 执行压缩
        compressed_messages, compressed_tokens = self.compressor.compress_messages(
            self.data.messages, self.data.total_tokens
        )
        
        # 更新缓存
        self.data.messages = compressed_messages
        self.data.total_tokens = compressed_tokens
        self._last_compression_time = time.time()
        
        self.log.info(
            f"Context compressed: {original_count}->{len(compressed_messages)} messages, "
            f"{original_tokens}->{compressed_tokens} tokens"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """获取上下文统计信息"""
        return {
            'message_count': len(self.data.messages),
            'total_tokens': self.data.total_tokens,
            'last_compression': self._last_compression_time
        }
    
    def clear(self):
        """清理消息缓存，只保留最初的两条消息和最后一条消息"""
        messages = self.data.messages
        if not messages or len(messages) <= 2:
            return
            
        if messages[0].role == MessageRole.SYSTEM:
            if len(messages) > 3:
                messages[2] = messages[-1]
                del messages[3:]
        else:
            messages[1] = messages[-1]
            del messages[2:]
        
        self._last_compression_time = 0
        self.data.total_tokens = sum(self.compressor.estimate_message_tokens(msg.content) for msg in messages)
        self.log.info(f"Context cleaned: {len(self.data.messages)} messages, {self.data.total_tokens} tokens")

    def rebuild(self, messages: List[ChatMessage]):
        """重建消息缓存"""
        self.data.messages.clear()
        self.data.total_tokens = 0
        
        for message in messages:
            self.add_message(message)
    
    def update_config(self, config: ContextConfig):
        """更新配置"""
        self.config = config
        self.compressor = MessageCompressor(config)
        self.log.info(f"Context config updated: {config.strategy.value}")
    