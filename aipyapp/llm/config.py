#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM Client Configuration Module

统一的 LLM 客户端配置类，包含通用参数和自定义参数支持。
"""

from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field


class ClientConfig(BaseModel):
    """
    LLM 客户端配置类

    包含所有 LLM API 调用的通用参数，以及支持自定义参数的 extra_fields
    """
    # 基础配置
    name: str = Field(..., description="客户端实例名称")
    type: str = Field("openai", description="客户端类型")

    # 管理配置
    enabled: bool = Field(
        True,
        alias="enable",  # 支持老配置文件中的 enable 字段
        description="是否启用此客户端"
    )
    default: bool = Field(False, description="是否为默认客户端")

    # API 连接配置
    api_key: Optional[str] = Field(None, description="API 密钥")
    base_url: Optional[str] = Field(None, description="API 基础 URL")
    timeout: Optional[int] = Field(None, gt=0, description="请求超时时间（秒）")
    tls_verify: bool = Field(True, description="是否验证 TLS 证书")

    # 模型配置
    model: Optional[str] = Field(None, description="模型名称")
    max_tokens: Optional[int] = Field(8192, gt=0, description="最大生成 token 数")
    temperature: Optional[float] = Field(0.1, ge=0.0, le=2.0, description="采样温度 (0.0-2.0)")
    models: Optional[List[str]] = Field(None, description="支持的模型列表")
    
    # 流式配置
    stream: bool = Field(True, description="是否使用流式响应")

    # 自定义参数 - 不同 API 特有的参数
    extra_fields: Dict[str, Any] = Field(default_factory=dict, description="客户端特定参数")

    class Config:
        extra = "forbid"  # 禁止额外字段，强制使用 extra_fields
        populate_by_name = True  # 允许通过字段名和别名访问

    def get_extra_field(self, key: str, default: Any = None) -> Any:
        """获取自定义参数值"""
        return self.extra_fields.get(key, default)

    def has_extra_field(self, key: str) -> bool:
        """检查是否包含某个自定义参数"""
        return key in self.extra_fields


def create_client_config(config_dict: Dict[str, Any]) -> ClientConfig:
    """
    创建客户端配置的便捷函数

    Args:
        config_dict: 配置字典，自动分离通用参数和自定义参数

    Returns:
        ClientConfig 实例
    """
    # 获取 ClientConfig 的字段名和别名
    config_fields = set(ClientConfig.model_fields.keys())
    field_aliases = {
        field_name: field_info.alias
        for field_name, field_info in ClientConfig.model_fields.items()
        if field_info.alias is not None
    }

    # 创建反向映射（别名 -> 字段名）
    alias_to_field = {alias: field for field, alias in field_aliases.items()}

    # 分离通用参数和自定义参数
    common_params = {}
    extra_params = {}

    for key, value in config_dict.items():
        if key in config_fields:
            common_params[key] = value
        elif key in alias_to_field:
            # 如果是别名，映射到实际字段名
            common_params[alias_to_field[key]] = value
        else:
            extra_params[key] = value

    # 添加自定义参数到通用参数中
    if extra_params:
        common_params["extra_fields"] = extra_params

    return ClientConfig.model_validate(common_params)