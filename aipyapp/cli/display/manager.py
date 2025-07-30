#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Dict, Type, Optional
from rich.console import Console

from loguru import logger

from ... import T
from .base import BaseDisplayPlugin
from .style_classic import DisplayClassic
from .style_modern import DisplayModern
from .style_minimal import DisplayMinimal

class DisplayManager:
    """显示效果管理器"""
    
    # 可用的显示效果插件
    DISPLAY_PLUGINS = {
        'classic': DisplayClassic,
        'modern': DisplayModern,
        'minimal': DisplayMinimal,
    }
    
    def __init__(self, console: Console, default_style: str = 'classic'):
        self.console = console
        self.current_plugin: Optional[BaseDisplayPlugin] = None
        self.plugins: Dict[str, BaseDisplayPlugin] = {}
        self.logger = logger.bind(src='display_manager')

        # 初始化默认插件
        self.set_style(default_style)
        
    def get_available_styles(self) -> list:
        """获取可用的显示风格列表"""
        return list(self.DISPLAY_PLUGINS.keys())
        
    def set_style(self, style_name: str) -> bool:
        """设置显示风格"""
        if style_name not in self.DISPLAY_PLUGINS:
            self.logger.error(f"Invalid display style: {style_name}")
            return False
            
        # 如果插件还没有创建，则创建它
        if style_name not in self.plugins:
            plugin_class = self.DISPLAY_PLUGINS[style_name]
            self.plugins[style_name] = plugin_class(self.console)
            
        self.current_plugin = self.plugins[style_name]
        self.logger.info(f"Set display style to {style_name}")
        return True
        
    def get_current_plugin(self) -> Optional[BaseDisplayPlugin]:
        """获取当前显示插件"""
        return self.current_plugin
        
    def register_plugin(self, name: str, plugin_class: Type[BaseDisplayPlugin]):
        """注册新的显示效果插件"""
        self.DISPLAY_PLUGINS[name] = plugin_class
        
    def get_plugin_info(self) -> Dict[str, str]:
        """获取插件信息"""
        info = {}
        for name, plugin_class in self.DISPLAY_PLUGINS.items():
            info[name] = T(plugin_class.__doc__) or f"{name} display style"
        return info 