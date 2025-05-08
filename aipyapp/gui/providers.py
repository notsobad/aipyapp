#! /usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import wx
import wx.adv
from loguru import logger
from typing import List
class ProviderPage(wx.adv.WizardPageSimple):
    def __init__(self, parent, provider_config):
        super().__init__(parent)
        self.provider_config = provider_config
        self.init_ui()
        self.SetSize(800, 600)

    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 标题
        title = wx.StaticText(self, label="选择 LLM 提供商")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        vbox.Add(title, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Provider 选择
        provider_box = wx.StaticBox(self, label="提供商")
        provider_sizer = wx.StaticBoxSizer(provider_box, wx.VERTICAL)
        
        self.provider_choice = wx.Choice(
            self,
            choices=list(self.provider_config.providers.keys())
        )
        self.provider_choice.Bind(wx.EVT_CHOICE, self.on_provider_selected)
        provider_sizer.Add(self.provider_choice, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(provider_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # API Key 输入
        api_key_box = wx.StaticBox(self, label="API Key")
        api_key_sizer = wx.StaticBoxSizer(api_key_box, wx.VERTICAL)
        
        self.api_key_text = wx.TextCtrl(
            self,
            size=(400, -1)
        )
        api_key_sizer.Add(self.api_key_text, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(api_key_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # 提示信息
        hint = wx.StaticText(self, label="请选择提供商并输入 API Key，点击下一步验证")
        hint.SetForegroundColour(wx.Colour(100, 100, 100))
        vbox.Add(hint, 0, wx.ALL, 10)

        self.SetSizer(vbox)

    def on_provider_selected(self, event):
        provider = self.provider_choice.GetStringSelection()
        if provider in self.provider_config.config:
            config = self.provider_config.config[provider]
            self.api_key_text.SetValue(config["api_key"])

    def get_provider(self):
        return self.provider_choice.GetStringSelection()

    def get_api_key(self):
        return self.api_key_text.GetValue()

class ModelPage(wx.adv.WizardPageSimple):
    def __init__(self, parent, provider_config):
        super().__init__(parent)
        self.provider_config = provider_config
        self.init_ui()
        self.SetSize(800, 600)

    def init_ui(self):
        vbox = wx.BoxSizer(wx.VERTICAL)

        # 标题
        title = wx.StaticText(self, label="选择模型")
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        vbox.Add(title, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Model 选择
        model_box = wx.StaticBox(self, label="可用模型")
        model_sizer = wx.StaticBoxSizer(model_box, wx.VERTICAL)
        
        self.model_choice = wx.Choice(self)
        model_sizer.Add(self.model_choice, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(model_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Max Tokens 配置
        max_tokens_box = wx.StaticBox(self, label="最大 Token 数")
        max_tokens_sizer = wx.StaticBoxSizer(max_tokens_box, wx.VERTICAL)
        
        self.max_tokens_text = wx.TextCtrl(self, value="8192")
        max_tokens_sizer.Add(self.max_tokens_text, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(max_tokens_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # Temperature 配置
        temp_box = wx.StaticBox(self, label="Temperature")
        temp_sizer = wx.StaticBoxSizer(temp_box, wx.VERTICAL)
        
        temp_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.temp_slider = wx.Slider(
            self,
            value=50,
            minValue=0,
            maxValue=100,
            style=wx.SL_HORIZONTAL | wx.SL_LABELS
        )
        self.temp_slider.Bind(wx.EVT_SLIDER, self.on_temp_changed)
        temp_hbox.Add(self.temp_slider, 1, wx.EXPAND | wx.ALL, 5)
        
        self.temp_text = wx.TextCtrl(self, value="0.5", size=(60, -1))
        self.temp_text.Bind(wx.EVT_TEXT, self.on_temp_text_changed)
        temp_hbox.Add(self.temp_text, 0, wx.ALL, 5)
        
        temp_sizer.Add(temp_hbox, 0, wx.EXPAND | wx.ALL, 5)
        vbox.Add(temp_sizer, 0, wx.EXPAND | wx.ALL, 5)

        # 提示信息
        self.hint = wx.StaticText(self, label="请选择要使用的模型并配置参数")
        self.hint.SetForegroundColour(wx.Colour(100, 100, 100))
        vbox.Add(self.hint, 0, wx.ALL, 10)

        self.SetSizer(vbox)

    def on_temp_changed(self, event):
        value = self.temp_slider.GetValue() / 100.0
        self.temp_text.SetValue(f"{value:.2f}")

    def on_temp_text_changed(self, event):
        try:
            value = float(self.temp_text.GetValue())
            if 0 <= value <= 1.0:
                self.temp_slider.SetValue(int(value * 100))
        except ValueError:
            pass

    def set_models(self, models: List[str], selected_model: str = None):
        self.model_choice.SetItems(models)
        if selected_model and selected_model in models:
            self.model_choice.SetStringSelection(selected_model)

    def get_selected_model(self):
        return self.model_choice.GetStringSelection()

    def get_max_tokens(self):
        try:
            return int(self.max_tokens_text.GetValue())
        except ValueError:
            return 8192

    def get_temperature(self):
        try:
            return float(self.temp_text.GetValue())
        except ValueError:
            return 0.5

class ProviderConfigWizard(wx.adv.Wizard):
    def __init__(self, llm_config, parent):
        super().__init__(parent, title="LLM Provider 配置向导")
        self.provider_config = llm_config
        self.init_ui()
        self.SetPageSize((600, 400))
        self.Centre()
        self.log = logger.bind(src="wizard")

    def init_ui(self):
        # 创建向导页面
        self.provider_page = ProviderPage(self, self.provider_config)
        self.model_page = ModelPage(self, self.provider_config)

        # 设置页面顺序
        wx.adv.WizardPageSimple.Chain(self.provider_page, self.model_page)

        # 绑定事件
        self.Bind(wx.adv.EVT_WIZARD_PAGE_CHANGED, self.on_page_changed)
        self.Bind(wx.adv.EVT_WIZARD_FINISHED, self.on_finished)

    def on_page_changed(self, event):
        if event.GetPage() == self.model_page:
            # 从第一步进入第二步时，验证 API Key 并获取模型列表
            provider = self.provider_page.get_provider()
            api_key = self.provider_page.get_api_key()

            if not provider or not api_key:
                wx.MessageBox("请选择提供商并输入 API Key", "错误", wx.OK | wx.ICON_ERROR)
                event.Veto()
                return

            models = self.get_models(provider, api_key)
            if not models:
                event.Veto()
                return

            # 设置模型列表
            selected_model = None
            if provider in self.provider_config.config:
                selected_model = self.provider_config.config[provider].get("selected_model")
            self.model_page.set_models(models, selected_model)

    def on_finished(self, event):
        provider = self.provider_page.get_provider()
        api_key = self.provider_page.get_api_key()
        selected_model = self.model_page.get_selected_model()
        max_tokens = self.model_page.get_max_tokens()
        temperature = self.model_page.get_temperature()
        provider_info = self.provider_config.providers[provider]
        
        config = self.provider_config.config
        config[provider] = {
            "api_key": api_key,
            "models": self.model_page.model_choice.GetItems(),
            "model": selected_model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "type": provider_info["type"]
        }

        self.provider_config.save_config(config)
        wx.MessageBox("配置已保存", "成功", wx.OK | wx.ICON_INFORMATION)

    def get_models(self, provider: str, api_key: str) -> List[str]:
        provider_info = self.provider_config.providers[provider]
        headers = {
            "Content-Type": "application/json"
        }
        
        if provider == "Claude":
            headers["x-api-key"] = api_key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            response = requests.get(
                f"{provider_info['api_base']}{provider_info['models_endpoint']}",
                headers=headers
            )
            self.log.info(f"获取模型列表: {response.text}")
            if response.status_code == 200:
                data = response.json()
                self.log.info(f"获取模型列表成功: {data}")
                if provider in ["OpenAI", "DeepSeek", "xAI", "Claude"]:
                    return [model["id"] for model in data["data"]]
                elif provider == "Google Gemini":
                    return [model["name"] for model in data["models"]]
                # 其他 provider 的模型解析逻辑
                return []
        except Exception as e:
            wx.MessageBox(f"获取模型列表失败: {str(e)}", "错误", wx.OK | wx.ICON_ERROR)
            return []

def show_provider_config(llm_config, parent=None):
    wizard = ProviderConfigWizard(llm_config, parent)
    wizard.RunWizard(wizard.provider_page)
    wizard.Destroy()
    return wx.ID_OK 