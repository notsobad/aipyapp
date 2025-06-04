import wx
import importlib.resources as resources

from .. import __version__, T, __respkg__
from ..aipy.config import CONFIG_DIR

class AboutDialog(wx.Dialog):
    def __init__(self, parent):
        super().__init__(parent, title=T("About AIPY"))
        
        # 创建垂直布局
        vbox = wx.BoxSizer(wx.VERTICAL)
        
        logo_panel = wx.Panel(self)
        logo_sizer = wx.BoxSizer(wx.HORIZONTAL)

        with resources.path(__respkg__, "aipy.ico") as icon_path:
            icon = wx.Icon(str(icon_path), wx.BITMAP_TYPE_ICO)
            bmp = wx.Bitmap()
            bmp.CopyFromIcon(icon)
            # Scale the bitmap to a more appropriate size
            scaled_bmp = wx.Bitmap(bmp.ConvertToImage().Scale(48, 48, wx.IMAGE_QUALITY_HIGH))
            logo_sizer.Add(wx.StaticBitmap(logo_panel, -1, scaled_bmp), 0, wx.ALL | wx.ALIGN_CENTER, 5)

        # 添加标题
        title = wx.StaticText(logo_panel, -1, label=T("AIPy"))
        title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        logo_sizer.Add(title, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        logo_panel.SetSizer(logo_sizer)
        vbox.Add(logo_panel, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        # 添加描述
        desc = wx.StaticText(self, label=T("AIPY is an intelligent assistant that can help you complete various tasks."))
        desc.Wrap(350)
        vbox.Add(desc, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        # 添加版本信息
        version = wx.StaticText(self, label=f"{T('Version')}: {__version__}")
        vbox.Add(version, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        # 添加配置目录信息
        config_dir = wx.StaticText(self, label=f"{T('Current configuration directory')}: {CONFIG_DIR}")
        config_dir.Wrap(350)
        vbox.Add(config_dir, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        # 添加工作目录信息
        work_dir = wx.StaticText(self, label=f"{T('Current working directory')}: {parent.tm.workdir}")
        work_dir.Wrap(350)
        vbox.Add(work_dir, 0, wx.ALL|wx.ALIGN_CENTER, 5)
        
        # 添加团队信息
        team = wx.StaticText(self, label=T("AIPY Team"))
        vbox.Add(team, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        # 添加确定按钮
        ok_button = wx.Button(self, wx.ID_OK, T("OK"))
        vbox.Add(ok_button, 0, wx.ALL|wx.ALIGN_CENTER, 10)
        
        self.SetSizer(vbox)
        self.SetMinSize((400, 320))
        self.Fit()
        self.Centre()