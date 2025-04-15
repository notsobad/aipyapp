
print("Loading GUI plugin...")
class Plugin:
    def on_task_start(self, prompt):
        print("Plugin on_task_start", prompt)

    def on_exec(self, blocks):
        print("Plugin on_exec", blocks)
        return blocks

    def on_result(self, result):
        print("Plugin on_result", result)
        return result

    def on_response_complete(self, response):
        print("Plugin on_response_complete", response)
        return response
