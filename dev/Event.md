# Event 描述

在 AiPy 中全局对象 `event_bus` 负责事件注册和通知。
主要有以下事件调用方式和事件类型：

# Event 调用方式
## pipeline
`pipeline` 调用方式的传入参数是 `dict` ，每个插件都能修改,流水线处理事件，返回最终结果。

## broadcast
`broadcast` 调用方式的传入参数是 `*args, **kwargs`， 广播消息给每个插件进行处理。

# Event 类型
## task_start
- 调用方式：pipeline
- 参数：prompt dict

 `task_start`为任务开始事件，在插件中实现 `on_task_start` 方法即可用插件处理爱派任务开始的相关参数，例如改写用户任务提示词，在用户任务的提示词前后附加提示词等.   
 
`prompt['task']` 为用户输入的任务，`prompt` 参数包含其他例如python版本、终端、当前时间等运行环境信息。


## exec
- 调用方式：pipeline
- 参数：blocks dict

`exec` 为 LLM 生成代码执行事件，在插件中实现 `on_exec` 方法即可用插件处理 LLM 生成的代码，例如保存代码到本地文件等。  

`blocks['main']` 为即将执行的代码块。

## result
- 调用方式：pipeline
- 参数：result dict

`result` 为代码执行结果处理事件，在插件中实现 `on_result` 方法即可用插件处理代码执行的结果，例如用插件获取执行结果，生成其他格式报告等。

## response_complete
- 调用方式：broadcast
- 参数：response dict
  - llm: LLM 名称
  - content: LLM 返回消息的完整内容

`response_complete` 为大模型 LLM 响应结束事件，在插件中实现`on_response_complete`方法即可用插件处理大模型 LLM 的返回内容。例如保存大模型 LLM 返回内容到本地文件等

## response_stream
- 调用方式：broadcast
- 参数：response dict
  - llm: LLM 名称
  - content: LLM 返回的一行消息
  - reazon: True/False，表示是否 Thinking 内容，只在 Thinking 内容时有该字段

`response_stream` 为大模型 LLM 流式响应事件，在插件中实现`on_response_stream`方法即可用插件处理大模型 LLM 的返回内容。例如保存大模型 LLM 返回内容到本地文件等

## summary
- 调用方式：broadcast
- 参数：执行统计信息字符串

## display
- 调用方式：broadcast
- 参数：要显示的图片 url 或者 path
