#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from typing import Dict, Type, Optional
from rich.console import Console

from loguru import logger

from .. import T
from .base import BaseDisplayPlugin
from .style_classic import DisplayClassic
from .style_modern import DisplayModern
from .style_minimal import DisplayMinimal
from .style_null import DisplayNull
from .style_agent import DisplayAgent
from .themes import get_theme, THEMES

class DisplayManager:
    """显示效果管理器"""
    
    # 可用的显示效果插件
    DISPLAY_PLUGINS = {
        'classic': DisplayClassic,
        'modern': DisplayModern,
        'minimal': DisplayMinimal,
        'agent': DisplayAgent,
    }
    
    def __init__(self, display_config, console: Console = None, record: bool = True, quiet: bool = False):
        """
        Args:
            console: 控制台对象
            record: 是否记录输出，控制是否可以保存HTML文件
            quiet: 是否安静模式，控制是否输出到控制台，不影响记录功能
            display_config: display配置字典，包含style、theme等设置
        """
        # 处理display配置
        config = display_config or {}
        self.console = console
        self.style = config.get('style', 'classic')
        self.theme = config.get('theme', 'default')
        self.record = config.get('record', True)
        self.quiet = config.get('quiet', False)
        self._record_buffer = console._record_buffer[:] if console else []
        self.logger = logger.bind(src='display_manager')
        self.logger.info(f"DisplayManager initialized with style: {self.style}, theme: {self.theme}")
        
    def get_available_styles(self) -> list:
        """获取可用的显示风格列表"""
        return list(self.DISPLAY_PLUGINS.keys())
        
    def get_available_themes(self) -> list:
        """获取可用的主题列表"""
        return list(THEMES.keys())
        
    def get_display_plugin(self) -> Optional[BaseDisplayPlugin]:
        """获取当前显示插件"""
        plugin_class = self.DISPLAY_PLUGINS[self.style]

        if self.quiet:
            if not self.record:
                quiet = True
            else:
                quiet = False
                file = open(os.devnull, 'w', encoding='utf-8')
        else:
            quiet = False
            file = None

        # 获取用户配置的主题
        rich_theme = get_theme(self.theme)
        console = Console(file=file, record=self.record, quiet=quiet, theme=rich_theme)
        console._record_buffer.extend(self._record_buffer)
        return plugin_class(console, quiet=self.quiet)
        
    def register_plugin(self, name: str, plugin_class: Type[BaseDisplayPlugin]):
        """注册新的显示效果插件"""
        self.DISPLAY_PLUGINS[name] = plugin_class
        
    def get_plugin_info(self) -> Dict[str, str]:
        """获取插件信息"""
        info = {}
        for name, plugin_class in self.DISPLAY_PLUGINS.items():
            info[name] = T(plugin_class.__doc__) or f"{name} display style"
        return info
    
 