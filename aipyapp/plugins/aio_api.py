class Plugin:
    """Trustoken all-in-one API plugin for AIPY
    """
    def on_exec(self, blocks):
        """
        执行代码事件
        param: blocks
        """
        blocks['main'] = blocks['main'].replace('https://restapi.amap.com/', 'https://api.trustoken.cn/aio-api/amap/')