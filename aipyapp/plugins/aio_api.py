class Plugin:
    """Trustoken all-in-one API plugin for AIPY
    """
    def __init__(self):
        pass

    def on_task_start(self, prompt):
        """
        任务开始事件
        param: prompt
        """
        pass

    def on_exec(self, blocks):
        """
        执行代码事件
        param: blocks
        """
        blocks['main'] = blocks['main'].replace('https://restapi.amap.com/', 'https://api.trustoken.ai/aio-api/amap/')
        print(blocks['main'])


    def on_result(self, result):
        """
        返回结果事件
        param: result
        """
        pass

    def on_response_complete(self, response):
        """
        广播LLM响应结束事件
        param: response
        """
        pass